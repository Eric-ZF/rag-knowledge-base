"""
Phase 1 — 数据接入层：解析器工厂
"""
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import BinaryIO

# ─── 解析结果数据结构 ────────────────────────────────────

@dataclass
class ParsedDocument:
    """统一解析输出格式"""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str = ""
    doi: str = ""
    language: str = "en"
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    sections: list["Section"] = field(default_factory=list)
    tables: list["Table"] = field(default_factory=list)
    references_text: str = ""  # 参考文献区（不入库索引）
    file_hash: str = ""
    parsing_warnings: list[str] = field(default_factory=list)

@dataclass
class Section:
    title: str = ""
    path: str = ""       # 如 "1.2.3"
    order: int = 0
    page_start: int | None = None
    page_end: int | None = None
    paragraphs: list[str] = field(default_factory=list)

@dataclass
class Table:
    title: str = ""
    page: int | None = None
    markdown: str = ""


# ─── 解析器基类 ─────────────────────────────────────────

class BaseParser(ABC):
    name: str = "base"

    @abstractmethod
    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        ...

    def compute_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


# ─── PDF 解析器（pymupdf）────────────────────────────────

class PDFParser(BaseParser):
    name = "pdf"

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        import fitz  # pymupdf

        doc = fitz.open(stream=file_content, filetype="pdf")
        doc_metadata = doc.metadata

        result = ParsedDocument(
            title=doc_metadata.get("title", "") or filename.replace(".pdf", ""),
            authors=self._parse_authors(doc_metadata.get("author", "")),
            year=self._extract_year(doc_metadata.get("creationDate", "")),
            parsing_warnings=[],
        )
        result.file_hash = self.compute_hash(file_content)

        # 检测语言（简单 heuristics）
        sample_text = self._get_sample_text(doc, n_pages=3)
        result.language = self._detect_language(sample_text)

        # 提取全文用于后续处理
        full_text = ""
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            result.sections.append(Section(
                title=f"Page {page_num + 1}",
                order=page_num,
                page_start=page_num + 1,
                page_end=page_num + 1,
                paragraphs=[p.strip() for p in text.split("\n") if p.strip()],
            ))
            full_text += text + "\n"

        # 尝试提取摘要（通常在第一页或正文之前）
        result.abstract = self._extract_abstract(result.sections, full_text)

        # 提取关键词
        result.keywords = self._extract_keywords(doc_metadata.get("keywords", ""))

        # 尝试提取参考文献区
        result.references_text = self._extract_references(full_text)

        doc.close()
        return result

    def _parse_authors(self, author_str: str) -> list[str]:
        if not author_str:
            return []
        # 常见分隔符：; , and &
        for sep in [";", " and ", " & "]:
            if sep in author_str:
                return [a.strip() for a in author_str.split(sep) if a.strip()]
        if "," in author_str:
            parts = author_str.split(",")
            if len(parts) > 2:
                return [p.strip() for p in parts]
        return [author_str.strip()]

    def _extract_year(self, creation_date: str) -> int | None:
        """从 PDF creation date 字符串提取年份，格式：D:YYYYMMDDHHmmSS"""
        if not creation_date:
            return None
        if creation_date.startswith("D:"):
            creation_date = creation_date[2:]
        if len(creation_date) >= 4:
            try:
                return int(creation_date[0:4])
            except ValueError:
                return None
        return None

    def _get_sample_text(self, doc, n_pages: int = 3) -> str:
        texts = []
        for i in range(min(n_pages, len(doc))):
            texts.append(doc[i].get_text("text"))
        return "\n".join(texts)

    def _detect_language(self, text: str) -> str:
        # 简单 heuristics：计算中文字符比例
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        total_chars = len(text)
        if total_chars == 0:
            return "en"
        chinese_ratio = chinese_chars / total_chars
        return "zh" if chinese_ratio > 0.3 else "en"

    def _extract_abstract(self, sections: list[Section], full_text: str) -> str:
        """尝试从正文提取摘要（关键字：摘要、Abstract）"""
        abstract_markers = ["abstract", "摘要", "abstracts", "summary", "概要"]
        intro_markers = ["1.", "introduction", "一、引言", "1 引言"]

        lines = full_text.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(m.lower() in line_lower for m in abstract_markers):
                # 找下一段或连续几行作为摘要
                abstract_lines = []
                for j in range(i + 1, min(i + 20, len(lines))):
                    if any(m.lower() in lines[j].lower() for m in intro_markers):
                        break
                    if lines[j].strip():
                        abstract_lines.append(lines[j].strip())
                if abstract_lines:
                    return " ".join(abstract_lines)
        return ""

    def _extract_keywords(self, keywords_str: str) -> list[str]:
        if not keywords_str:
            return []
        for sep in [";", ",", "，", "、"]:
            if sep in keywords_str:
                return [k.strip() for k in keywords_str.split(sep) if k.strip()]
        return [keywords_str.strip()]

    def _extract_references(self, full_text: str) -> str:
        """提取参考文献区（关键词匹配）"""
        ref_markers = [
            "references", "参考文献", "reference", "bibliography",
            "works cited", "literature cited",
        ]
        lines = full_text.split("\n")
        in_ref = False
        ref_parts = []
        for line in lines:
            if not in_ref:
                if any(m.lower() in line.lower() for m in ref_markers):
                    in_ref = True
            else:
                ref_parts.append(line)
        return "\n".join(ref_parts)


# ─── 解析器工厂 ─────────────────────────────────────────

class ParserFactory:
    _parsers: dict[str, BaseParser] = {
        "pdf": PDFParser(),
    }

    @classmethod
    def get(cls, file_ext: str) -> BaseParser:
        ext = file_ext.lower().lstrip(".")
        parser = cls._parsers.get(ext)
        if not parser:
            raise ValueError(f"不支持的文件类型: .{ext}，支持的类型: {list(cls._parsers.keys())}")
        return parser

    @classmethod
    def parse(cls, file_content: bytes, filename: str) -> ParsedDocument:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        parser = cls.get(ext)
        return parser.parse(file_content, filename)
