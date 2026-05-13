"""知乎 OAuth 2.0 登录 — Authorization Code Flow

APP_ID: 217
回调: https://crucible.zeabur.app/api/auth/zhihu/callback
"""
import os
import time
import json
import secrets
import logging
from typing import Optional, Dict
from dataclasses import dataclass

import requests
from cryptography.fernet import Fernet
import base64
import hashlib

logger = logging.getLogger(__name__)

ZHIHU_APP_ID = os.getenv("ZHIHU_OAUTH_APP_ID", "217")
ZHIHU_APP_KEY = os.getenv("ZHIHU_OAUTH_APP_KEY", "")
REDIRECT_URI = os.getenv("ZHIHU_OAUTH_REDIRECT_URI", "https://crucible.zeabur.app/api/auth/zhihu/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "")

AUTHORIZE_URL = "https://openapi.zhihu.com/authorize"
TOKEN_URL = "https://openapi.zhihu.com/access_token"
USER_URL = "https://openapi.zhihu.com/user"


@dataclass
class ZhihuUser:
    uid: int
    fullname: str
    avatar_path: str = ""
    headline: str = ""
    gender: str = "unknown"


# ── State store (in-memory, ttl 10min) ────────────────
_state_store: Dict[str, float] = {}

def generate_state() -> str:
    state = secrets.token_urlsafe(32)
    _state_store[state] = time.time()
    # Cleanup expired states
    expired = [k for k, v in _state_store.items() if time.time() - v > 600]
    for k in expired:
        del _state_store[k]
    return state

def verify_state(state: str) -> bool:
    ts = _state_store.pop(state, None)
    return ts is not None and time.time() - ts < 600


# ── Simple signed token (no PyJWT dependency) ─────────
# Format: base64(json_payload).base64(hmac_signature)

def _get_signing_key() -> bytes:
    """Derive a 32-byte signing key from JWT_SECRET or ZHIHU_APP_KEY"""
    src = JWT_SECRET or ZHIHU_APP_KEY or "crucible-dev-key-change-me"
    return hashlib.sha256(src.encode()).digest()

def create_session_token(user: ZhihuUser, expires_in: int = 2592000) -> str:
    """Create a signed session token (valid for expires_in seconds, default 30 days)"""
    payload = {
        "uid": user.uid,
        "fullname": user.fullname,
        "avatar": user.avatar_path,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()
    
    import hmac as hmac_mod
    sig = hmac_mod.new(_get_signing_key(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def verify_session_token(token: str) -> Optional[Dict]:
    """Verify and decode a session token. Returns payload dict or None."""
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        
        import hmac as hmac_mod
        expected_sig = hmac_mod.new(_get_signing_key(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac_mod.compare_digest(sig, expected_sig):
            return None
        
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if time.time() > payload.get("exp", 0):
            return None
        return payload
    except Exception:
        return None


# ── OAuth flow ────────────────────────────────────────

def get_authorize_url() -> Dict[str, str]:
    """Generate authorization URL + state"""
    state = generate_state()
    url = (
        f"{AUTHORIZE_URL}?"
        f"app_id={ZHIHU_APP_ID}&"
        f"response_type=code&"
        f"redirect_uri={REDIRECT_URI}&"
        f"state={state}"
    )
    return {"authorize_url": url, "state": state}


def exchange_code(code: str) -> Optional[str]:
    """Exchange authorization code for access_token"""
    try:
        resp = requests.post(TOKEN_URL, json={
            "app_id": ZHIHU_APP_ID,
            "app_key": ZHIHU_APP_KEY,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code,
        }, timeout=15)
        data = resp.json()
        if data.get("access_token"):
            logger.info(f"OAuth token obtained, expires_in={data.get('expires_in')}")
            return data["access_token"]
        else:
            logger.error(f"Token exchange failed: {data}")
            return None
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        return None


def get_user_info(access_token: str) -> Optional[ZhihuUser]:
    """Fetch user profile with access_token"""
    try:
        resp = requests.get(USER_URL, headers={
            "Authorization": f"Bearer {access_token}"
        }, timeout=15)
        data = resp.json()
        if data.get("uid"):
            return ZhihuUser(
                uid=data["uid"],
                fullname=data.get("fullname", ""),
                avatar_path=data.get("avatar_path", ""),
                headline=data.get("headline", ""),
                gender=data.get("gender", "unknown"),
            )
        else:
            logger.error(f"User info failed: {data}")
            return None
    except Exception as e:
        logger.error(f"User info error: {e}")
        return None
