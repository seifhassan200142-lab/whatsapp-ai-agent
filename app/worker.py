import asyncio
import logging
import time

from .handoff import asks_for_human, escalate, handoff_notice
from .models import ServiceError
from .transcription import transcribe

log = logging.getLogger("agent")


class Worker:
    def __init__(self, settings, db, whatsapp, groq):
        self.settings, self.db = settings, db
        self.whatsapp, self.groq = whatsapp, groq
        # This app deliberately supports one Uvicorn process only.
        self.action_lock = asyncio.Lock()
        self.wake = asyncio.Event()

    async def send(self, phone, text, reply_to=None, actor="bot"):
        conversation = self.db.conversation(phone)
        if not conversation or time.time() - conversation["last_incoming_at"] >= 86400:
            raise ServiceError("whatsapp_24h_window_closed")
        ident = self.db.begin_send(phone, text, reply_to, actor)
        try:
            wa_id = await self.whatsapp.send_text(phone, text)
            self.db.sent(ident, wa_id)
            log.info("meta_send_accepted local_id=%s", ident)
            return wa_id
        except ServiceError as exc:
            uncertain = exc.code == "meta_send_uncertain" or exc.code.startswith("meta_http_5")
            self.db.finish(ident, "uncertain" if uncertain else "failed", exc.code)
            self.db.set_status(phone, "human_required", error=exc.code)
            raise

    async def process(self, job):
        phone, ident = job["phone"], job["id"]
        if self.db.conversation(phone)["status"] != "active":
            self.db.finish(ident, "suppressed")
            return
        text = job["text"]
        try:
            if time.time() - job["timestamp"] >= 86400:
                raise ServiceError("whatsapp_24h_window_closed")
            if job["type"] == "audio":
                audio, mime = await self.whatsapp.download_audio(job["media_id"])
                text = await transcribe(self.groq, audio, mime)
                del audio
                self.db.set_transcript(ident, text)
                log.info("audio_transcribed local_id=%s", ident)
            history = self.db.history(phone, self.settings.history_messages, through=ident)
            if asks_for_human(text):
                await escalate(self.db, self.groq, phone, history, "customer_requested_human")
                await self.send(phone, handoff_notice(text), ident)
            else:
                try:
                    knowledge = self.settings.knowledge_path.read_text(encoding="utf-8-sig")
                    if not knowledge.strip() or len(knowledge) > 14000:
                        raise ServiceError("knowledge_empty_or_too_large")
                except OSError as exc:
                    raise ServiceError("knowledge_file_unavailable") from exc
                decision = await self.groq.decide(history, knowledge)
                if decision.handoff:
                    await escalate(self.db, self.groq, phone, history, decision.reason or "unsupported_question")
                    await self.send(phone, handoff_notice(text), ident)
                elif self.db.conversation(phone)["status"] == "active":
                    await self.send(phone, decision.reply, ident)
            self.db.finish(ident)
        except ServiceError as exc:
            log.warning("processing_failed local_id=%s code=%s", ident, exc.code)
            history = self.db.history(phone, self.settings.history_messages, through=ident)
            # Do not spend another call when the provider failed; keep a local summary.
            await escalate(self.db, self.groq, phone, history, exc.code, use_groq=False)
            self.db.finish(ident, "failed", exc.code)
            # Never retry an uncertain/failed outbound request automatically.
            if not exc.code.startswith("meta_") and exc.code != "whatsapp_24h_window_closed":
                try:
                    notice = handoff_notice(text) if text else "تعذرت معالجة الرسالة؛ تم تسجيلها للمراجعة البشرية. / Message processing failed; human review is required."
                    await self.send(phone, notice, ident)
                except ServiceError as send_error:
                    log.warning("handoff_notice_failed code=%s", send_error.code)

    async def run(self):
        while True:
            self.wake.clear()
            try:
                async with self.action_lock:
                    job = self.db.next_job()
                    if job:
                        try:
                            await self.process(job)
                        except Exception:
                            # Deliberately omit exception text/tracebacks: SDK exceptions
                            # and URLs can contain secrets or customer content.
                            log.error("unexpected_processing_error local_id=%s", job["id"])
                            self.db.finish(job["id"], "failed", "unexpected_processing_error")
                            self.db.set_status(job["phone"], "human_required",
                                               "Unexpected processing error. Review conversation.", "fallback",
                                               "unexpected_processing_error")
                if job:
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("worker_database_error")
            try:
                await asyncio.wait_for(self.wake.wait(), timeout=1)
            except TimeoutError:
                pass
