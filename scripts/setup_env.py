"""Create a collision-resistant local project ID; never overwrite an existing .env."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
target = root / ".env"
if not target.exists():
    text = (root / ".env.example").read_text(encoding="utf-8")
    text = text.replace("buddycheck_ganti_dengan_id_kelompok", "buddycheck_" + secrets.token_hex(4))
    target.write_text(text, encoding="utf-8")
    print(".env dibuat dengan PROJECT_ID unik. Samakan ID ini di kedua HP.")
else:
    print(".env sudah ada; konfigurasi dipertahankan.")
