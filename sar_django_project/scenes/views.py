from datetime import date
from rest_framework import status , viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping
from .models import Scene
from .serializers import SceneSerializer
from .services import ASFSearchError , search_asf

class SceneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Scene.objects.all()
    serializer_class = SceneSerializer

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
