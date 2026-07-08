"""카카오 Local API 주소 → 좌표 (FieldNote 등 클라이언트용 프록시)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

_LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/geocode", tags=["geocode"])


class GeocodeRequest(BaseModel):
    address: str = Field(..., min_length=1, max_length=500)


class GeocodeResponse(BaseModel):
    latitude: float
    longitude: float
    address_name: str | None = None


class GeocodeBatchRequest(BaseModel):
    addresses: list[str] = Field(..., min_length=1, max_length=50)


class GeocodeBatchItem(BaseModel):
    address: str
    latitude: float | None = None
    longitude: float | None = None
    error: str | None = None


class GeocodeBatchResponse(BaseModel):
    items: list[GeocodeBatchItem]


def _kakao_geocode_one(address: str) -> GeocodeResponse:
    api_key = (settings.kakao_rest_api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="KAKAO_REST_API_KEY not configured")

    query = urllib.parse.urlencode({"query": address.strip()})
    url = f"https://dapi.kakao.com/v2/local/search/address.json?{query}"
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"KakaoAK {api_key}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        _LOG.warning("Kakao geocode HTTP error: %s", exc)
        raise HTTPException(status_code=502, detail="Kakao geocode request failed") from exc
    except urllib.error.URLError as exc:
        _LOG.warning("Kakao geocode network error: %s", exc)
        raise HTTPException(status_code=502, detail="Kakao geocode network error") from exc

    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not documents:
        raise HTTPException(status_code=404, detail="address_not_found")

    first = documents[0]
    try:
        longitude = float(first["x"])
        latitude = float(first["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="invalid_kakao_response") from exc

    address_name = first.get("address_name") if isinstance(first, dict) else None
    return GeocodeResponse(
        latitude=latitude,
        longitude=longitude,
        address_name=str(address_name) if address_name else None,
    )


@router.post("/kakao", response_model=GeocodeResponse)
def geocode_kakao(body: GeocodeRequest) -> GeocodeResponse:
    return _kakao_geocode_one(body.address)


@router.post("/kakao/batch", response_model=GeocodeBatchResponse)
def geocode_kakao_batch(body: GeocodeBatchRequest) -> GeocodeBatchResponse:
    items: list[GeocodeBatchItem] = []
    for raw in body.addresses:
        address = raw.strip()
        if not address:
            items.append(GeocodeBatchItem(address=raw, error="empty_address"))
            continue
        try:
            result = _kakao_geocode_one(address)
            items.append(
                GeocodeBatchItem(
                    address=address,
                    latitude=result.latitude,
                    longitude=result.longitude,
                ),
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "geocode_failed"
            items.append(GeocodeBatchItem(address=address, error=detail))
    return GeocodeBatchResponse(items=items)
