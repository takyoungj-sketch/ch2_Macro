"""Public FieldNote app configuration; no account or database dependency."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/fieldnote", tags=["fieldnote-app"])


@router.get("/app-config")
def app_config():
    return {
        "min_version_code": settings.fieldnote_app_min_version_code,
        "latest_version_code": settings.fieldnote_app_latest_version_code,
        "message": settings.fieldnote_app_update_message,
        "blocked_features": list(dict.fromkeys(
            feature.strip()
            for feature in settings.fieldnote_app_blocked_features.split(",")
            if feature.strip()
        )),
    }
