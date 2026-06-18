from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.prompt import PromptItem, PromptUpdate
from app.services import prompt_service

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


def _to_item(pdef, system_text: str, user_template: str, customized: bool) -> PromptItem:
    return PromptItem(
        key=pdef.key,
        name=pdef.name,
        group=pdef.group,
        description=pdef.description,
        placeholders=list(pdef.placeholders),
        system_text=system_text,
        user_template=user_template,
        customized=customized,
        default_system=pdef.default_system,
        default_user=pdef.default_user,
    )


@router.get("", response_model=list[PromptItem])
def list_prompts(db: Session = Depends(get_db)) -> list[PromptItem]:
    out: list[PromptItem] = []
    for pdef in prompt_service.list_all():
        system_text, user_template, customized = prompt_service.load(db, pdef.key)
        out.append(_to_item(pdef, system_text, user_template, customized))
    return out


@router.put("/{key}", response_model=PromptItem)
def update_prompt(
    key: str, payload: PromptUpdate, db: Session = Depends(get_db)
) -> PromptItem:
    try:
        pdef = prompt_service.get_def(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"未知的提示词: {key}")
    prompt_service.save(db, key, payload.system_text, payload.user_template)
    return _to_item(pdef, payload.system_text, payload.user_template, True)


@router.post("/{key}/reset", response_model=PromptItem)
def reset_prompt(key: str, db: Session = Depends(get_db)) -> PromptItem:
    try:
        pdef = prompt_service.get_def(key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"未知的提示词: {key}")
    prompt_service.reset(db, key)
    return _to_item(pdef, pdef.default_system, pdef.default_user, False)
