"""
Loaders for Kozy AI ingestion pipeline.
Source: Cloudinary URL (PDF, DOCX, PPTX, or HTML).
Output: TextDoc (with local file_path) + chunks ready for Graphiti episodes.
Pipeline: download -> save to persistent local storage -> Docling parse (+ VLM image captions) -> chunk/clean.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass
import requests
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
    PowerpointFormatOption,
    HTMLFormatOption,
)
from docling.datamodel.base_models import InputFormat, MimeTypeToFormat, FormatToExtensions
from docling.datamodel.backend_options import HTMLBackendOptions
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    ConvertPipelineOptions,
    PictureDescriptionApiOptions,
)

UA = "kozy-brain/1.0"
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/app/storage")

OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
VLM_MODEL            = os.getenv("VLM_MODEL", "qwen/qwen2.5-vl-72b-instruct")

VLM_PROMPT = (
    "Describe this image's content and its business context in 2-3 concise sentences. "
    "If it is a chart or table, state what it shows. Be factual, no speculation."
)

ALLOWED_FORMATS = [InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX, InputFormat.HTML]


def _picture_description_options() -> PictureDescriptionApiOptions:
    return PictureDescriptionApiOptions(
        url=f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        params=dict(model=VLM_MODEL),
        prompt=VLM_PROMPT,
        timeout=90,
        concurrency=3,
    )


def _build_converter() -> DocumentConverter:
    """One converter for all supported formats; each gets VLM picture captioning."""
    pdf_opts = PdfPipelineOptions()
    pdf_opts.do_ocr = True
    pdf_opts.do_table_structure = True
    pdf_opts.generate_picture_images = True  # PDF crops pictures off the rendered page
    pdf_opts.images_scale = 2.0
    pdf_opts.do_picture_description = True
    pdf_opts.enable_remote_services = True
    pdf_opts.picture_description_options = _picture_description_options()

    # DOCX/PPTX backends read embedded picture bytes directly — no extra flags needed.
    office_opts = ConvertPipelineOptions(
        do_picture_description=True,
        enable_remote_services=True,
        picture_description_options=_picture_description_options(),
    )

    html_opts = ConvertPipelineOptions(
        do_picture_description=True,
        enable_remote_services=True,
        picture_description_options=_picture_description_options(),
    )

    return DocumentConverter(
        allowed_formats=ALLOWED_FORMATS,
        format_options={
            InputFormat.PDF:  PdfFormatOption(pipeline_options=pdf_opts),
            InputFormat.DOCX: WordFormatOption(pipeline_options=office_opts),
            InputFormat.PPTX: PowerpointFormatOption(pipeline_options=office_opts),
            InputFormat.HTML: HTMLFormatOption(
                pipeline_options=html_opts,
                # HTML images are external by default -> must opt in to fetch them.
                backend_options=HTMLBackendOptions(fetch_images=True, enable_remote_fetch=True),
            ),
        },
    )


_converter = _build_converter()  # built once, reused across calls


@dataclass
class TextDoc:
    source: str
    title: str
    text: str
    file_path: str


def _clean(text: str) -> str:
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _guess_extension(url: str, content_type: str | None) -> str:
    """Best-effort filename extension. Docling content-sniffs regardless, so this
    only needs to be good enough for sensible storage filenames."""
    path = url.split("?")[0].rsplit("/", 1)[-1]
    if "." in path:
        ext = path.rsplit(".", 1)[-1].lower()
        if ext.isalnum() and 1 < len(ext) <= 5:
            return ext
    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        formats = MimeTypeToFormat.get(mime)
        if formats:
            return FormatToExtensions[formats[0]][0]
    return "bin"


def _local_storage_path(company_id: str, url: str, title: str | None, ext: str) -> str:
    company_dir = os.path.join(STORAGE_ROOT, company_id)
    os.makedirs(company_dir, exist_ok=True)
    filename = title or url.split("/")[-1].split("?")[0]
    if not filename.lower().endswith(f".{ext}"):
        filename = f"{filename}.{ext}"
    return os.path.join(company_dir, filename)


def load_cloudinary_file(url: str, company_id: str, title: str | None = None) -> TextDoc | None:
    """Download + parse a Cloudinary file (PDF, DOCX, PPTX, or HTML) into a TextDoc."""
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [skip] download failed {url}: {e}")
        return None

    ext = _guess_extension(url, resp.headers.get("Content-Type"))
    file_path = _local_storage_path(company_id, url, title, ext)
    try:
        with open(file_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        print(f"  [skip] failed to save file {file_path}: {e}")
        return None

    try:
        result = _converter.convert(file_path)
        text = _clean(result.document.export_to_markdown(image_placeholder=""))
    except Exception as e:
        print(f"  [skip] Docling parse failed {file_path}: {e}")
        return None

    if not text:
        print(f"  [skip] empty text after parse: {file_path}")
        return None

    doc_title = title or os.path.splitext(os.path.basename(file_path))[0]
    return TextDoc(source=url, title=doc_title, text=text, file_path=file_path)
