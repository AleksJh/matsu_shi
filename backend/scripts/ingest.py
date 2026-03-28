"""PDF Ingestion Pipeline — CLI Entry Point.

Usage (from backend/ directory):
    python scripts/ingest.py --path ./manual.pdf --machine-model "PC300-8"
    python scripts/ingest.py --dir ./manuals/ --category hydraulics
    python scripts/ingest.py --path ./manual.pdf --machine-model "PC300-8" --dry-run

Checkpointing flags (Phase 8.7):
    --stop-after {parse,chunk,enrich,embed}   save artifact and stop after this stage
    --start-from {chunk,enrich,embed,write}   load artifact and resume from this stage
    --save-artifacts                           save all intermediate artifacts (full run)
    --artifact-dir DIR                         artifact cache directory (default: ./cache)

Artifacts are stored as JSON in:
    {artifact_dir}/{sha256_checksum}/{parse,visual,chunks,enriched,embedded}.json
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import io
import json
import re
import sys
import time
from dataclasses import dataclass, replace as dc_replace
from pathlib import Path

# Load .env from project root BEFORE importing app modules (settings reads from os.environ)
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import tiktoken  # noqa: E402
import boto3  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
from docling.datamodel.base_models import InputFormat  # noqa: E402
from docling.datamodel.pipeline_options import PdfPipelineOptions  # noqa: E402
from docling.document_converter import DocumentConverter, PdfFormatOption  # noqa: E402
from google import genai  # noqa: E402
from loguru import logger  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.chunk import Chunk  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.rag.embedder import embed_text  # noqa: E402

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    """Result of parsing a PDF file via Docling."""

    markdown: str
    page_count: int
    figure_pages: list[dict]  # [{page_number: int, bbox: dict | None}, ...]
    checksum: str
    doc_name: str          # path.stem — used as display_name in documents table
    original_filename: str  # path.name — maps to original_filename column (NOT NULL)


@dataclass
class VisualTag:
    """Visual metadata for a single figure page, produced by step_visual_ingest."""

    page_number: int   # 1-indexed; matches figure_pages[n]["page_number"]
    r2_url: str        # public URL of the WebP in Cloudflare R2
    description: str   # one-line Russian description from Gemini Vision


@dataclass
class ChunkData:
    """In-memory chunk before DB write (PRD §4.3)."""

    chunk_index: int
    content: str                      # raw text (pre-enrichment)
    chunk_type: str                   # "text" | "table" | "visual_caption"
    section_title: str | None         # last seen H1-H4 heading
    page_number: int | None           # best-guess page (from heading context or figure_pages)
    visual_refs: list[str]            # filled in step_enrich (Rule 3)
    token_count: int
    # set at step_write time (carried from CLI args):
    doc_name: str
    machine_model: str
    category: str | None
    vector: list[float] | None = None  # populated by step_embed


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


async def step_parse(
    pdf_path: Path,
    machine_model: str,
    rebuild_index: bool,
    dry_run: bool = False,
) -> ParseResult | None:
    """Step 1: Parse PDF with Docling → markdown + page metadata.

    Returns ParseResult, or None if the file is skipped (checksum already exists).
    """
    logger.info(f"[1/6] Парсинг: {pdf_path.name} ...")

    # 1. Compute SHA-256 checksum
    pdf_bytes = pdf_path.read_bytes()
    checksum = hashlib.sha256(pdf_bytes).hexdigest()

    # 2. Duplicate check — skip if already indexed (unless rebuild or dry_run)
    if dry_run:
        logger.info("dry-run: пропуск проверки checksum")
    elif not rebuild_index:
        async with AsyncSessionLocal() as session:
            existing = await session.scalar(
                select(Document).where(Document.checksum == checksum)
            )
            if existing:
                logger.info(
                    f"Пропуск: {pdf_path.name} уже проиндексирован (checksum совпадает)"
                )
                return None

    # 3. Docling parse in 60-page chunks to avoid pypdfium2 heap corruption.
    # Large PDFs cause std::bad_alloc errors on many pages; after ~100 accumulated
    # failures the C++ heap corrupts and segfaults. Each 60-page temp PDF starts a
    # fresh pypdfium2 document context, so at most a handful of bad_allocs accumulate
    # before the context is discarded — well within docling's graceful-recovery limit.
    # OCR is also disabled: manuals have embedded text layers and OCR is not needed.
    _CHUNK_SIZE = 60
    _pdf_opts = PdfPipelineOptions(do_ocr=False)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=_pdf_opts)}
    )

    from pypdf import PdfReader, PdfWriter  # noqa: E402
    import tempfile  # noqa: E402

    _reader = PdfReader(str(pdf_path))
    _total_pages = len(_reader.pages)
    _chunk_starts = list(range(0, _total_pages, _CHUNK_SIZE))

    _markdown_parts: list[str] = []
    figure_pages: list[dict] = []

    with tempfile.TemporaryDirectory() as _tmpdir:
        for _ci, _cs in enumerate(_chunk_starts):
            _ce = min(_cs + _CHUNK_SIZE, _total_pages)
            logger.info(
                f"[1/6] Чанк {_ci + 1}/{len(_chunk_starts)}: "
                f"страницы {_cs + 1}–{_ce} из {_total_pages} ..."
            )
            _writer = PdfWriter()
            for _pg in _reader.pages[_cs:_ce]:
                _writer.add_page(_pg)
            _chunk_path = Path(_tmpdir) / f"chunk_{_ci:04d}.pdf"
            with open(_chunk_path, "wb") as _f:
                _writer.write(_f)

            _chunk_result = converter.convert(str(_chunk_path))

            _markdown_parts.append(_chunk_result.document.export_to_markdown())

            for pic in _chunk_result.document.pictures:
                if pic.prov:
                    prov = pic.prov[0]
                    bbox = (
                        {"l": prov.bbox.l, "t": prov.bbox.t, "r": prov.bbox.r, "b": prov.bbox.b}
                        if prov.bbox
                        else None
                    )
                    # prov.page_no is 1-based within the chunk; map to absolute page number
                    figure_pages.append({"page_number": _cs + prov.page_no, "bbox": bbox})

    # 4. Combine markdown from all chunks
    markdown = "\n\n".join(_markdown_parts)

    page_count = _total_pages
    logger.success(
        f"[1/6] Парсинг завершён: {pdf_path.name} — {page_count} стр., "
        f"{len(figure_pages)} рисунков, {len(markdown)} символов Markdown"
    )

    return ParseResult(
        markdown=markdown,
        page_count=page_count,
        figure_pages=figure_pages,
        checksum=checksum,
        doc_name=pdf_path.stem,
        original_filename=pdf_path.name,
    )


async def step_visual_ingest(
    pdf_path: Path,
    parse_result: ParseResult,
    machine_model: str,
    dry_run: bool,
    partial_path: Path | None = None,
) -> list[VisualTag]:
    """Step 2: Render diagram pages → WebP → Cloudflare R2 → Gemini description.

    For each page in parse_result.figure_pages:
      1. Render page to WebP at DPI=150 via pypdfium2
      2. Upload WebP to Cloudflare R2: {machine_model}/{doc_name}/page_{n}.webp
      3. Send WebP to Gemini vision (LLM_ADVANCED_MODEL) with Russian prompt
      4. Store VisualTag(page_number, r2_url, description)

    Per-page errors are non-fatal: logged as WARNING, processing continues.
    Runs in parallel with step_chunk via asyncio.TaskGroup.

    If partial_path is provided, progress is saved after every page so the step
    can be resumed after a crash or API limit without repeating paid API calls.
    On resume, already-processed pages are skipped automatically.
    """
    figure_pages = parse_result.figure_pages
    logger.info(f"[2/6] Visual ingest: {len(figure_pages)} figure pages found")

    visual_tags: list[VisualTag] = []

    if not figure_pages:
        logger.success("[2/6] Visual ingest complete: 0 images uploaded")
        return visual_tags

    # dry-run: log intent, skip all IO
    if dry_run:
        for fig in figure_pages:
            logger.info(f"dry-run: would upload page_{fig['page_number']}.webp to R2")
        logger.success("[2/6] Visual ingest complete: 0 images uploaded (dry-run)")
        return visual_tags

    # Resume from partial progress if available
    done_pages: set[int] = set()
    if partial_path is not None and partial_path.exists():
        try:
            raw = json.loads(partial_path.read_text(encoding="utf-8"))
            visual_tags = [VisualTag(**item) for item in raw]
            done_pages = {t.page_number for t in visual_tags}
            logger.info(f"[2/6] Resuming visual ingest: {len(done_pages)} pages already done, skipping")
        except Exception as exc:
            logger.warning(f"[2/6] Не удалось загрузить partial progress ({exc}), начинаем с нуля")
            visual_tags = []
            done_pages = set()

    # Set up clients once for the entire document
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.CF_R2_ENDPOINT,
        aws_access_key_id=settings.CF_R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.CF_R2_SECRET_ACCESS_KEY,
    )
    gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    pdf = pdfium.PdfDocument(str(pdf_path))

    seen_pages: set[int] = set(done_pages)
    try:
        for fig in figure_pages:
            page_number: int = fig["page_number"]
            if page_number in seen_pages:
                continue
            seen_pages.add(page_number)
            try:
                # 1. Render page to WebP (DPI=150; pypdfium2 base is 72 DPI)
                page = pdf[page_number - 1]  # 0-indexed
                bitmap = page.render(scale=150 / 72)
                pil_image = bitmap.to_pil()
                buf = io.BytesIO()
                pil_image.save(buf, format="webp")
                webp_bytes = buf.getvalue()

                # 2. Upload to Cloudflare R2
                key = f"{machine_model}/{parse_result.doc_name}/page_{page_number}.webp"
                s3.put_object(
                    Bucket=settings.CF_R2_BUCKET,
                    Key=key,
                    Body=webp_bytes,
                    ContentType="image/webp",
                )
                r2_url = f"{settings.CF_R2_PUBLIC_BASE_URL}/{key}"
                logger.debug(f"  Uploaded page_{page_number}.webp → {r2_url}")

                # 3. Describe via Gemini Vision (retry up to 3x on 503)
                img = Image.open(io.BytesIO(webp_bytes))
                description = ""
                for _attempt in range(20):
                    try:
                        response = gemini_client.models.generate_content(
                            model=settings.LLM_ADVANCED_MODEL,
                            contents=[  # type: ignore[arg-type]  # PIL.Image accepted at runtime
                                "Опиши техническую схему: компоненты, стрелки, метки. "
                                "Одна строка технического описания на русском.",
                                img,
                            ],
                        )
                        description = (response.text or "").strip()
                        break
                    except Exception as _exc:
                        if _attempt < 19 and "503" in str(_exc):
                            _wait = 2
                            logger.warning(
                                f"  Gemini 503 на странице {page_number}, "
                                f"попытка {_attempt + 1}/20, ждём {_wait}s ..."
                            )
                            await asyncio.sleep(_wait)
                        else:
                            raise
                logger.info(f"  page_{page_number}: {description}")

                visual_tags.append(
                    VisualTag(page_number=page_number, r2_url=r2_url, description=description)
                )

                # Save incremental progress after each successful page
                if partial_path is not None:
                    partial_path.write_text(
                        json.dumps(
                            [dataclasses.asdict(t) for t in visual_tags],
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

            except Exception as exc:
                logger.warning(f"Visual ingest failed for page {page_number}: {exc}")
                # Non-fatal: continue processing remaining pages
            finally:
                pass  # No throttle needed; retry logic handles 503s
    finally:
        pdf.close()

    # Clean up partial file on successful completion
    if partial_path is not None and partial_path.exists():
        partial_path.unlink()
        logger.debug(f"  Partial progress file removed: {partial_path}")

    logger.success(f"[2/6] Visual ingest complete: {len(visual_tags)} images uploaded")
    return visual_tags


# ---------------------------------------------------------------------------
# Token counting + overlap helpers (Rule 4)
# ---------------------------------------------------------------------------

_enc = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding (tiktoken)."""
    return len(_enc.encode(text))


def _apply_overlap(
    chunks: list[ChunkData], overlap_ratio: float = 0.10
) -> list[ChunkData]:
    """Rule 4: prepend tail of previous text chunk to current text chunk (10% token overlap).

    Only applied to adjacent text↔text pairs; table and visual_caption chunks are skipped.
    """
    result: list[ChunkData] = []
    for i, chunk in enumerate(chunks):
        if chunk.chunk_type == "text" and i > 0:
            prev = chunks[i - 1]
            if prev.chunk_type == "text":
                overlap_tokens = max(1, int(prev.token_count * overlap_ratio))
                words = prev.content.split()
                overlap_text = " ".join(words[-overlap_tokens:])
                chunk = dc_replace(chunk, content=overlap_text + "\n" + chunk.content)
        result.append(chunk)
    return result


def _merge_small_chunks(chunks: list[ChunkData], min_tokens: int) -> list[ChunkData]:
    """Merge text chunks smaller than min_tokens into the preceding text chunk.

    Deep subsections (e.g. 3.15.4.5) often produce very short chunks that embed
    poorly and add retrieval noise.  This post-processing step absorbs them into
    the parent/sibling text chunk that immediately precedes them.

    Rules:
    - Only text-type chunks are merged; tables and visual_captions are never touched.
    - A tiny chunk with no preceding text chunk (e.g. very first chunk) is kept as-is.
    - After merging, chunk_index values are resequenced 0..N-1.
    """
    merged: list[ChunkData] = []
    for chunk in chunks:
        if (
            chunk.chunk_type == "text"
            and chunk.token_count < min_tokens
            and merged
            and merged[-1].chunk_type == "text"
        ):
            prev = merged[-1]
            new_content = prev.content + "\n\n" + chunk.content
            merged[-1] = dc_replace(
                prev,
                content=new_content,
                token_count=_count_tokens(new_content),
                # Keep prev's section_title (parent heading) and page_number
            )
        else:
            merged.append(chunk)

    # Reindex sequentially after merges
    return [dc_replace(c, chunk_index=i) for i, c in enumerate(merged)]


# ---------------------------------------------------------------------------
# Phase 8.7 — Artifact helpers (checkpoint system)
# ---------------------------------------------------------------------------


def _compute_checksum(pdf_path: Path) -> str:
    """Compute SHA-256 checksum of a PDF file without running Docling.

    Called once at the start of main() to locate the artifact cache directory.
    Separate from step_parse() so checksum is available even when --start-from
    skips the parse step entirely.
    """
    return hashlib.sha256(pdf_path.read_bytes()).hexdigest()


def _save_artifact(
    artifact_dir: Path,
    checksum: str,
    stage: str,
    data: object,
) -> None:
    """Serialize a dataclass or list[dataclass] to JSON and write to disk.

    File location: {artifact_dir}/{checksum}/{stage}.json
    Directory is created automatically if it does not exist.
    """
    dest = artifact_dir / checksum
    dest.mkdir(parents=True, exist_ok=True)
    if isinstance(data, list):
        payload = [dataclasses.asdict(item) for item in data]
    else:
        payload = dataclasses.asdict(data)  # type: ignore[arg-type]
    (dest / f"{stage}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Артефакт сохранён: {dest / stage}.json")


def _load_artifact(
    artifact_dir: Path,
    checksum: str,
    stage: str,
    cls: type,
) -> object:
    """Load a previously saved artifact from disk and reconstruct dataclass(es).

    If the file does not exist, raises FileNotFoundError with a clear message
    directing the user to re-run from an earlier stage.
    """
    path = artifact_dir / checksum / f"{stage}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Артефакт не найден: {path}. "
            f"Запустите pipeline с начала или с более раннего шага."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [cls(**item) for item in raw]
    return cls(**raw)


# ---------------------------------------------------------------------------
# Step 3: Chunking
# ---------------------------------------------------------------------------


async def step_chunk(
    parse_result: ParseResult,
    machine_model: str,
    category: str | None,
    dry_run: bool,
) -> list[ChunkData]:
    """Step 3: Hybrid structural + semantic chunking (4 rules from PRD §4.2).

    Rule 1 — H1-H4 headings as chunk boundaries; procedural steps not split.
    Rule 2 — Each Markdown table → isolated chunk of type 'table'.
    Rule 3 — visual_refs left empty here; filled by step_enrich (task 2.5).
    Rule 4 — 10% token overlap between adjacent text chunks.

    Runs in parallel with step_visual_ingest via asyncio.TaskGroup.
    visual_tags are applied post-chunking in step_enrich to preserve parallel execution.
    """
    logger.info("[3/6] Чанкинг: структурное и семантическое разбиение по правилам §4.2")

    chunks: list[ChunkData] = []
    lines = parse_result.markdown.splitlines(keepends=True)
    buf: list[str] = []
    current_section: str | None = None
    chunk_index = 0

    def _flush_text_buf() -> None:
        nonlocal chunk_index
        text = "".join(buf).strip()
        if not text:
            buf.clear()
            return
        chunks.append(
            ChunkData(
                chunk_index=chunk_index,
                content=text,
                chunk_type="text",
                section_title=current_section,
                page_number=None,
                visual_refs=[],
                token_count=_count_tokens(text),
                doc_name=parse_result.doc_name,
                machine_model=machine_model,
                category=category,
            )
        )
        chunk_index += 1
        buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Rule 1 — Heading boundary (H1–H4)
        if re.match(r"^#{1,4}\s", line):
            _flush_text_buf()
            current_section = line.lstrip("#").strip()
            buf.append(line)
            i += 1
            continue

        # Rule 2 — Table detection: current line starts with '|' AND next line is separator
        if (
            line.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|[-:| ]+\|", lines[i + 1])
        ):
            _flush_text_buf()
            table_lines: list[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            table_text = "".join(table_lines).strip()
            chunks.append(
                ChunkData(
                    chunk_index=chunk_index,
                    content=table_text,
                    chunk_type="table",
                    section_title=current_section,
                    page_number=None,
                    visual_refs=[],
                    token_count=_count_tokens(table_text),
                    doc_name=parse_result.doc_name,
                    machine_model=machine_model,
                    category=category,
                )
            )
            chunk_index += 1
            continue

        buf.append(line)
        i += 1

    _flush_text_buf()  # flush remaining buffer

    # Post-processing: merge tiny text chunks into the preceding text chunk before overlap
    chunks = _merge_small_chunks(chunks, settings.CHUNK_MIN_TOKENS)

    # Rule 4 — apply 10% overlap to adjacent text chunks
    chunks = _apply_overlap(chunks)

    n_text = sum(1 for c in chunks if c.chunk_type == "text")
    n_table = sum(1 for c in chunks if c.chunk_type == "table")
    logger.success(
        f"[3/6] Чанкинг завершён: {len(chunks)} чанков "
        f"({n_text} text, {n_table} table)"
    )
    return chunks


async def step_enrich(
    chunks: list[ChunkData],
    doc_name: str,
    machine_model: str,
    visual_tags: list[VisualTag],
    dry_run: bool = False,
    artifact_dir: Path | None = None,
    checksum: str | None = None,
) -> list[ChunkData]:
    """Step 4: Contextual enrichment — Rule 3 + Gemini prepend (PRD §4.1, §4.2 Rule 3).

    1. Rule 3: attach visual_refs to text chunks referencing Figure/Рис./Схема N;
       create visual_caption chunks from VisualTag descriptions.
    2. Gemini enrichment for text + visual_caption: prepend "[Контекст: {summary}]".
    3. Gemini context header for table chunks (no [Контекст:] wrapper).
    dry_run=True skips all Gemini calls; Rule 3 always runs (no IO).
    """
    logger.info(
        f"[4/6] Контекстуальное обогащение: {len(chunks)} чанков, "
        f"{len(visual_tags)} visual tags"
    )

    # Step 1: Build page_number → VisualTag lookup
    tag_by_page: dict[int, VisualTag] = {vt.page_number: vt for vt in visual_tags}
    _fig_pattern = re.compile(r"(?:Figure|Рис\.|Схема)\s+(\d+)", re.IGNORECASE)

    # Step 2: Apply Rule 3 — attach visual_refs to text chunks
    result_chunks: list[ChunkData] = []
    for chunk in chunks:
        if chunk.chunk_type == "text":
            matches = _fig_pattern.findall(chunk.content)
            refs: list[str] = []
            for m in matches:
                page = int(m)
                if page in tag_by_page:
                    refs.append(tag_by_page[page].r2_url)
            if refs:
                chunk = dc_replace(chunk, visual_refs=refs)
        result_chunks.append(chunk)

    # Step 3: Create visual_caption chunks for ALL VisualTags
    for vc_index, vt in enumerate(visual_tags):
        result_chunks.append(
            ChunkData(
                chunk_index=len(result_chunks) + vc_index,
                content=vt.description,
                chunk_type="visual_caption",
                section_title=None,
                page_number=vt.page_number,
                visual_refs=[vt.r2_url],
                token_count=_count_tokens(vt.description),
                doc_name=doc_name,
                machine_model=machine_model,
                category=chunks[0].category if chunks else None,
            )
        )

    # Step 4: Gemini enrichment (skipped in dry_run)
    if not dry_run:
        gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        total = len(result_chunks)
        partial_path = (artifact_dir / checksum / "enriched_partial.json") if artifact_dir and checksum else None

        # Resume from partial checkpoint if available
        start_i = 0
        if partial_path and partial_path.exists():
            raw = json.loads(partial_path.read_text(encoding="utf-8"))
            for j, saved in enumerate(raw):
                if j < len(result_chunks):
                    result_chunks[j] = ChunkData(**saved)
            start_i = len(raw)
            logger.info(f"[4/6] Resuming enrich from chunk {start_i}/{total}")

        for i in range(start_i, total):
            chunk = result_chunks[i]
            logger.debug(
                f"  enrich chunk {i}/{total}: [{chunk.chunk_type}] {chunk.section_title}"
            )
            try:
                if chunk.chunk_type in ("text", "visual_caption"):
                    prompt = (
                        f"Напиши одно предложение, описывающее содержание этого фрагмента "
                        f"в контексте документа '{doc_name}' модели '{machine_model}'.\n\n"
                        f"{chunk.content}"
                    )
                    for _attempt in range(20):
                        try:
                            response = gemini_client.models.generate_content(
                                model=settings.LLM_LITE_MODEL,
                                contents=[prompt],
                            )
                            summary = (response.text or "").strip()
                            break
                        except Exception as _exc:
                            if _attempt < 19 and "503" in str(_exc):
                                logger.warning(
                                    f"  Gemini 503 на чанке {i}, "
                                    f"попытка {_attempt + 1}/20, ждём 2s ..."
                                )
                                await asyncio.sleep(2)
                            else:
                                raise
                    if summary:
                        result_chunks[i] = dc_replace(
                            chunk,
                            content=f"[Контекст: {summary}]\n\n{chunk.content}",
                        )
                elif chunk.chunk_type == "table":
                    section_ctx = f"Раздел: {chunk.section_title}. " if chunk.section_title else ""
                    page_ctx = f"Страница {chunk.page_number}. " if chunk.page_number else ""
                    prompt = (
                        f"Техника: {machine_model}. {section_ctx}{page_ctx}\n\n"
                        f"Опиши в 1-2 предложениях на русском языке: что содержит следующая "
                        f"таблица и в какой ситуации механик её использует.\n\n"
                        f"{chunk.content}"
                    )
                    for _attempt in range(20):
                        try:
                            response = gemini_client.models.generate_content(
                                model=settings.LLM_LITE_MODEL,
                                contents=[prompt],
                            )
                            header = (response.text or "").strip()
                            break
                        except Exception as _exc:
                            if _attempt < 19 and "503" in str(_exc):
                                logger.warning(
                                    f"  Gemini 503 на чанке {i}, "
                                    f"попытка {_attempt + 1}/20, ждём 2s ..."
                                )
                                await asyncio.sleep(2)
                            else:
                                raise
                    if header:
                        result_chunks[i] = dc_replace(
                            chunk,
                            content=f"[Таблица: {header}]\n\n{chunk.content}",
                        )
            except Exception as exc:
                logger.warning(f"enrich failed for chunk {i}: {exc}")

            # Save partial checkpoint every 10 chunks
            if partial_path and (i + 1) % 10 == 0:
                _save_artifact(artifact_dir, checksum, "enriched_partial", result_chunks[: i + 1])

        # Clean up partial checkpoint on successful completion
        if partial_path and partial_path.exists():
            partial_path.unlink()

    # Step 5: Reindex chunk_index 0..N-1
    result_chunks = [
        dc_replace(c, chunk_index=idx) for idx, c in enumerate(result_chunks)
    ]

    n_text = sum(1 for c in result_chunks if c.chunk_type == "text")
    n_table = sum(1 for c in result_chunks if c.chunk_type == "table")
    n_vc = sum(1 for c in result_chunks if c.chunk_type == "visual_caption")
    logger.success(
        f"[4/6] Обогащение завершено: {n_text} text, {n_table} table, {n_vc} visual_caption"
    )
    return result_chunks


async def step_embed(chunks: list[ChunkData], dry_run: bool = False) -> list[ChunkData]:
    """Step 5: Embed enriched chunks via OpenRouter (qwen3-embedding-4b).

    For each chunk: call OpenRouter-compatible embeddings API and store the
    float vector in ChunkData.vector.

    Validation: the dimension of the first successful response is checked
    against settings.EMBED_DIM — sys.exit(1) on mismatch.

    Per-chunk API errors are non-fatal: vector stays None, processing continues.
    dry_run=True skips all API calls (vectors remain None).

    Embedding is delegated to app.rag.embedder.embed_text().
    Dimension validation remains here (caller's responsibility per contract).
    """
    logger.info(
        f"[5/6] Эмбеддинг: модель={settings.EMBED_MODEL}, "
        f"dim={settings.EMBED_DIM}, чанков={len(chunks)}"
    )

    if dry_run:
        logger.info("dry-run: пропуск вызовов эмбеддинг API")
        return chunks

    dimension_validated = False
    result: list[ChunkData] = []

    for i, chunk in enumerate(chunks):
        vector = await embed_text(chunk.content)

        if vector is None:
            result.append(chunk)  # vector stays None
            continue

        # Validate dimension on first successful response
        if not dimension_validated:
            actual_dim = len(vector)
            if actual_dim != settings.EMBED_DIM:
                logger.error(
                    f"Несоответствие размерности эмбеддинга: "
                    f"получено {actual_dim}, ожидалось {settings.EMBED_DIM} "
                    f"(EMBED_DIM в .env). Обновите EMBED_DIM и повторите."
                )
                sys.exit(1)
            dimension_validated = True

        result.append(dc_replace(chunk, vector=vector))
        logger.debug(f"  chunk {i}: embedded ({len(vector)} dims)")

    n_ok = sum(1 for c in result if c.vector is not None)
    n_fail = len(result) - n_ok
    logger.success(
        f"[5/6] Эмбеддинг завершён: {n_ok} чанков, "
        f"{n_fail} ошибок (vector=None)"
    )
    return result


async def step_write(
    chunks: list[ChunkData],
    parse_result: ParseResult,
    machine_model: str,
    category: str | None,
    rebuild_index: bool,
    session: AsyncSession,
) -> None:
    """Step 6: Upsert document record + batch-insert chunk rows into PostgreSQL.

    1. Upsert the document row (conflict target: checksum) and retrieve doc_id.
    2. If rebuild_index: delete existing chunks for this document first.
    3. Batch-insert all chunks with their embedding vectors.
    """
    # --- Step 1: Upsert document ---
    stmt = (
        pg_insert(Document)
        .values(
            original_filename=parse_result.original_filename,
            display_name=parse_result.doc_name,
            machine_model=machine_model,
            category=category,
            page_count=parse_result.page_count,
            chunk_count=len(chunks),
            status="indexed",
            checksum=parse_result.checksum,
        )
        .on_conflict_do_update(
            index_elements=["checksum"],
            set_=dict(
                display_name=parse_result.doc_name,
                chunk_count=len(chunks),
                status="indexed",
            ),
        )
        .returning(Document.id)
    )
    result = await session.execute(stmt)
    doc_id: int = result.scalar_one()

    # --- Step 2: Rebuild index (delete existing chunks) ---
    if rebuild_index:
        await session.execute(delete(Chunk).where(Chunk.document_id == doc_id))

    # --- Step 3: Batch-insert chunks ---
    chunk_objects = [
        Chunk(
            document_id=doc_id,
            chunk_index=c.chunk_index,
            content=c.content,
            chunk_type=c.chunk_type,
            section_title=c.section_title,
            page_number=c.page_number,
            machine_model=c.machine_model,
            visual_refs=c.visual_refs or [],
            embedding=c.vector,
            token_count=c.token_count,
        )
        for c in chunks
    ]
    session.add_all(chunk_objects)
    await session.commit()

    logger.info(
        f"[6/6] Запись в БД: {len(chunks)} чанков, "
        f"документ={parse_result.doc_name}, doc_id={doc_id}"
    )


# ---------------------------------------------------------------------------
# Interactive helper for --dir mode
# ---------------------------------------------------------------------------


def _prompt_machine_model(filename: str) -> str:
    """Prompt user interactively for machine_model in --dir mode.

    Loops until a non-empty string is entered.
    """
    while True:
        print(f"\nФайл: {filename}")
        value = input("Введите machine model (например, PC300-8): ").strip()
        if value:
            return value
        print("Ошибка: machine model не может быть пустым. Повторите ввод.")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def _run_one_pdf(
    pdf_path: Path,
    machine_model: str,
    args: argparse.Namespace,
    artifact_dir: Path,
) -> tuple[int, int, bool]:
    """Run the ingestion pipeline for a single PDF, respecting checkpoint flags.

    Returns (n_chunks, n_images, was_skipped).
    """
    start_from: str | None = getattr(args, "start_from", None)
    stop_after: str | None = getattr(args, "stop_after", None)
    save_artifacts: bool = getattr(args, "save_artifacts", False)

    # Always compute checksum — fast (just hashing), no Docling needed.
    checksum = _compute_checksum(pdf_path)

    parse_result: ParseResult | None = None
    visual_tags: list[VisualTag] = []
    chunks: list[ChunkData] = []

    # ------------------------------------------------------------------ #
    # Determine entry point: default (full run) vs. start_from (resume)   #
    # ------------------------------------------------------------------ #

    if start_from is None:
        # --- Full pipeline from Step 1 ---

        # Step 1: Parse
        parse_result = await step_parse(
            pdf_path, machine_model, args.rebuild_index, dry_run=args.dry_run
        )
        if parse_result is None:
            return 0, 0, True  # skipped (duplicate checksum)

        if save_artifacts or stop_after == "parse":
            _save_artifact(artifact_dir, checksum, "parse", parse_result)
        if stop_after == "parse":
            logger.success(f"Остановка после шага parse. Артефакт: {artifact_dir}/{checksum}/parse.json")
            return 0, 0, False

        # Steps 2 & 3: Run in parallel
        async with asyncio.TaskGroup() as tg:
            visual_task = tg.create_task(
                step_visual_ingest(
                    pdf_path, parse_result, machine_model, args.dry_run,
                    partial_path=artifact_dir / checksum / "visual_partial.json",
                )
            )
            chunk_task = tg.create_task(
                step_chunk(parse_result, machine_model, args.category, args.dry_run)
            )
        visual_tags = visual_task.result()
        chunks = chunk_task.result()

        if save_artifacts or stop_after == "chunk":
            _save_artifact(artifact_dir, checksum, "visual", visual_tags)
            _save_artifact(artifact_dir, checksum, "chunks", chunks)
        if stop_after == "chunk":
            logger.success(f"Остановка после шага chunk. Артефакты: {artifact_dir}/{checksum}/")
            return len(chunks), len(visual_tags), False

    elif start_from == "chunk":
        # Load parse from cache; load visual from cache if available, otherwise run it now.
        logger.info(f"[checkpoint] Загрузка parse из {artifact_dir}/{checksum}/")
        parse_result = _load_artifact(artifact_dir, checksum, "parse", ParseResult)  # type: ignore[assignment]
        visual_path = artifact_dir / checksum / "visual.json"
        if visual_path.exists():
            visual_tags = _load_artifact(artifact_dir, checksum, "visual", VisualTag)  # type: ignore[assignment]
        else:
            logger.info("[checkpoint] visual.json не найден — запуск step_visual_ingest")
            visual_tags = await step_visual_ingest(
                pdf_path, parse_result, machine_model, args.dry_run,
                partial_path=artifact_dir / checksum / "visual_partial.json",
            )
            if save_artifacts:
                _save_artifact(artifact_dir, checksum, "visual", visual_tags)
        chunks = await step_chunk(parse_result, machine_model, args.category, args.dry_run)

        if save_artifacts or stop_after == "chunk":
            _save_artifact(artifact_dir, checksum, "chunks", chunks)
        if stop_after == "chunk":
            logger.success(f"Остановка после шага chunk. Артефакт: {artifact_dir}/{checksum}/chunks.json")
            return len(chunks), len(visual_tags), False

    elif start_from in ("enrich", "embed", "write"):
        # Load parse + visual for metadata; actual chunk data comes from stage-specific artifact
        logger.info(f"[checkpoint] Загрузка артефактов из {artifact_dir}/{checksum}/")
        parse_result = _load_artifact(artifact_dir, checksum, "parse", ParseResult)  # type: ignore[assignment]
        visual_tags = _load_artifact(artifact_dir, checksum, "visual", VisualTag)  # type: ignore[assignment]

    else:
        logger.error(f"Неизвестный --start-from: {start_from}")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step 4: Contextual enrichment                                        #
    # ------------------------------------------------------------------ #
    doc_name: str = parse_result.doc_name  # type: ignore[union-attr]

    if start_from not in ("embed", "write"):
        if start_from == "enrich":
            chunks = _load_artifact(artifact_dir, checksum, "chunks", ChunkData)  # type: ignore[assignment]
        chunks = await step_enrich(
            chunks, doc_name, machine_model, visual_tags, dry_run=args.dry_run,
            artifact_dir=artifact_dir, checksum=checksum,
        )
        if save_artifacts or stop_after == "enrich":
            _save_artifact(artifact_dir, checksum, "enriched", chunks)
        if stop_after == "enrich":
            logger.success(f"Остановка после шага enrich. Артефакт: {artifact_dir}/{checksum}/enriched.json")
            return len(chunks), len(visual_tags), False
    else:
        # Reload enriched or embedded artifact
        artifact_stage = "enriched" if start_from == "embed" else "embedded"
        chunks = _load_artifact(artifact_dir, checksum, artifact_stage, ChunkData)  # type: ignore[assignment]

    # ------------------------------------------------------------------ #
    # Step 5: Embedding                                                    #
    # ------------------------------------------------------------------ #

    if start_from != "write":
        chunks = await step_embed(chunks, dry_run=args.dry_run)
        if save_artifacts or stop_after == "embed":
            _save_artifact(artifact_dir, checksum, "embedded", chunks)
        if stop_after == "embed":
            logger.success(f"Остановка после шага embed. Артефакт: {artifact_dir}/{checksum}/embedded.json")
            return len(chunks), len(visual_tags), False

    # ------------------------------------------------------------------ #
    # Step 6: Remote write                                                 #
    # ------------------------------------------------------------------ #

    if args.dry_run:
        logger.info("dry-run: пропуск записи в БД и R2")
    else:
        async with AsyncSessionLocal() as session:
            await step_write(
                chunks, parse_result, machine_model,  # type: ignore[arg-type]
                args.category, args.rebuild_index, session,
            )

    return len(chunks), len(visual_tags), False


async def main(args: argparse.Namespace) -> None:
    """Run the ingestion pipeline for one or more PDF files.

    Supports checkpoint flags: --stop-after, --start-from, --save-artifacts.
    """
    start = time.monotonic()

    artifact_dir = Path(getattr(args, "artifact_dir", "./cache"))

    pdf_paths: list[Path]
    if args.path:
        pdf_paths = [Path(args.path)]
    else:
        target_dir = Path(args.dir)
        pdf_paths = sorted(target_dir.glob("*.pdf"))
        if not pdf_paths:
            logger.warning(f"В папке {target_dir} не найдено PDF-файлов")
            return

    total_chunks = 0
    total_images = 0
    skipped = 0

    for pdf_path in pdf_paths:
        logger.info(f"=== Обработка: {pdf_path.name} ===")

        machine_model: str
        if args.dir:
            machine_model = _prompt_machine_model(pdf_path.name)
        else:
            machine_model = args.machine_model

        file_start = time.monotonic()

        n_chunks, n_images, was_skipped = await _run_one_pdf(
            pdf_path, machine_model, args, artifact_dir
        )

        if was_skipped:
            skipped += 1
            continue

        total_chunks += n_chunks
        total_images += n_images
        file_elapsed = time.monotonic() - file_start

        dry_run_suffix = " (dry-run)" if args.dry_run else ""
        stop_after = getattr(args, "stop_after", None)
        stop_suffix = f" [остановлено после: {stop_after}]" if stop_after else ""
        logger.success(
            f"Завершено: {n_chunks} чанков, {n_images} изображений, "
            f"документ: {pdf_path.stem}, время: {file_elapsed:.1f}с{dry_run_suffix}{stop_suffix}"
        )

    if len(pdf_paths) > 1:
        elapsed = time.monotonic() - start
        logger.success(
            f"Итого: {total_chunks} чанков, {total_images} изображений, "
            f"файлов: {len(pdf_paths) - skipped} из {len(pdf_paths)}, "
            f"пропущено: {skipped}, время: {elapsed:.1f}с"
        )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest",
        description="Matsu Shi — загрузка PDF в векторную базу данных",
    )

    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--path",
        metavar="PDF_FILE",
        help="Путь к одному PDF-файлу для индексации",
    )
    source.add_argument(
        "--dir",
        metavar="PDF_DIR",
        help="Путь к папке с PDF-файлами (все *.pdf будут обработаны, "
        "machine model запрашивается интерактивно для каждого файла)",
    )

    parser.add_argument(
        "--machine-model",
        required=False,
        default=None,
        metavar="MODEL",
        help='Модель техники, например "PC300-8". Обязателен для --path; '
        "для --dir запрашивается интерактивно для каждого файла.",
    )
    parser.add_argument(
        "--category",
        metavar="CATEGORY",
        default=None,
        help='Категория документа, например "hydraulics" (необязательный)',
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        default=False,
        help="Удалить существующие чанки документа перед переиндексацией",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Разбор и чанкинг без записи в БД и Cloudflare R2",
    )

    # --- Phase 8.7: Checkpoint flags ---
    checkpoint = parser.add_argument_group("checkpoint (Phase 8.7)")
    checkpoint.add_argument(
        "--stop-after",
        choices=["parse", "chunk", "enrich", "embed"],
        default=None,
        metavar="STAGE",
        help=(
            "Сохранить артефакт и остановиться после указанного шага. "
            "Допустимые значения: parse, chunk, enrich, embed."
        ),
    )
    checkpoint.add_argument(
        "--start-from",
        choices=["chunk", "enrich", "embed", "write"],
        default=None,
        metavar="STAGE",
        help=(
            "Загрузить артефакт из кеша и возобновить pipeline с указанного шага. "
            "Допустимые значения: chunk, enrich, embed, write. "
            "Требует предварительного запуска с --stop-after или --save-artifacts."
        ),
    )
    checkpoint.add_argument(
        "--save-artifacts",
        action="store_true",
        default=False,
        help="Сохранить все промежуточные артефакты при полном прогоне (для инспекции и повтора).",
    )
    checkpoint.add_argument(
        "--artifact-dir",
        default="./cache",
        metavar="DIR",
        help="Директория для хранения артефактов (default: ./cache).",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if not args.path and not args.dir:
        parser.error("Укажите --path (один файл) или --dir (папка с PDF)")

    # --machine-model is required for --path mode, optional for --dir (prompted per file)
    if args.path and not args.machine_model:
        parser.error("--machine-model обязателен при использовании --path")

    asyncio.run(main(args))
    sys.exit(0)
