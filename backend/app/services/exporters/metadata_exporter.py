"""元数据副产物导出器:metadata.json / kdp_listing.txt。

设计原则:
- metadata.json 是机器可读的发布字段集合,解压后可二次脚本化
- kdp_listing.txt 按 KDP 后台上架表单字段顺序排版,人工对照填表用
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.project import Project


def _project_meta_dict(p: Project) -> dict:
    return {
        "name": p.name,
        "description": p.description,
        "synopsis": p.synopsis,
        "channel": p.channel,
        "genre": p.genre,
        "tags": list(p.tags or []),
        "pen_name": p.pen_name,
        "series_name": p.series_name,
        "series_index": p.series_index,
        "blurb": p.blurb,
        "keywords": list(p.keywords or []),
        "categories": list(p.categories or []),
        "target_platform_codes": list(p.target_platform_codes or []),
        "stats": {
            "chapter_count": len(p.chapters or []),
            "word_count": sum((c.word_count or 0) for c in (p.chapters or [])),
        },
    }


def export_metadata_json(db: Session, project_id: int) -> bytes:
    p = db.get(Project, project_id)
    if p is None:
        raise ValueError(f"工程不存在: {project_id}")
    body = json.dumps(_project_meta_dict(p), ensure_ascii=False, indent=2)
    return body.encode("utf-8")


def export_kdp_listing(db: Session, project_id: int) -> bytes:
    """按 KDP 上架表单顺序排版,纯文本对照填表用。"""
    p = db.get(Project, project_id)
    if p is None:
        raise ValueError(f"工程不存在: {project_id}")

    parts: list[str] = []
    parts.append("=== Amazon KDP 上架字段对照 ===")
    parts.append("")
    parts.append(f"Book Title:    {p.name}")
    if p.series_name:
        parts.append(f"Series Title:  {p.series_name}")
        if p.series_index:
            parts.append(f"Volume Number: {p.series_index}")
    parts.append(f"Author Name:   {p.pen_name or '<待填写>'}")
    parts.append("")
    parts.append("--- Description (Long Blurb, max 4000 chars) ---")
    parts.append(p.blurb or p.description or "<待填写>")
    parts.append("")
    parts.append("--- Keywords (KDP 上限 7 个) ---")
    kws = list(p.keywords or [])
    if kws:
        for i, kw in enumerate(kws[:7], 1):
            parts.append(f"  {i}. {kw}")
        if len(kws) > 7:
            parts.append(f"  (注意:已配置 {len(kws)} 个,KDP 仅取前 7 个)")
    else:
        parts.append("  <待填写>")
    parts.append("")
    parts.append("--- Categories (KDP 最多选 2 个 BISAC) ---")
    cats = list(p.categories or [])
    if cats:
        for i, c in enumerate(cats[:2], 1):
            parts.append(f"  {i}. {c}")
        if len(cats) > 2:
            parts.append(f"  (注意:已配置 {len(cats)} 个,KDP 仅取前 2 个)")
    else:
        parts.append("  <待填写>")
    parts.append("")
    return "\n".join(parts).encode("utf-8")
