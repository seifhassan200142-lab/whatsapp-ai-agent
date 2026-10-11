"""Run: python -m scripts.check_setup [--groq] [--meta]. No WhatsApp is sent."""
import argparse
import asyncio

import httpx

from app.config import load_settings
from app.database import Database
from app.llm import GroqGateway
from app.models import ServiceError
from app.whatsapp import WhatsApp


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--groq", action="store_true")
    parser.add_argument("--meta", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    db = Database(settings.db_path)
    db.init()
    print("SQLite: OK")
    print("Knowledge:", "OK" if settings.knowledge_path.is_file() else "MISSING")
    print("Missing settings:", ", ".join(settings.missing()) or "none")
    failed = bool(settings.missing()) or not settings.knowledge_path.is_file()
    if args.groq:
        groq = GroqGateway(settings, db)
        try:
            models = await groq.call("models", groq.client.models.list)
            ids = {m.id for m in models.data}
            for ident in (settings.groq_model, settings.groq_whisper_model):
                print("Model:", ident, "LISTED" if ident in ids else "NOT LISTED")
                failed |= ident not in ids
            decision = await groq.decide([{"direction": "incoming", "text": "مواعيد شغلكم ايه؟"}], settings.knowledge_path.read_text(encoding="utf-8-sig"))
            print("Groq test: OK; JSON reply received. Handoff:", decision.handoff)
        except (ServiceError, OSError) as exc:
            print("Groq test: FAILED", exc.code if isinstance(exc, ServiceError) else "knowledge_file_unavailable")
            failed = True
        finally:
            await groq.close()
    if args.meta:
        async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=False) as http:
            meta = WhatsApp(settings, http)
            try:
                result = await http.get(f"{meta.base}/{settings.meta_phone_number_id}",
                                        params={"fields": "id,display_phone_number"}, headers=meta.headers())
                meta.check(result)
                print("Meta token + Phone Number ID: OK (no message sent)")
                actual = result.headers.get("facebook-api-version")
                if actual:
                    print("Meta response API version:", actual)
                    if actual != settings.meta_graph_version:
                        print("Version differs: copy a supported version from Meta API Setup into .env.")
                        failed = True
            except ServiceError as exc:
                print("Meta test: FAILED", exc.code)
                failed = True
            except httpx.RequestError:
                print("Meta test: FAILED network_or_timeout")
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
