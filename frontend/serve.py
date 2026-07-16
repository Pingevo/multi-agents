#!/usr/bin/env python3
"""Async reverse proxy with WebSocket support.
Serves Vite build output (dist/) + proxies /ws, /api, etc. to backend at :8000.
"""
import asyncio
import os
import sys
from aiohttp import web, ClientSession, WSMsgType

DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
BACKEND = "http://127.0.0.1:8000"
PROXY_PATHS = ("/ws", "/api", "/auth", "/project", "/public", "/favicon", "/logo")

async def proxy_http(request: web.Request) -> web.StreamResponse:
    path = request.path_qs
    url = f"{BACKEND}{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "transfer-encoding")}
    body = await request.read()
    async with ClientSession() as session:
        async with session.request(request.method, url, headers=headers, data=body, allow_redirects=False) as resp:
            ret = web.StreamResponse(status=resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "content-encoding", "content-length", "connection"):
                    ret.headers[k] = v
            await ret.prepare(request)
            async for chunk in resp.content.iter_any():
                await ret.write(chunk)
            await ret.write_eof()
            return ret

async def proxy_ws(request: web.Request) -> web.WebSocketResponse:
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)
    path = request.path_qs
    url = f"{BACKEND}{path}".replace("http://", "ws://")
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "connection", "upgrade", "sec-websocket-key", "sec-websocket-version", "sec-websocket-extensions")}
    async with ClientSession() as session:
        async with session.ws_connect(url, headers=headers) as ws_backend:
            async def c2b():
                async for msg in ws_client:
                    if msg.type == WSMsgType.TEXT:
                        await ws_backend.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_backend.send_bytes(msg.data)
                    elif msg.type == WSMsgType.CLOSE:
                        await ws_backend.close()
                        break
            async def b2c():
                async for msg in ws_backend:
                    if msg.type == WSMsgType.TEXT:
                        await ws_client.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_client.send_bytes(msg.data)
                    elif msg.type == WSMsgType.CLOSE:
                        await ws_client.close()
                        break
            await asyncio.gather(c2b(), b2c())
    return ws_client

async def handle(request: web.Request) -> web.StreamResponse:
    path = request.path
    if any(path.startswith(p) for p in PROXY_PATHS):
        if path.startswith("/ws") and request.headers.get("Upgrade", "").lower() == "websocket":
            return await proxy_ws(request)
        return await proxy_http(request)
    rel_path = path.lstrip("/")
    if not rel_path or rel_path.endswith("/"):
        rel_path = "index.html"
    file_path = os.path.join(DIST, rel_path)
    if not os.path.isfile(file_path):
        file_path = os.path.join(DIST, "index.html")
    if not os.path.isfile(file_path):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(file_path)

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    app = web.Application()
    app.router.add_route("*", "/", handle)
    app.router.add_route("*", "/{tail:.*}", handle)
    print(f"Serving {DIST} on http://{host}:{port} (proxy to {BACKEND})", flush=True)
    web.run_app(app, host=host, port=port, print=None)

if __name__ == "__main__":
    main()
