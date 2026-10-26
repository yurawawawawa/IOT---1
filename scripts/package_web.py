"""Create a static-hosting ZIP containing only public web assets and licenses."""
from pathlib import Path
from shutil import copyfile, make_archive

root = Path(__file__).resolve().parent.parent
(root / "dist").mkdir(exist_ok=True)
for document in ("LICENSE", "NOTICE.md"):
    copyfile(root / document, root / "web" / document)
archive = make_archive(str(root / "dist" / "buddycheck-web"), "zip", root_dir=root / "web")
print(f"Paket hosting: {archive}")
print("Isi paket hanya folder web; tidak menyertakan .env atau kredensial laptop.")
