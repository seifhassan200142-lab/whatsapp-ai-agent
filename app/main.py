import asyncio
import hmac
import json
import logging
import sqlite3
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.security import APIKeyHeader
from pydantic import ValidationError

from .config import Settings, load_settings, secret
from .database import Database
from .handoff import escalate
from .llm import GroqGateway
from .models import AdminReply, Inbound, ServiceError
from .whatsapp import WhatsApp, verify_signature
from .worker import Worker

log = logging.getLogger("agent")
static = Path(__file__).parent / "static"
key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def create_app(settings: Settings | None = None, groq_client=None, meta_transport=None):
    settings = settings or load_settings()
    db = Database(settings.db_path)

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        for name in ("httpx", "httpcore", "groq"):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        try:
            db.init()
            db.recover()
        except sqlite3.Error as exc:
            raise RuntimeError("Database initialization failed. Check DB_PATH and folder write permission.") from exc
        async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=False,
                                     transport=meta_transport) as http:
            groq = GroqGateway(settings, db, groq_client)
            worker = Worker(settings, db, WhatsApp(settings, http), groq)
            app.state.worker, app.state.db = worker, db
            task = asyncio.create_task(worker.run()) if settings.worker_enabled else None
            app.state.worker_task = task
            log.info("startup_ok missing_settings=%s", ",".join(settings.missing()) or "none")
            try:
                yield
            finally:
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                await groq.close()

    app = FastAPI(title="WhatsApp AI Agent", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path in ("/admin", "/admin.js", "/admin.css"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return response

    async def admin_auth(key: str | None = Depends(key_header)):
        expected = secret(settings.admin_api_key)
        if not expected:
            raise HTTPException(503, "ADMIN_API_KEY is not configured")
        if not key or not hmac.compare_digest(key.encode(), expected.encode()):
            raise HTTPException(401, "Invalid admin key")

    def require_conversation(phone):
        conversation = db.conversation(phone)
        if not conversation:
            raise HTTPException(404, "Conversation not found")
        return conversation

    @app.get("/health")
    async def health():
        with db.connect() as con:
            con.execute("SELECT 1")
        task = app.state.worker_task
        running = task is not None and not task.done()
        return {"status": "ok", "database": "ok", "configured": not settings.missing(),
                "worker_running": running, "external_integrations": "not_checked_by_health_endpoint"}

    @app.get("/webhook", response_class=PlainTextResponse)
    async def verification(request: Request):
        expected = secret(settings.meta_verify_token)
        if not expected:
            raise HTTPException(503, "Verify token is not configured")
        params = request.query_params
        given = params.get("hub.verify_token", "")
        if params.get("hub.mode") != "subscribe" or not hmac.compare_digest(expected.encode(), given.encode()):
            raise HTTPException(403, "Webhook verification failed")
        challenge = params.get("hub.challenge", "")
        if not challenge or len(challenge) > 200:
            raise HTTPException(400, "Invalid challenge")
        log.info("webhook_verified")
        return challenge

    @app.post("/webhook")
    async def webhook(request: Request):
        if not secret(settings.meta_app_secret) or not settings.meta_phone_number_id:
            raise HTTPException(503, "Meta settings incomplete")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 3_000_000:
                raise HTTPException(413, "Webhook too large")
        if not verify_signature(bytes(body), request.headers.get("X-Hub-Signature-256", ""), secret(settings.meta_app_secret)):
            raise HTTPException(403, "Invalid webhook signature")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            raise HTTPException(400, "Invalid JSON")
        if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
            return {"accepted": 0}
        accepted = 0
        entries = payload.get("entry", [])
        if not isinstance(entries, list):
            raise HTTPException(400, "Invalid entry list")
        for entry in entries:
            changes = entry.get("changes", []) if isinstance(entry, dict) else []
            for change in changes if isinstance(changes, list) else []:
                if not isinstance(change, dict) or change.get("field") != "messages":
                    continue
                value = change.get("value", {})
                if not isinstance(value, dict):
                    continue
                metadata = value.get("metadata", {})
                if not isinstance(metadata, dict) or str(metadata.get("phone_number_id", "")) != settings.meta_phone_number_id:
                    continue
                messages = value.get("messages", [])
                for message in messages if isinstance(messages, list) else []:
                    if not isinstance(message, dict) or message.get("type") not in ("text", "audio"):
                        continue
                    try:
                        text_data, audio_data = message.get("text", {}), message.get("audio", {})
                        inbound = Inbound(id=message["id"], phone=message["from"],
                            timestamp=message["timestamp"], type=message["type"],
                            text=text_data.get("body", ""), media_id=audio_data.get("id", ""))
                        if (inbound.type == "text" and not inbound.text.strip()) or (inbound.type == "audio" and not inbound.media_id):
                            continue
                        accepted += db.receive(inbound)
                    except (KeyError, TypeError, AttributeError, ValidationError):
                        log.warning("ignored_malformed_message")
                statuses = value.get("statuses", [])
                for status in statuses if isinstance(statuses, list) else []:
                    if not isinstance(status, dict):
                        continue
                    errors = status.get("errors", [])
                    code = ""
                    if isinstance(errors, list) and errors and isinstance(errors[0], dict) and isinstance(errors[0].get("code"), int):
                        code = "meta_delivery_" + str(errors[0]["code"])
                    wa_id, delivery_state = status.get("id"), status.get("status")
                    if isinstance(wa_id, str) and delivery_state in ("sent", "delivered", "read", "failed"):
                        db.delivery(wa_id, delivery_state, code)
        if accepted:
            log.info("webhook_queued count=%s", accepted)
            app.state.worker.wake.set()
        return {"accepted": accepted}

    @app.get("/admin", include_in_schema=False)
    async def dashboard():
        return FileResponse(static / "admin.html")

    @app.get("/admin.js", include_in_schema=False)
    async def dashboard_js():
        return FileResponse(static / "admin.js", media_type="application/javascript")

    @app.get("/admin.css", include_in_schema=False)
    async def dashboard_css():
        return FileResponse(static / "admin.css", media_type="text/css")

    @app.get("/admin/config", dependencies=[Depends(admin_auth)])
    async def config_status():
        return {"missing": settings.missing(), "groq_model": settings.groq_model,
                "groq_whisper_model": settings.groq_whisper_model,
                "graph_version": settings.meta_graph_version,
                "knowledge_exists": settings.knowledge_path.is_file()}

    @app.get("/admin/conversations", dependencies=[Depends(admin_auth)])
    async def conversations(status: Literal["active", "human_required", "resolved"] | None = None,
                            limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        return db.list_conversations(status, limit, offset)

    @app.get("/admin/conversations/{phone}", dependencies=[Depends(admin_auth)])
    async def detail(phone: str, limit: int = Query(100, ge=1, le=200), before: int | None = Query(None, ge=1)):
        return {"conversation": require_conversation(phone), "messages": db.messages(phone, limit, before)}

    @app.post("/admin/conversations/{phone}/pause", dependencies=[Depends(admin_auth)])
    async def pause(phone: str):
        require_conversation(phone)
        async with app.state.worker.action_lock:
            await escalate(db, app.state.worker.groq, phone, db.history(phone), "operator_paused")
        return db.conversation(phone)

    @app.post("/admin/conversations/{phone}/resume", dependencies=[Depends(admin_auth)])
    async def resume(phone: str):
        require_conversation(phone)
        async with app.state.worker.action_lock:
            db.set_status(phone, "active")
        return db.conversation(phone)

    @app.post("/admin/conversations/{phone}/resolve", dependencies=[Depends(admin_auth)])
    async def resolve(phone: str):
        require_conversation(phone)
        async with app.state.worker.action_lock:
            db.set_status(phone, "resolved")
        return db.conversation(phone)

    @app.post("/admin/conversations/{phone}/reply", dependencies=[Depends(admin_auth)])
    async def reply(phone: str, body: AdminReply):
        require_conversation(phone)
        if not body.text.strip():
            raise HTTPException(422, "Reply must not be blank")
        async with app.state.worker.action_lock:
            db.set_status(phone, "human_required")
            try:
                wa_id = await app.state.worker.send(phone, body.text.strip(), actor="human")
            except ServiceError as exc:
                return JSONResponse(status_code=502, content={"detail": exc.code})
        return {"status": "accepted_by_meta", "wa_id": wa_id}

    return app


app = create_app()
