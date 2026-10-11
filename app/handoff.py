import logging
import re

from .database import Database
from .llm import GroqGateway
from .models import ServiceError

log = logging.getLogger("agent")


def asks_for_human(text: str) -> bool:
    text = re.sub(r"[\u064b-\u065f\u0640]", "", text.lower())
    text = text.translate(str.maketrans("أإآى", "اااي"))
    return bool(re.search(r"(?:عايز|عاوز|محتاج|اريد|ممكن).{0,30}(?:اكلم|اتكلم|اتواصل|التحدث).{0,15}(?:موظف|انسان|شخص|بشر|خدمه العملاء|خدمة العملاء)|(?:حولني|وصلني).{0,20}(?:موظف|انسان|شخص)|\b(?:talk|speak|connect|transfer).{0,25}\b(?:human|person|agent|representative)\b|^(?:human|agent|موظف)[.!؟? ]*$", text))


def handoff_notice(text: str) -> str:
    if re.search(r"[\u0600-\u06ff]", text):
        return "سجلت طلبك لمراجعة بشرية ووقفت الردود الآلية. المسؤول يقدر يشوف المحادثة ويرد عليك؛ مفيش موعد رد مؤكد حاليًا."
    return "I've marked this conversation for human review and paused automatic replies. An operator can review and reply; a response time is not confirmed."


async def escalate(db: Database, groq: GroqGateway, phone: str, history: list[dict],
                   reason: str, use_groq: bool = True):
    # Pause first, even when summary generation fails.
    fallback = "Human review required. Reason: " + reason + "\n" + "\n".join(
        f'{m["direction"]}: {m["text"][:400]}' for m in history[-4:])
    db.set_status(phone, "human_required", fallback[:2000], "fallback", reason)
    if use_groq:
        try:
            summary = await groq.summarize(history, reason)
            db.set_status(phone, "human_required", summary, "groq", reason)
        except ServiceError as exc:
            log.warning("summary_fallback code=%s", exc.code)
    log.info("human_required")
