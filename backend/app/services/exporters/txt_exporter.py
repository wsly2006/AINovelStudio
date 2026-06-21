"""txt 导出器:全本 + 章节包 zip。

中文连载平台(起点/番茄/晋江)主流仍是 txt 上传。
- 全本格式:`第 N 章 标题\\n\\n正文\\n\\n` 兼容多数平台拆章规则
- 章节包:每章独立文件,打包成 zip,便于按章上传
- 编码可选 utf-8 / gb18030;gb18030 不可表示字符以 ? 兜底,记日志
"""

from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO

from sqlalchemy.orm import Session

from app.models.project import Project

logger = logging.getLogger(__name__)


_INVALID_FN_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def _encode(text: str, encoding: str) -> bytes:
    """按指定编码写出,gb18030 不可表示字符替换为 ?,记日志。"""
    enc = (encoding or "utf-8").lower()
    if enc not in {"utf-8", "gb18030"}:
        enc = "utf-8"
    try:
        return text.encode(enc)
    except UnicodeEncodeError:
        # 用 replace 兜底,把不可编码字符替换成 ?
        logger.warning(
            "txt export: %s 编码下存在不可表示字符,已用 ? 替换", enc
        )
        return text.encode(enc, errors="replace")


def _chapter_heading(order_index: int, title: str | None) -> str:
    sub = (title or "").strip()
    return f"第 {order_index} 章 {sub}".rstrip()


def _safe_filename(name: str) -> str:
    cleaned = _INVALID_FN_CHARS.sub("_", name).strip()
    return cleaned[:80] or "chapter"


def export_to_txt_whole(db: Session, project_id: int, encoding: str = "utf-8") -> bytes:
    """整本 txt;每章 `第 N 章 标题\\n\\n正文\\n\\n`。"""
    p = db.get(Project, project_id)
    if p is None:
        raise ValueError(f"工程不存在: {project_id}")

    parts: list[str] = []
    parts.append(p.name)
    if p.pen_name:
        parts.append(f"作者:{p.pen_name}")
    if p.blurb:
        parts.append("")
        parts.append(p.blurb.strip())
    parts.append("")
    parts.append("")

    for ch in sorted(p.chapters, key=lambda c: c.order_index):
        parts.append(_chapter_heading(ch.order_index, ch.title))
        parts.append("")
        parts.append((ch.content or "").rstrip())
        parts.append("")
        parts.append("")

    return _encode("\n".join(parts).rstrip() + "\n", encoding)


def export_to_txt_chapters_zip(
    db: Session, project_id: int, encoding: str = "utf-8"
) -> bytes:
    """每章一个 txt 打 zip。"""
    p = db.get(Project, project_id)
    if p is None:
        raise ValueError(f"工程不存在: {project_id}")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ch in sorted(p.chapters, key=lambda c: c.order_index):
            heading = _chapter_heading(ch.order_index, ch.title)
            body = (ch.content or "").rstrip()
            text = f"{heading}\n\n{body}\n"
            fname = f"{ch.order_index:04d}_{_safe_filename(ch.title or '')}.txt"
            zf.writestr(fname, _encode(text, encoding))
    return buf.getvalue()
