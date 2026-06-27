"""作者声音档案 service。

一个项目至多一份,所以 API 走 GET / PUT(upsert) / DELETE,不开 POST。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.author_voice_profile import AuthorVoiceProfile
from app.models.project import Project
from app.schemas.author_voice_profile import (
    AuthorVoiceProfileRead,
    AuthorVoiceProfileUpsert,
)


class ProjectNotFoundError(Exception):
    pass


class VoiceProfileNotFoundError(Exception):
    pass


def get_profile(db: Session, project_id: int) -> AuthorVoiceProfileRead | None:
    """读不到返回 None — 让 API 决定 404 还是返回空对象。"""
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundError(project_id)
    stmt = select(AuthorVoiceProfile).where(AuthorVoiceProfile.project_id == project_id)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    return AuthorVoiceProfileRead.model_validate(row)


def upsert_profile(
    db: Session, project_id: int, payload: AuthorVoiceProfileUpsert
) -> AuthorVoiceProfileRead:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundError(project_id)
    stmt = select(AuthorVoiceProfile).where(AuthorVoiceProfile.project_id == project_id)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        row = AuthorVoiceProfile(
            project_id=project_id,
            quirks=payload.quirks,
            style_notes=payload.style_notes,
        )
        db.add(row)
    else:
        row.quirks = payload.quirks
        row.style_notes = payload.style_notes
    db.commit()
    db.refresh(row)
    return AuthorVoiceProfileRead.model_validate(row)


def delete_profile(db: Session, project_id: int) -> None:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundError(project_id)
    stmt = select(AuthorVoiceProfile).where(AuthorVoiceProfile.project_id == project_id)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise VoiceProfileNotFoundError(project_id)
    db.delete(row)
    db.commit()


def build_prompt_fragment(db: Session, project_id: int) -> str:
    """给 chapter_ai_service 拼 system prompt 时调用。

    没 profile / 全空就返回 "",调用方拿到空串就不拼接。
    """
    profile = get_profile(db, project_id) if db.get(Project, project_id) else None
    if profile is None:
        return ""
    parts: list[str] = []
    if profile.style_notes:
        parts.append(profile.style_notes.strip())
    if profile.quirks:
        # 行首符让 LLM 更易当成清单
        lines = "\n".join(f"- {q}" for q in profile.quirks)
        parts.append(f"个人语癖(尽量自然融入,不要刻意堆砌):\n{lines}")
    if not parts:
        return ""
    body = "\n\n".join(parts)
    return (
        "【作者声音】\n"
        "本作的写作要保留以下个人风格特征,不要被通用 AI 文风覆盖:\n"
        f"{body}"
    )
