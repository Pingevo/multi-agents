"""FastAPI server for REST API endpoints (auth, etc.)."""

import os
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.auth.system81 import System81AuthProvider
from backend.auth.session import SessionManager
from backend.auth.user_store import UserStore


# Pydantic models
class LoginRequest(BaseModel):
    username: str | None = None
    password: str | None = None
    token: str | None = None


class VerifyRequest(BaseModel):
    token: str


class LogoutRequest(BaseModel):
    token: str


class AuthResponse(BaseModel):
    success: bool
    error: str | None = None
    token: str | None = None
    user: dict[str, Any] | None = None


class VerifyResponse(BaseModel):
    success: bool
    valid: bool
    user: dict[str, Any] | None = None


class LoginUrlResponse(BaseModel):
    login_url: str


# Global instances
auth_provider = System81AuthProvider()
session_mgr = SessionManager()
user_store = UserStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for the FastAPI app."""
    print("[AUTH-API] Starting FastAPI server on port 8001", flush=True)
    yield
    print("[AUTH-API] Shutting down FastAPI server", flush=True)


app = FastAPI(lifespan=lifespan)

# CORS — frontend is served by Chainlit on port 8000, auth API on port 8001
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/login")
async def login(req: LoginRequest) -> AuthResponse:
    """Handle login with username/password or OAuth token."""
    try:
        if req.token:
            user = await auth_provider.authenticate({"token": req.token})
        elif req.username and req.password:
            user = await auth_provider.authenticate({"username": req.username, "password": req.password})
        else:
            return AuthResponse(success=False, error="Missing credentials")

        if user:
            # Create session token
            session_token = session_mgr.create_session(user.user_id)
            user_store.update_last_login(user.user_id)

            return AuthResponse(
                success=True,
                token=session_token,
                user={
                    "user_id": user.user_id,
                    "username": user.username,
                    "email": user.email,
                    "provider": user.provider,
                    "avatar_url": user.avatar_url,
                }
            )
        else:
            return AuthResponse(success=False, error="Authentication failed")
    except Exception as e:
        print(f"[AUTH-API] Login error: {e}", flush=True)
        return AuthResponse(success=False, error=str(e))


@app.post("/api/auth/verify")
async def verify(req: VerifyRequest) -> VerifyResponse:
    """Verify a session token and return user info."""
    try:
        user_id = session_mgr.verify_token(req.token)
        if user_id:
            profile = user_store.get_by_id(user_id)
            if profile:
                return VerifyResponse(
                    success=True,
                    valid=True,
                    user={
                        "user_id": user_id,
                        "username": profile.get("username", ""),
                        "email": profile.get("email", ""),
                        "provider": "system81",
                        "avatar_url": profile.get("avatar_url", ""),
                    }
                )

        return VerifyResponse(success=True, valid=False)
    except Exception as e:
        print(f"[AUTH-API] Verify error: {e}", flush=True)
        return VerifyResponse(success=False, valid=False)


@app.post("/api/auth/logout")
async def logout(req: LogoutRequest):
    """Invalidate a session token."""
    try:
        if req.token:
            session_mgr.revoke_session(req.token)
        return {"success": True}
    except Exception as e:
        print(f"[AUTH-API] Logout error: {e}", flush=True)
        return {"success": False, "error": str(e)}


@app.get("/api/auth/login-url")
async def get_login_url() -> LoginUrlResponse:
    """Get the OAuth login URL."""
    try:
        login_url = auth_provider.get_login_url()
        return LoginUrlResponse(login_url=login_url or "")
    except Exception as e:
        print(f"[AUTH-API] Login URL error: {e}", flush=True)
        return LoginUrlResponse(login_url="")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
