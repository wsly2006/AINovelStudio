"""EPUB 导出器。

使用 ebooklib 生成符合 EPUB 3 的电子书,适配 Amazon KDP / Apple Books / Calibre。

设计要点:
- 不嵌入字体,依赖阅读器系统字体(中英文阅读器都能渲染)
- blurb 写入 description meta;keywords/categories 写入 subject meta
- 章节按 order_index 顺序;每章一个 XHTML 文档
- 段落级渲染:把 chapter.content 按空行拆段,每段包成 <p>
"""

from __future__ import annotations

import html
import os
import re
import tempfile

from ebooklib import epub
from sqlalchemy.orm import Session

from app.models.project import Project


_PARA_SPLIT = re.compile(r"\n\s*\n+")


def _paragraphs_from_content(content: str) -> list[str]:
    """章节正文按空行拆段;单换行视作段内换行,转 <br/>。"""
    paragraphs: list[str] = []
    for raw in _PARA_SPLIT.split(content or ""):
        para = raw.strip()
        if not para:
            continue
        # 段内换行 → <br/>;转义后再插入(转义不会动 < > & 之外的字符)
        escaped = html.escape(para).replace("\n", "<br/>")
        paragraphs.append(escaped)
    return paragraphs


def _chapter_xhtml(title: str, paragraphs: list[str]) -> str:
    body_paras = "\n".join(f"  <p>{p}</p>" for p in paragraphs) or "  <p></p>"
    title_html = html.escape(title or "")
    return (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh"><head>\n'
        f"  <title>{title_html}</title>\n"
        '  <link rel="stylesheet" type="text/css" href="style.css" />\n'
        "</head><body>\n"
        f"  <h2>{title_html}</h2>\n"
        f"{body_paras}\n"
        "</body></html>"
    )


_DEFAULT_CSS = """
body { font-family: serif; line-height: 1.6; }
h2 { text-align: center; margin: 2em 0 1em; }
p { text-indent: 2em; margin: 0 0 0.6em; }
""".strip()


def export_to_epub(db: Session, project_id: int) -> bytes:
    p = db.get(Project, project_id)
    if p is None:
        raise ValueError(f"工程不存在: {project_id}")

    book = epub.EpubBook()
    # 没有正式 ISBN,用 project id + name 拼一个稳定 identifier
    book.set_identifier(f"ainovelstudio-{p.id}")
    book.set_title(p.name)
    # 语言:目前没有 language 字段,先按 zh 标记;P0 翻译落地后再读取
    book.set_language("zh")

    if p.pen_name:
        book.add_author(p.pen_name)
    if p.blurb:
        book.add_metadata("DC", "description", p.blurb)
    elif p.description:
        book.add_metadata("DC", "description", p.description)
    if p.series_name:
        # EPUB 没标准 series 字段,Calibre 用 calibre:series meta 习惯
        book.add_metadata(
            None,
            "meta",
            "",
            {"name": "calibre:series", "content": p.series_name},
        )
        if p.series_index:
            book.add_metadata(
                None,
                "meta",
                "",
                {"name": "calibre:series_index", "content": str(p.series_index)},
            )
    for kw in (p.keywords or []):
        book.add_metadata("DC", "subject", kw)
    for cat in (p.categories or []):
        book.add_metadata("DC", "subject", cat)

    css = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css", content=_DEFAULT_CSS
    )
    book.add_item(css)

    spine: list = ["nav"]
    toc: list = []
    chapters = sorted(p.chapters, key=lambda c: c.order_index)
    for idx, ch in enumerate(chapters, start=1):
        title = (ch.title or "").strip() or f"第 {ch.order_index} 章"
        # 复合显示标题:第 N 章 + 副标题
        display = f"第 {ch.order_index} 章" if (ch.title or "").strip() else title
        if (ch.title or "").strip():
            display = f"第 {ch.order_index} 章 {ch.title.strip()}"
        item = epub.EpubHtml(
            title=display,
            file_name=f"chap_{idx:04d}.xhtml",
            lang="zh",
        )
        # ebooklib 内部用 lxml 解析 content,必须是 bytes
        item.content = _chapter_xhtml(
            display, _paragraphs_from_content(ch.content or "")
        ).encode("utf-8")
        item.add_item(css)
        book.add_item(item)
        spine.append(item)
        toc.append(item)

    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    # ebooklib 的 write_epub 只接受文件路径,这里写到临时文件再读回
    fd, tmp_path = tempfile.mkstemp(suffix=".epub")
    os.close(fd)
    try:
        epub.write_epub(tmp_path, book)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
