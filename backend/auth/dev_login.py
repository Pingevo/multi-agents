"""DevLoginProvider — simple username-based login for development."""

from backend.auth.base import AuthProvider, User


class DevLoginProvider(AuthProvider):
    """Login ด้วย username ง่ายๆ สำหรับ development ไม่ต้องใช้ password"""

    async def authenticate(self, credentials: dict) -> User | None:
        username = credentials.get("username", "").strip()
        if not username:
            return None
        return User(
            user_id=f"dev_{username.lower()}",
            username=username,
            email="",
            provider="dev",
        )

    def get_login_url(self) -> str | None:
        return None
