from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files import File
from rest_framework import status , viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping
from .models import Scene
from .serializers import GeoTIFFBuildSerializer, GeoAIAnalyzeSerializer, SceneSerializer
from .services import ASFSearchError , search_asf
from .geoai_client import GeoAIClientError, analyze_geotiff
from .geotiff_builder import build_rgb_like_geotiff

class SceneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Scene.objects.all()
    serializer_class = SceneSerializer

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='geotiff')
    def build_geotiff(self, request, pk=None):
        """Build the capped, 3-band "normal-photo-like" preview GeoTIFF for this scene.

        Accepts raw single-band SAR rasters (vv_file required, vh_file optional),
        each readable by rasterio with its own CRS/transform (e.g. already-
        geocoded GRD band GeoTIFFs). Output is always <= MAX_GEOTIFF_BYTES.
        """
        scene = self.get_object()
        serializer = GeoTIFFBuildSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            import rasterio
        except ImportError:
            return Response(
                {'error': 'rasterio is not installed on this server; see requirements.txt'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        vv_upload = serializer.validated_data['vv_file']
        vh_upload = serializer.validated_data.get('vh_file')
        max_bytes = serializer.validated_data.get('max_bytes') or settings.MAX_GEOTIFF_BYTES

        tmp_dir = Path(settings.MEDIA_ROOT) / 'scenes' / 'tmp' / str(scene.pk)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        vv_path = tmp_dir / f'vv_{vv_upload.name}'
        with open(vv_path, 'wb') as fh:
            for chunk in vv_upload.chunks():
                fh.write(chunk)
        vh_path = None
        if vh_upload:
            vh_path = tmp_dir / f'vh_{vh_upload.name}'
            with open(vh_path, 'wb') as fh:
                for chunk in vh_upload.chunks():
                    fh.write(chunk)

        try:
            with rasterio.open(vv_path) as vv_ds:
                vv_array = vv_ds.read(1)
                transform, crs = vv_ds.transform, vv_ds.crs
            vh_array = None
            if vh_path:
                with rasterio.open(vh_path) as vh_ds:
                    vh_array = vh_ds.read(1)

            out_path = tmp_dir / f'{scene.file_id or scene.pk}_preview.tif'
            result = build_rgb_like_geotiff(
                {'vv': vv_array, 'vh': vh_array}, transform, crs, str(out_path), max_bytes=max_bytes,
            )
        except Exception as exc:
            return Response({'error': 'Failed to build GeoTIFF', 'detail': str(exc)},
                             status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        with open(result['path'], 'rb') as fh:
            scene.geotiff_file.save(Path(result['path']).name, File(fh), save=False)
        scene.geotiff_band_count = result['band_count']
        scene.geotiff_size_bytes = result['size_bytes']
        scene.save(update_fields=['geotiff_file', 'geotiff_band_count', 'geotiff_size_bytes'])

        return Response({**SceneSerializer(scene).data, 'within_budget': result['within_budget']},
                         status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='analyze')
    def analyze_with_geoai(self, request, pk=None):
        """Send this scene's preview GeoTIFF to the separate GeoAI models API.

        The two projects stay decoupled Django apps talking plain HTTP: this
        project never imports anything from the GeoAI project, and vice versa.
        """
        scene = self.get_object()
        if not scene.geotiff_file:
            return Response(
                {'error': 'Build the preview GeoTIFF first via POST .../geotiff/'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = GeoAIAnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = analyze_geotiff(
                scene.geotiff_file.path, prompt=serializer.validated_data['prompt'],
                requested_model=serializer.validated_data.get('requested_model', 'auto'),
                point=serializer.validated_data.get('point'), box=serializer.validated_data.get('box'),
            )
        except GeoAIClientError as exc:
            return Response({'error': 'GeoAI API call failed', 'detail': str(exc)},
                             status=status.HTTP_502_BAD_GATEWAY)

        scene.analysis_report = report
        scene.save(update_fields=['analysis_report'])
        return Response(SceneSerializer(scene).data, status=status.HTTP_200_OK)

@api_view(["POST"])
def search_scenes(request):
    wkt = request.data.get("wkt")
    if not wkt:
        return Response({"error": "wkt is required"},status=status.HTTP_400_BAD_REQUEST)
    
    try:
        shape = shapely_wkt.loads(wkt)
        if (shape.is_empty or shape.geom_type != "Polygon" or not shape.is_valid):
            raise ValueError
    except Exception:
        return Response({"error": ("wkt must be a valid ""non-empty Polygon")},
                status=status.HTTP_400_BAD_REQUEST,)
    
    start_date = request.data.get("start_date")
    end_date = request.data.get("end_date")
    for value in (start_date,end_date):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                return Response(
                    {"error": ("dates must use "" YYYY-MM-DD")},
                    status=status.HTTP_400_BAD_REQUEST,)
    platform = request.data.get("platform","SENTINEL-1")

    try:
        records = search_asf(wkt=wkt , start_date=start_date , end_date=end_date , platform=platform)
    except ASFSearchError as exc:
        return Response(
            {"error": "ASF search failed","detail": str(exc),
            "hint": ("Check the WKT, dates, ""platform, and ASF availability.")},
            status=status.HTTP_502_BAD_GATEWAY)

    saved_scenes = []
    for record in records:
        file_id = record.pop("file_id",None)
        if not file_id:
            continue
        scene, _ = (Scene.objects.update_or_create(file_id=file_id,defaults=record))
        saved_scenes.append(SceneSerializer(scene).data)
    return Response(
        {"count": len(saved_scenes),"polygon": mapping(shape),"scenes": saved_scenes},
        status=status.HTTP_200_OK)
