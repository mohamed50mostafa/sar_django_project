"""HTTP client for the separate GeoAI models API (the other project).

The two projects are deployed independently (this one on its own host,
the models project as a Hugging Face Space) and talk to each other only
over plain HTTP, exactly like two unrelated third-party APIs would. This
keeps them swappable: either side can be redeployed, rescaled, or
replaced without the other one changing a single import.

Only the 3 models the GeoAI API still serves are meaningful here:
``gemini_only``, ``prithvi``, ``sam_hq``. GGUF local vision models were
disabled on that side because they failed to load reliably, so this
client never requests them.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import requests
from django.conf import settings

SUPPORTED_MODELS = ("auto", "gemini_only", "prithvi", "sam_hq")


class GeoAIClientError(Exception):
    pass


def _base_url() -> str:
    base = getattr(settings, "GEOAI_API_BASE_URL", "") or ""
    if not base:
        raise GeoAIClientError(
            "GEOAI_API_BASE_URL is not configured; set it to the deployed "
            "GeoAI models API, e.g. https://<user>-<space>.hf.space"
        )
    return base.rstrip("/")


def analyze_geotiff(file_path: str, prompt: str, requested_model: str = "auto",
                     point: list[int] | None = None, box: list[int] | None = None,
                     timeout: int | None = None) -> dict[str, Any]:
    """POST a GeoTIFF to the GeoAI API's /api/jobs/analyze/ endpoint.

    Returns the parsed JSON job record (``route`` + ``report``). Raises
    ``GeoAIClientError`` on any transport, HTTP, or configuration failure
    so callers can decide how to surface it (the view below stores it on
    the Scene and returns 502, matching the SAR API's own ASF error style).
    """
    if requested_model not in SUPPORTED_MODELS:
        raise GeoAIClientError(
            f"'{requested_model}' is not served by the GeoAI API anymore "
            f"(GGUF models are disabled). Use one of {SUPPORTED_MODELS}."
        )

    path = Path(file_path)
    if not path.exists():
        raise GeoAIClientError(f"GeoTIFF not found: {file_path}")

    url = f"{_base_url()}/api/jobs/analyze/"
    mime = mimetypes.guess_type(path.name)[0] or "image/tiff"
    data = {"prompt": prompt, "requested_model": requested_model}
    if point:
        data["point"] = ",".join(str(int(v)) for v in point)
    if box:
        data["box"] = ",".join(str(int(v)) for v in box)
    request_timeout = timeout or getattr(settings, "GEOAI_API_TIMEOUT", 120)

    try:
        with path.open("rb") as fh:
            response = requests.post(
                url, data=data, files={"file": (path.name, fh, mime)}, timeout=request_timeout
            )
    except requests.RequestException as exc:
        raise GeoAIClientError(f"Could not reach GeoAI API at {url}: {exc}") from exc

    if response.status_code >= 400:
        raise GeoAIClientError(
            f"GeoAI API returned {response.status_code} for {url}: {response.text[:500]}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise GeoAIClientError(f"GeoAI API returned a non-JSON response: {response.text[:500]}") from exc
