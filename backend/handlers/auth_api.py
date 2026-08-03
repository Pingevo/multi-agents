"""REST API endpoints for authentication (for React frontend)."""

import json
from typing import Any

import chainlit as cl
from backend.auth.system81 import System81AuthProvider
from backend.auth.session import SessionManager
from backend.auth.user_store import UserStore


@cl.on_message
async def handle_auth_api(message: cl.Message):
    """Handle REST API-style auth requests via Chainlit message."""
    content = message.content
    if not isinstance(content, str):
        return

    try:
        data = json.loads(content)
        action = data.get("action")
    except json.JSONDecodeError:
        return

    if action == "auth_login":
        # Handle login request
        token = data.get("token")
        username = data.get("username")
        password = data.get("password")

        auth_provider = System81AuthProvider()
        if token:
            user = await auth_provider.authenticate({"token": token})
        elif username and password:
            user = await auth_provider.authenticate({"username": username, "password": password})
        else:
            await cl.Message(content=json.dumps({"success": False, "error": "Missing credentials"})).send()
            return

        if user:
            # Create session token
            session_mgr = SessionManager()
            session_token = session_mgr.create_session(user.user_id)
            user_store = UserStore()
            user_store.update_last_login(user.user_id)

            await cl.Message(content=json.dumps({
                "success": True,
                "token": session_token,
                "user": {
                    "user_id": user.user_id,
                    "username": user.username,
                    "email": user.email,
                    "provider": user.provider,
                    "avatar_url": user.avatar_url,
                }
            })).send()
        else:
            await cl.Message(content=json.dumps({"success": False, "error": "Authentication failed"})).send()

    elif action == "auth_verify":
        # Handle token verification
        token = data.get("token")
        if not token:
            await cl.Message(content=json.dumps({"success": False, "error": "Missing token"})).send()
            return

        session_mgr = SessionManager()
        user_id = session_mgr.verify_token(token)
        if user_id:
            user_store = UserStore()
            profile = user_store.get_by_id(user_id)
            if profile:
                await cl.Message(content=json.dumps({
                    "success": True,
                    "valid": True,
                    "user": {
                        "user_id": user_id,
                        "username": profile.get("username", ""),
                        "email": profile.get("email", ""),
                        "provider": "system81",
                        "avatar_url": profile.get("avatar_url", ""),
                    }
                })).send()
                return

        await cl.Message(content=json.dumps({"success": False, "valid": False})).send()

    elif action == "auth_logout":
        # Handle logout
        token = data.get("token")
        if token:
            session_mgr = SessionManager()
            session_mgr.invalidate_token(token)

        await cl.Message(content=json.dumps({"success": True})).send()

    elif action == "auth_login_url":
        # Get OAuth login URL
        auth_provider = System81AuthProvider()
        login_url = auth_provider.get_login_url()
        await cl.Message(content=json.dumps({"login_url": login_url or ""})).send()
