import re
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
text = (path if path.exists() else root / ".env.example").read_text(encoding="utf-8-sig")
for name in ("META_VERIFY_TOKEN", "ADMIN_API_KEY"):
    match = re.search(rf"^{name}=(.*)$", text, flags=re.M)
    if match and match.group(1).strip() and not match.group(1).startswith("PASTE_"):
        continue
    replacement = f"{name}={secrets.token_urlsafe(32)}"
    text = re.sub(rf"^{name}=.*$", replacement, text, flags=re.M) if match else text + "\n" + replacement + "\n"
path.write_text(text, encoding="utf-8")
print(".env is ready. Open it in VS Code and fill the four provider values. No secrets printed.")
