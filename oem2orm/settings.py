# oem2orm/settings.py
import os


def _get(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if (v is not None and str(v).strip() != "") else default


def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "yes", "on", "y"}


def is_local_profile() -> bool:
    profile = (_get("OEP_PROFILE") or _get("ENV") or "").strip().lower()
    if profile in {"local", "dev"}:
        return True
    # Secondary switch, if someone prefers a boolean flag
    if _truthy(_get("OEP_USE_LOCAL")):
        return True
    return False


def get_oep_user() -> str:
    return _get("OEP_USER", "")


def get_oep_host() -> str:
    if is_local_profile():
        return _get("OEP_URL_LOCAL") or _get("OEP_URL", "openenergyplatform.org")
    return _get("OEP_URL", "openenergyplatform.org")


def get_oep_api_url() -> str:
    # Build the base URL for REST meta operations
    if is_local_profile():
        base = _get("OEP_API_URL_LOCAL") or _get(
            "OEP_API_URL", "https://openenergyplatform.org/api/v0/"
        )
    else:
        base = _get("OEP_API_URL", "https://openenergyplatform.org/api/v0/")
    base = (base or "").rstrip("/") + "/"
    return base


def get_oep_token() -> str | None:
    if is_local_profile():
        return _get("OEP_API_TOKEN_LOCAL") or _get("OEP_API_TOKEN") or _get("OEP_TOKEN")
    # prod profile
    return _get("OEP_API_TOKEN") or _get("OEP_API_TOKEN_LOCAL") or _get("OEP_TOKEN")
