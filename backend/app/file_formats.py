"""Identify approved file types and prepare inert previews without external services."""

import io
import re
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .core import fail

IMAGES = {
    ".png": ("PNG", "image/png"),
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".gif": ("GIF", "image/gif"),
    ".webp": ("WEBP", "image/webp"),
}
OFFICE = {
    ".docx": ("word/document.xml", "wordprocessingml.document"),
    ".xlsx": ("xl/workbook.xml", "spreadsheetml.sheet"),
    ".pptx": ("ppt/presentation.xml", "presentationml.presentation"),
}


def safe_xml(data):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("invalid XML")
    return ElementTree.fromstring(data)


def office_preview(data, ext):
    main, subtype = OFFICE[ext]
    mime = "application/vnd.openxmlformats-officedocument." + subtype
    with ZipFile(io.BytesIO(data)) as archive:
        parts = archive.infolist()
        if (
            len(parts) > 2048
            or sum(p.file_size for p in parts) > 48 * 1024**2
            or any(
                p.file_size > 8 * 1024**2 or p.flag_bits & 1 or "vbaproject" in p.filename.lower()
                for p in parts
            )
        ):
            raise ValueError("oversized, encrypted or macro-enabled file")
        types = safe_xml(archive.read("[Content_Types].xml"))
        if not any(
            node.get("PartName") == "/" + main and node.get("ContentType") == mime + ".main+xml"
            for node in types
        ):
            raise ValueError("wrong document type")
        root = safe_xml(archive.read(main))
        names = archive.namelist()
        roots = [root]
        if ext == ".xlsx":
            for path in (
                "xl/sharedStrings.xml",
                *[n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)][:2],
            ):
                if path in names:
                    roots.append(safe_xml(archive.read(path)))
        if ext == ".pptx":
            roots += [
                safe_xml(archive.read(n))
                for n in sorted(names)
                if re.fullmatch(r"ppt/slides/slide[1-3]\.xml", n)
            ]
        words = []
        length = 0
        for tree in roots:
            for node in tree.iter():
                if node.tag.rsplit("}", 1)[-1] in {"t", "v", "sheet"}:
                    word = (node.text or node.get("name", "")).strip()
                    if word:
                        words.append(word[: 4000 - length])
                        length += len(word) + 1
                    if length >= 4000:
                        break
            if length >= 4000:
                break
        return mime, "\n".join(words) or "文件沒有可預覽的文字。"


def inspect_file(filename, data, supplied):
    if (
        not filename
        or len(filename) > 180
        or any(ord(c) < 32 or c in "/\\:" for c in filename)
        or filename.strip() in {".", ".."}
    ):
        fail(422, "INVALID_FILENAME", "檔名不可包含路徑或控制字元。")
    ext = PurePosixPath(filename).suffix.lower()
    try:
        if ext in IMAGES:
            fmt, mime = IMAGES[ext]
            with Image.open(io.BytesIO(data)) as im:
                if im.format != fmt or im.width * im.height > 20_000_000:
                    raise ValueError("invalid image")
                im.verify()
            text = ""
        elif ext == ".pdf":
            if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
                raise ValueError("invalid PDF")
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError("encrypted")
            pages = len(reader.pages)
            text = f"PDF · {pages} 頁"
            if pages:
                text += "\n" + (reader.pages[0].extract_text() or "第一頁沒有可預覽的文字。")[:4000]
            mime = "application/pdf"
        elif ext in OFFICE:
            mime, text = office_preview(data, ext)
        else:
            fail(415, "UNSUPPORTED_FILE", "可上傳 PNG、JPEG、GIF、WebP、PDF、DOCX、XLSX 或 PPTX。")
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        EOFError,
        BadZipFile,
        ElementTree.ParseError,
        UnidentifiedImageError,
        PdfReadError,
        Image.DecompressionBombError,
        RuntimeError,
        OverflowError,
    ):
        fail(415, "INVALID_FILE_CONTENT", "無法讀取此檔案，請確認格式、副檔名及內容。")
    if supplied and supplied not in {mime, "application/octet-stream"}:
        fail(415, "MIME_MISMATCH", "檔案類型與內容不一致。")
    return mime, text.replace("\x00", "")
