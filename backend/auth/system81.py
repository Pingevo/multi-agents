"""System81AuthProvider — OAuth-style login via Sellercenter System81."""

import os
import urllib.parse
from typing import Any

import requests

from backend.auth.base import AuthProvider, User


class System81AuthProvider(AuthProvider):
    """
    Authenticate users against the Sellercenter System81 identity service.

    Supports two modes:
    - Redirect flow: user is redirected to /system81/login with a redirect_uri,
      then returns with a token that we verify.
    - Direct credentials: backend calls POST /system81/login and verifies the
      returned token.
    """

    def __init__(self):
        self.base_url = (
            os.getenv("SELLERCENTER_OAUTH_BASE_URL", "https://data.digital.in.th").rstrip("/")
        )
        self.app_name = os.getenv("SELLERCENTER_OAUTH_APP_NAME", "Multi-Agent Platform")
        self.app_logo = os.getenv("SELLERCENTER_OAUTH_APP_LOGO", "")
        self.client_id = os.getenv("SELLERCENTER_OAUTH_CLIENT_ID", "multi_agent_app")
        self.timeout = 15

    def _get_userinfo(self, token: str) -> dict[str, Any] | None:
        """Verify a System81 token by calling /system81/userinfo."""
        if not token:
            return None

        url = f"{self.base_url}/system81/userinfo"

        # Try Bearer header first
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data.get("user")
        except Exception as e:
            print(f"[System81AuthProvider] userinfo bearer error: {e}", flush=True)

        # Fallback to query parameter
        try:
            resp = requests.get(url, params={"token": token}, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data.get("user")
        except Exception as e:
            print(f"[System81AuthProvider] userinfo query error: {e}", flush=True)

        return None

    def _map_user(self, info: dict[str, Any]) -> User:
        """Convert System81 userinfo payload into our User dataclass."""
        sub = info.get("sub") or info.get("user_id") or info.get("username")
        user_id = f"system81_{sub}" if sub else ""
        return User(
            user_id=user_id,
            username=info.get("username", ""),
            email=info.get("email", ""),
            provider="system81",
            avatar_url=info.get("avatar_url") or info.get("profilePicture") or "",
            metadata={
                "name": info.get("name", ""),
                "emp_id": info.get("emp_id", ""),
                "department": info.get("department", ""),
                "position": info.get("position", ""),
            },
        )

    async def authenticate(self, credentials: dict[str, Any]) -> User | None:
        """
        Authenticate either by token or by username/password.

        - token: a System81 token obtained from the redirect flow.
        - username/password: backend performs the System81 login directly.
        """
        token = credentials.get("token")
        if token:
            info = self._get_userinfo(token)
            if info:
                return self._map_user(info)
            return None

        username = credentials.get("username", "").strip()
        password = credentials.get("password", "")
        if not username or not password:
            return None

        try:
            resp = requests.post(
                f"{self.base_url}/system81/login",
                json={"username": username, "password": password, "redirect_uri": ""},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            data = resp.json()
            if not data.get("success"):
                return None

            token = data.get("token")
            if token:
                info = self._get_userinfo(token)
                if info:
                    return self._map_user(info)

            user = data.get("user", {})
            if user:
                return self._map_user(user)
        except Exception as e:
            print(f"[System81AuthProvider] login error: {e}", flush=True)

        return None

    def get_login_url(self) -> str | None:
        """Return the URL to redirect the user to the System81 login page."""
        redirect_uri = os.getenv(
            "SELLERCENTER_OAUTH_REDIRECT_URI",
            "http://localhost:5173/",
        )
        params: dict[str, str] = {
            "app_name": self.app_name,
            "redirect_uri": redirect_uri,
        }
        if self.app_logo:
            params["app_logo"] = self.app_logo
        if self.client_id:
            params["client_id"] = self.client_id

        return f"{self.base_url}/system81/login?{urllib.parse.urlencode(params)}"
