"""Package only the verified HTML, the portable matrix, and evidence, excluding the archive itself."""
import hashlib,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[2]
entries=sorted(p for p in root.rglob("*") if p.is_file() and p.suffix not in [".zip",".pyc"] and "__pycache__" not in p.parts and p.name!="checksums.sha256")
manifest=root/"evidence/system/checksums.sha256"
manifest.write_text("\n".join(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+p.relative_to(root).as_posix() for p in entries)+"\n",encoding="utf8")
out=root/"WayToGo-驗收證據.zip"
with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in entries+[manifest]:z.write(p,p.relative_to(root).as_posix())
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(entries)+1
    assert all(z.read(p.relative_to(root).as_posix())==p.read_bytes() for p in entries+[manifest])
print(len(entries)+1,"files,",out.stat().st_size,"bytes")
