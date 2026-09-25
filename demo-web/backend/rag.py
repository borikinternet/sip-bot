"""Session-scoped corpus preparation and atomic publication."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from pypdf import PdfReader

from config import constants
from sip_bot.dialogue.events import StructuredDecision
from sip_bot.llm import LlmFacade, OllamaHttpClient, StreamEventKind
from sip_bot.prompt.manager import LlmRequest, PromptDiagnostics
from sip_bot.retrieval import KnowledgeQueryBuilder, build_and_publish_index
from sip_bot.retrieval.contracts import (
    CORPUS_SCHEMA_VERSION,
    EmbeddingProvider,
    EmbeddingRequest,
    EmbeddingResponse,
    KnowledgeContext,
)
from sip_bot.retrieval.index import LocalKnowledgeIndex

from .models import MAX_UPLOAD_BYTES


class RagPreparationError(RuntimeError):
    """The uploaded corpus did not cross the prepared-artifact boundary."""


class _ReadableHtml(HTMLParser):
    """Keep document prose and headings; discard page chrome and executable text."""

    _SKIP = {"head", "script", "style", "noscript", "template", "svg", "nav", "footer", "aside", "form"}
    _BLOCK = {"article", "blockquote", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "main", "p", "section", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self.skip_depth += 1
        elif not self.skip_depth and tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif not self.skip_depth and tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def _extract_html_text(data: bytes) -> str:
    try:
        html = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RagPreparationError("HTML document must be valid UTF-8") from exc
    parser = _ReadableHtml()
    parser.feed(html)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    text = "\n\n".join(line for line in lines if line)
    if not text:
        raise RagPreparationError("HTML document does not contain readable text")
    return text


def _extract_pdf_text(data: bytes) -> str:
    """Extract selectable text from a PDF without introducing an OCR pipeline."""

    try:
        reader = PdfReader(BytesIO(data), strict=False)
        pages: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:  # pypdf exposes parser errors per page.
                raise RagPreparationError(f"cannot extract text from PDF page {page_number}") from exc
            if page_text.strip():
                pages.append(page_text.strip())
    except RagPreparationError:
        raise
    except Exception as exc:
        raise RagPreparationError("cannot read PDF file") from exc

    text = "\n\n".join(pages).strip()
    if not text or "\x00" in text:
        raise RagPreparationError("PDF does not contain selectable text; scanned PDFs are not supported")
    return text


def _decode_uploaded_document(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix == ".pdf":
        return _extract_pdf_text(data)
    if suffix in {".html", ".htm"}:
        return _extract_html_text(data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RagPreparationError("uploaded file must be valid UTF-8") from exc
    if not text.strip() or "\x00" in text:
        raise RagPreparationError("uploaded file must contain non-empty text without NUL")
    return text


@dataclass(frozen=True, slots=True)
class RagMetadata:
    title: str
    topic: str
    description: str
    questions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "topic": self.topic,
            "description": self.description,
            "questions": list(self.questions),
        }


class MetadataProvider(Protocol):
    def generate(self, *, text: str, filename: str, corpus_id: str) -> RagMetadata: ...


class EmbeddingFacadeProvider:
    """Typed embedding adapter; it never calls Ollama outside the facade."""

    def __init__(self, facade: LlmFacade) -> None:
        self.facade = facade

    def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        return self.facade.embed(request)


class StaticMetadataProvider:
    """Deterministic provider used by offline tests and local UI smoke runs."""

    def generate(self, *, text: str, filename: str, corpus_id: str) -> RagMetadata:
        first_line = next((line.strip("# \t") for line in text.splitlines() if line.strip()), filename)
        topic = first_line[:120] or "загруженному документу"
        return RagMetadata(
            title=first_line[:120] or "Пользовательский корпус",
            topic=topic,
            description=f"Вопросы по материалам файла «{filename}».",
            questions=(
                "О чём этот документ?",
                "Какие основные факты в нём приведены?",
                "Какие выводы можно сделать по материалам корпуса?",
            ),
        )


class OllamaMetadataProvider:
    """Generate bounded UI metadata through the existing typed chat facade."""

    def __init__(self, facade: LlmFacade | None = None) -> None:
        self.facade = facade or LlmFacade(
            OllamaHttpClient(
                endpoint=constants.LLM_HTTP_ENDPOINT,
                chat_model=constants.LLM_CHAT_MODEL,
                timeout_s=constants.LLM_READ_TIMEOUT_S,
                max_generation_tokens=512,
            )
        )

    def generate(self, *, text: str, filename: str, corpus_id: str) -> RagMetadata:
        context = KnowledgeContext(
            context_id=f"metadata-{corpus_id}",
            query_text="metadata",
            hits=(),
            sufficient=True,
            threshold=0.0,
            top_k=1,
            index_version="metadata-only",
            embedding_model=constants.LLM_EMBEDDING_MODEL,
        )
        prompt = (
            "Проанализируй загруженный русскоязычный документ для демонстрационного RAG. "
            "Верни в поле text строго JSON без Markdown с ключами title, topic, description, questions. "
            "title/topic — короткие строки до 120 символов, description — до 160 символов, "
            "questions — массив из 5 коротких самостоятельных вопросов (каждый до 80 символов), на каждый из которых "
            "в тексте есть прямой, однозначный ответ. Используй те же ключевые слова и имена, "
            "что в тексте. Не спрашивай о причинах, изменениях, последствиях или применении, "
            "если они не объяснены прямо. Для длинного документа выбери вопросы из разных разделов. "
            "Не выдумывай сведения вне текста.\n\n"
            f"Имя файла: {filename}\nТекст документа:\n{text[:9000]}"
        )
        request = LlmRequest(
            call_id=f"rag-metadata-{corpus_id}",
            turn_id=f"metadata-{uuid.uuid4().hex}",
            skill_id="rag-metadata",
            skill_version="1",
            prompt_template_id="rag-metadata-json",
            prompt_template_version="1",
            generation_profile_id="rag-metadata-short",
            generation_profile_version="1",
            output_schema_id="rag-metadata-envelope-v1",
            final_user_text=prompt[: constants.LLM_MAX_REQUEST_CHARS],
            prompt=prompt,
            knowledge_context=context,
            authoritative=True,
            answer_mode="rag_answer",
            allowed_actions=("answer",),
            diagnostics=PromptDiagnostics(
                skill_id="rag-metadata",
                skill_version="1",
                template_id="rag-metadata-json",
                template_version="1",
                profile_id="rag-metadata-short",
                profile_version="1",
                knowledge_context_id=context.context_id,
                source_ids=(),
                sufficient=True,
            ),
        )
        operation = self.facade.start_chat(request)
        events = list(operation)
        decision = next(
            (event.decision for event in events if event.kind is StreamEventKind.DECISION),
            None,
        )
        if not isinstance(decision, StructuredDecision) or not decision.text:
            raise RagPreparationError(
                f"metadata LLM did not return a structured result: {operation.error_detail or operation.status.status.value}"
            )
        try:
            payload = json.loads(decision.text)
        except json.JSONDecodeError as exc:
            raise RagPreparationError("metadata LLM returned invalid JSON") from exc
        return _metadata_from_payload(payload)


@dataclass(frozen=True, slots=True)
class PreparedRag:
    artifact_dir: Path
    index_path: Path
    metadata: dict[str, Any]
    registry_payload: dict[str, Any]


class RagPreparationCoordinator:
    """Build one immutable artifact and publish it only after self-check."""

    def __init__(
        self,
        *,
        artifact_root: Path,
        registry_root: Path,
        embedding_provider: EmbeddingProvider,
        embedding_model: str = constants.RAG_EMBEDDING_MODEL,
        metadata_provider: MetadataProvider | None = None,
    ) -> None:
        self.artifact_root = artifact_root
        self.registry_root = registry_root
        self.embedding_provider = embedding_provider
        self.embedding_model = embedding_model
        self.metadata_provider = metadata_provider or OllamaMetadataProvider()

    def prepare(
        self,
        *,
        session_id: str,
        caller_id: str,
        filename: str,
        data: bytes,
        source_url: str | None = None,
    ) -> PreparedRag:
        if len(data) > MAX_UPLOAD_BYTES:
            raise RagPreparationError("uploaded file exceeds 640 KiB")
        suffix = Path(filename).suffix.casefold()
        if suffix not in {".md", ".txt", ".pdf", ".html", ".htm"}:
            raise RagPreparationError("only .md, .txt, .html and text-based .pdf documents are accepted")
        text = _decode_uploaded_document(filename, data)

        corpus_id = f"conference-{session_id[:20]}"
        metadata = self.metadata_provider.generate(text=text, filename=filename, corpus_id=corpus_id)
        source_sha256 = hashlib.sha256(data).hexdigest()
        generation = uuid.uuid4().hex
        final_dir = self.artifact_root / f"{session_id}-{generation}"
        temporary_dir = self.artifact_root / f".{session_id}-{generation}.building"
        temporary_dir.mkdir(parents=True, exist_ok=False)
        try:
            document_name = "uploaded-document.md"
            (temporary_dir / document_name).write_text(text, encoding="utf-8")
            manifest = {
                "schema_version": CORPUS_SCHEMA_VERSION,
                "corpus_id": corpus_id,
                "corpus_version": f"{corpus_id}-v1",
                "title": metadata.title,
                "language": "ru",
                "license": "conference-demo-user-upload",
                "sources": [
                    {
                        "source_id": "uploaded-document",
                        "file": document_name,
                        "title": metadata.title,
                        "origin": source_url or f"conference upload: {filename}",
                        "license": "conference-demo-user-upload",
                        "attribution": "Загружено посетителем конференции",
                        "owner": "conference-demo",
                        "version": source_sha256[:16],
                        "effective_date": date.today().isoformat(),
                        "priority": 100,
                        "topics": [metadata.topic],
                        "audiences": ["посетители конференции"],
                    }
                ],
            }
            (temporary_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            index_path = temporary_dir / "index.json"
            report = build_and_publish_index(
                temporary_dir,
                index_path,
                self.embedding_provider,
                index_version=f"{corpus_id}-{source_sha256[:12]}",
                embedding_model=self.embedding_model,
            )
            index = LocalKnowledgeIndex.load(
                index_path,
                expected_index_version=report.index_version,
                expected_corpus_version=report.corpus_version,
                expected_embedding_model=self.embedding_model,
            )
            questions = verified_questions(metadata.questions, index, self.embedding_provider)
            artifact_metadata = {
                **metadata.as_dict(),
                "questions": list(questions),
                "corpus_id": corpus_id,
                "corpus_version": report.corpus_version,
                "source_sha256": source_sha256,
                "index_version": report.index_version,
                "embedding_model": report.embedding_model,
                "dimension": report.dimension,
                "item_count": report.item_count,
                "original_filename": filename,
                "source_url": source_url,
            }
            (temporary_dir / "metadata.json").write_text(
                json.dumps(artifact_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary_dir.replace(final_dir)
            published_index = final_dir / "index.json"
            registry_payload = {
                "schema_version": "conference-rag-registry-v1",
                "session_id": session_id,
                "caller_id": caller_id,
                "state": "ready",
                "index_path": str(published_index.resolve()),
                "artifact_dir": str(final_dir.resolve()),
                "metadata_path": str((final_dir / "metadata.json").resolve()),
                "metadata": artifact_metadata,
            }
            (final_dir / "registry.json").write_text(
                json.dumps(registry_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return PreparedRag(final_dir, published_index, artifact_metadata, registry_payload)
        except BaseException:
            if temporary_dir.exists():
                import shutil

                shutil.rmtree(temporary_dir)
            if final_dir.exists():
                import shutil

                shutil.rmtree(final_dir)
            raise


def verified_questions(
    questions: tuple[str, ...],
    index: LocalKnowledgeIndex,
    embedding_provider: EmbeddingProvider,
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    """Expose only examples accepted by the bot's actual retrieval gate."""

    builder = KnowledgeQueryBuilder()
    accepted: list[tuple[str, str]] = []
    seen: set[str] = set()
    for question in questions:
        normalized = question.strip().casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        context = index.query(
            builder.build(question),
            embedding_provider,
            top_k=constants.RAG_TOP_K,
            threshold=constants.RAG_RELEVANCE_THRESHOLD,
            context_id=f"example-{len(seen)}",
        )
        if context.sufficient:
            hits = getattr(context, "hits", ())
            source_id = hits[0].source_id if hits else "unknown"
            accepted.append((question, source_id))
    # For a multi-source corpus, show its breadth before repeating a source.
    selected: list[str] = []
    selected_sources: set[str] = set()
    for question, source_id in accepted:
        if source_id not in selected_sources:
            selected.append(question)
            selected_sources.add(source_id)
        if len(selected) >= limit:
            return tuple(selected)
    for question, _ in accepted:
        if question not in selected:
            selected.append(question)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _metadata_from_payload(payload: object) -> RagMetadata:
    if not isinstance(payload, dict):
        raise RagPreparationError("metadata payload must be a JSON object")
    title = _bounded_text(payload.get("title"), "title", 120)
    topic = _bounded_text(payload.get("topic"), "topic", 120)
    description = _bounded_text(payload.get("description"), "description", 300)
    questions_raw = payload.get("questions")
    if not isinstance(questions_raw, list) or not 3 <= len(questions_raw) <= 10:
        raise RagPreparationError("metadata questions must contain 3 to 10 items")
    questions = tuple(_bounded_text(item, "question", 180) for item in questions_raw)
    return RagMetadata(title, topic, description, questions)


def _bounded_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RagPreparationError(f"metadata {field} is empty")
    value = " ".join(value.split())
    if len(value) > limit:
        raise RagPreparationError(f"metadata {field} exceeds {limit} characters")
    return value


__all__ = [
    "EmbeddingFacadeProvider",
    "OllamaMetadataProvider",
    "PreparedRag",
    "RagMetadata",
    "RagPreparationCoordinator",
    "RagPreparationError",
    "StaticMetadataProvider",
]
