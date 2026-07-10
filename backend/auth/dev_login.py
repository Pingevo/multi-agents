"""DevLoginProvider — username + password login checked against pre-configured list."""

from backend.auth.base import AuthProvider, User
from backend.auth.user_store import UserStore


class DevLoginProvider(AuthProvider):
    """Login ด้วย username + password ที่กำหนดไว้ล่วงหน้าใน data/users.json
    ไม่มีการสมัครอัตโนมัติ — admin ต้องเพิ่ม user เอง
    อนาคต: เปลี่ยนเป็น AuthProvider ที่เชื่อมระบบ auth ขององค์กร
    """

    def __init__(self):
        self.user_store = UserStore()

    async def authenticate(self, credentials: dict) -> User | None:
        username = credentials.get("username", "").strip()
        password = credentials.get("password", "")
        if not username or not password:
            return None

        user_id = f"dev_{username.lower()}"
        existing = self.user_store.get_by_id(user_id)

        if not existing:
            # User not found — no auto-registration
            return None

        # Verify password
        if not self.user_store.verify_password(user_id, password):
            return None

        return User(
            user_id=user_id,
            username=existing.get("username", username),
            email=existing.get("email", ""),
            provider="dev",
        )

    def get_login_url(self) -> str | None:
        return None
