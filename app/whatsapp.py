import base64
import hashlib
import hmac
import re
from urllib.parse import urlsplit

import httpx

from .config import Settings, secret
from .models import ServiceError


def verify_signature(body: bytes, signature: str, app_secret: str) -> bool:
    if not app_secret or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class WhatsApp:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client
        self.base = f"https://graph.facebook.com/{settings.meta_graph_version}"

    def headers(self):
        token = secret(self.settings.meta_access_token)
        if not token:
            raise ServiceError("meta_not_configured")
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def check(response: httpx.Response):
        if not response.is_success:
            code = "unknown"
            try:
                candidate = response.json().get("error", {}).get("code")
                if isinstance(candidate, int):
                    code = str(candidate)
            except (ValueError, AttributeError, httpx.ResponseNotRead):
                pass
            raise ServiceError(f"meta_http_{response.status_code}_code_{code}")

    async def send_text(self, phone: str, text: str) -> str:
        if not self.settings.meta_phone_number_id:
            raise ServiceError("meta_not_configured")
        try:
            response = await self.client.post(
                f"{self.base}/{self.settings.meta_phone_number_id}/messages",
                headers=self.headers(),
                json={"messaging_product": "whatsapp", "recipient_type": "individual",
                      "to": phone, "type": "text", "text": {"preview_url": False, "body": text}},
            )
            self.check(response)
            return str(response.json()["messages"][0]["id"])
        except httpx.RequestError as exc:
            raise ServiceError("meta_send_uncertain") from exc
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ServiceError("meta_send_uncertain") from exc

    @staticmethod
    def safe_media_url(url: str) -> bool:
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower()
            allowed = host in {"lookaside.fbsbx.com", "graph.facebook.com"} or host.endswith(".fbcdn.net")
            return bool(allowed and parsed.scheme == "https" and parsed.port in (None, 443)
                        and not parsed.username and not parsed.password)
        except ValueError:
            return False

    async def download_audio(self, media_id: str) -> tuple[bytes, str]:
        if not re.fullmatch(r"\d{1,128}", media_id):
            raise ServiceError("audio_invalid_media_id")
        try:
            response = await self.client.get(f"{self.base}/{media_id}", headers=self.headers())
            self.check(response)
            data = response.json()
            url = data["url"]
            if not isinstance(url, str) or not self.safe_media_url(url):
                raise ServiceError("audio_untrusted_url")
            if int(data.get("file_size", 0)) > self.settings.max_audio_bytes:
                raise ServiceError("audio_too_large")
            content = bytearray()
            # Never forward a bearer token to a redirect target.
            async with self.client.stream("GET", url, headers=self.headers(), follow_redirects=False) as stream:
                self.check(stream)
                async for chunk in stream.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.settings.max_audio_bytes:
                        raise ServiceError("audio_too_large")
            if not content:
                raise ServiceError("audio_empty")
            expected = data.get("sha256")
            if expected:
                digest = hashlib.sha256(content)
                if expected not in (digest.hexdigest(), base64.b64encode(digest.digest()).decode()):
                    raise ServiceError("audio_checksum_failed")
            return bytes(content), str(data.get("mime_type", "application/octet-stream"))
        except httpx.RequestError as exc:
            raise ServiceError("audio_download_network") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceError("audio_metadata_invalid") from exc
