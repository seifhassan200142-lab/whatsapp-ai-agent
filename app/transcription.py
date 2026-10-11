from .llm import GroqGateway
from .models import ServiceError

# WhatsApp voice notes use an OGG container with Opus. Groq accepts OGG directly.
FORMATS = {"audio/ogg": "ogg", "application/ogg": "ogg", "audio/mpeg": "mp3",
           "audio/mp3": "mp3", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
           "audio/wav": "wav", "audio/x-wav": "wav", "audio/flac": "flac",
           "audio/webm": "webm"}


async def transcribe(groq: GroqGateway, content: bytes, mime: str) -> str:
    mime = mime.split(";")[0].strip().lower()
    suffix = FORMATS.get(mime)
    if not suffix:
        raise ServiceError("audio_unsupported_format")
    result = await groq.call("transcription", groq.client.audio.transcriptions.create,
                            file=(f"voice.{suffix}", content, mime),
                            model=groq.settings.groq_whisper_model,
                            response_format="json", temperature=0)
    text = getattr(result, "text", "").strip()
    if not text:
        raise ServiceError("audio_empty_transcript")
    if len(text) > 4096:
        raise ServiceError("audio_transcript_too_long")
    return text
