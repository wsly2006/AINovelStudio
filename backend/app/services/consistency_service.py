"""一致性问题持久化服务。

跑一次扫描会产生一个新 run_id,所有本次发现的 issue 共享。老 run 的 issue 不删,
状态(open/resolved/dismissed)由用户改 —— 长篇写到后期能查「这本书还欠哪些坑」。
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.models.consistency_issue import ConsistencyIssue
from app.models.project import Project
from app.schemas.consistency_issue import (
    ConsistencyCheckResult,
    ConsistencyIssueRead,
    ConsistencyIssueUpdate,
)
from app.services import plot_service, prompt_service


class ConsistencyIssueNotFoundError(Exception):
    pass


class ProjectNotFoundForIssueError(Exception):
    pass


def _parse_issues_json(raw: str) -> list[dict]:
    """从 AI 输出里抠 issues 列表。容忍 markdown 代码块包裹。"""
    import json
    import re

    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    items = data.get("issues") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def _coerce_int_list(raw) -> list[int]:
    if not isinstance(raw, list):
        return []
    out = []
    for x in raw:
        if isinstance(x, bool):
            continue
        if isinstance(x, int):
            out.append(x)
        elif isinstance(x, str) and x.strip().lstrip("-").isdigit():
            out.append(int(x))
    return out


async def run_check(db: Session, project_id: int) -> ConsistencyCheckResult:
    """跑一次一致性扫描:调 AI → 解析 → 落库 → 返回本批次。"""
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundForIssueError(project_id)

    characters = list(project.characters)
    events = plot_service.list_events(db, project_id)

    chars_brief = "\n".join(
        f"id={c.id} {c.name}: {c.profile or ''}" for c in characters
    ) or "(无)"
    events_brief = "\n".join(
        f"- ev{ev.id} 章 {ev.chapter_id} 「{ev.title}」(人物 ids: {ev.character_ids}): {ev.description or ''}"
        for ev in events
    ) or "(无)"

    messages = prompt_service.render(
        db,
        "analysis.check",
        {
            "project_name": project.name,
            "characters_brief": chars_brief,
            "events_brief": events_brief,
        },
    )
    raw = await ai_client.complete(
        db, messages, scene="analysis.check", max_tokens=3000, project_id=project_id
    )
    items = _parse_issues_json(raw)

    run_id = str(uuid.uuid4())
    created: list[ConsistencyIssue] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        kind = (item.get("kind") or "其他").strip()[:32]
        detail = (item.get("detail") or "").strip() or None
        row = ConsistencyIssue(
            project_id=project_id,
            run_id=run_id,
            kind=kind,
            title=title[:200],
            detail=detail,
            related_event_ids=_coerce_int_list(item.get("related_event_ids")),
            related_character_ids=_coerce_int_list(item.get("related_character_ids")),
            status="open",
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)

    open_count = _count_open(db, project_id)
    return ConsistencyCheckResult(
        run_id=run_id,
        issues=[ConsistencyIssueRead.model_validate(r) for r in created],
        open_count=open_count,
    )


def list_issues(
    db: Session, project_id: int, *, status: str | None = None
) -> list[ConsistencyIssueRead]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForIssueError(project_id)
    stmt = (
        select(ConsistencyIssue)
        .where(ConsistencyIssue.project_id == project_id)
        .order_by(ConsistencyIssue.created_at.desc(), ConsistencyIssue.id.desc())
    )
    if status:
        stmt = stmt.where(ConsistencyIssue.status == status)
    rows = db.execute(stmt).scalars().all()
    return [ConsistencyIssueRead.model_validate(r) for r in rows]


def count_open(db: Session, project_id: int) -> int:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForIssueError(project_id)
    return _count_open(db, project_id)


def _count_open(db: Session, project_id: int) -> int:
    stmt = select(func.count(ConsistencyIssue.id)).where(
        ConsistencyIssue.project_id == project_id,
        ConsistencyIssue.status == "open",
    )
    return int(db.execute(stmt).scalar() or 0)


def update_issue(
    db: Session, issue_id: int, payload: ConsistencyIssueUpdate
) -> ConsistencyIssueRead:
    row = db.get(ConsistencyIssue, issue_id)
    if row is None:
        raise ConsistencyIssueNotFoundError(issue_id)
    row.status = payload.status
    db.commit()
    db.refresh(row)
    return ConsistencyIssueRead.model_validate(row)


def delete_issue(db: Session, issue_id: int) -> None:
    row = db.get(ConsistencyIssue, issue_id)
    if row is None:
        raise ConsistencyIssueNotFoundError(issue_id)
    db.delete(row)
    db.commit()
