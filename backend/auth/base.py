"""AuthProvider — pluggable authentication interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class User:
    """Authenticated user identity."""
    user_id: str
    username: str
    email: str
    provider: str
    avatar_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AuthProvider(ABC):
    """Abstract auth provider — implement this to add a new login method."""

    @abstractmethod
    async def authenticate(self, credentials: dict) -> User | None:
        """Verify credentials and return User, or None if authentication failed."""
        pass

    @abstractmethod
    def get_login_url(self) -> str | None:
        """Return OAuth/SAML redirect URL, or None for form-based login."""
        pass
