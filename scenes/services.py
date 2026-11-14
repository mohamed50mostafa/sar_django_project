from datetime import datetime


class ASFSearchError(Exception):
    pass
def _iso(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None
def search_asf(wkt , start_date=None , end_date=None , platform="SENTINEL-1"):
    try:
        import asf_search
        from asf_search import (
            ASFSearchOptions,
            ASFSession,
        )
    except ImportError as exc:
        raise ASFSearchError("asf_search is not installed") from exc

    search_params = {
        "intersectsWith": wkt,
        "platform": platform,
        "dataset": "SENTINEL-1",
        "processingLevel": "GRD",
    }

    if start_date:
        search_params["start"] = start_date

    if end_date:
        search_params["end"] = end_date

    try:
        session = ASFSession()
        options = ASFSearchOptions(session=session)
        results = asf_search.search(**search_params,opts=options)
        return [result_to_dict(item)for item in results]
    except Exception as exc:
        raise ASFSearchError(
            str(exc)
        ) from exc


def result_to_dict(item):
    properties = getattr(item,"properties",{}) or {}
    geometry = (properties.get("geometry",{}) or {})
    file_size_bytes = (properties.get("bytes") or properties.get("sizeInBytes") 
                       or properties.get("SizeInBytes")
    )
    return {"file_id": (properties.get("fileID") or properties.get("file_id")
                    or getattr(item, "name", "")),
        "scene_name": properties.get("sceneName",""),
        "platform": properties.get("platform",""),
        "sensor": properties.get("sensor",""),
        "processing_level": properties.get("processingLevel",""),
        "beam_mode": properties.get("beamModeType",""),
        "polarization": properties.get("polarization",""),
        "start_time": _iso(properties.get("startTime")),
        "stop_time": _iso(properties.get("stopTime")),
        "flight_direction": properties.get("flightDirection",""),
        "orbit": properties.get("orbit"),
        "path_number": properties.get("pathNumber"),
        "frame_number": properties.get("frameNumber"),
        "file_size_bytes": file_size_bytes,
        "download_url": properties.get("url",""),
        "geometry": geometry,
        "source_metadata": dict(properties),
        }
