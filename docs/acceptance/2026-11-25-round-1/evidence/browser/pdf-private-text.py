"""Extract text from the two Chromium-rendered PDFs and verify it independently of the DOM."""
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader, __version__

directory = Path(__file__).resolve().parent
sample = json.loads((directory / "pdf-private.json").read_text(encoding="utf-8"))
result = {"engine": f"pypdf {__version__}", "exports": {}}
for mode in ("details", "brief"):
    source = directory / f"pdf-private-{mode}.pdf"
    reader = PdfReader(source)
    text = "\n".join(page.extract_text() for page in reader.pages)
    normalized = "".join(text.split())
    observed = {
        "pages": len(reader.pages),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "extractedText": text,
        "publicItemPresent": sample["expectedPublic"] in normalized,
        "addressPresent": sample["expectedAddress"] in normalized,
        "privateMarkersAbsent": {field:field not in normalized for field in sample["expectedPrivate"]},
    }
    result["exports"][mode] = observed
    assert observed["sha256"] == sample["printed"][mode]["sha256"]
    assert observed["pages"] and observed["publicItemPresent"]
    assert observed["addressPresent"] == (mode == "details")
    assert all(observed["privateMarkersAbsent"].values())
result["privateFileObject"] = "BLOCKED - no actual private file could be attached"
(directory / "pdf-private-text.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
