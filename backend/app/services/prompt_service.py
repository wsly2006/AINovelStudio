"""提示词服务:加载 / 保存 / 还原 + 渲染。

渲染逻辑:
    最终文本 = 模板.replace("{{key}}", value) ...,然后把多余空行合并。
    这样允许某些块缺失时,模板里对应行会被替换成空字符串,
    再收一遍连续空行,不会留下大段空白。
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.ai.prompt_registry import PromptDef, all_prompts, get as registry_get
from app.models.prompt_template import PromptTemplate


_BLANK_LINES = re.compile(r"\n{3,}")


def list_all() -> list[PromptDef]:
    return list(all_prompts())


def get_def(key: str) -> PromptDef:
    return registry_get(key)


def load(db: Session | None, key: str) -> tuple[str, str, bool]:
    """返回 (system_text, user_template, customized)。customized=True 表示来自 DB。

    db=None 时直接返回默认值,不查表(用于单测和无 db 的纯渲染)。
    """
    pdef = registry_get(key)
    if db is None:
        return pdef.default_system, pdef.default_user, False
    row = db.get(PromptTemplate, key)
    if row is None:
        return pdef.default_system, pdef.default_user, False
    return row.system_text, row.user_template, True


def save(db: Session, key: str, system_text: str, user_template: str) -> PromptTemplate:
    registry_get(key)  # 校验 key
    row = db.get(PromptTemplate, key)
    if row is None:
        row = PromptTemplate(key=key, system_text=system_text, user_template=user_template)
        db.add(row)
    else:
        row.system_text = system_text
        row.user_template = user_template
    db.commit()
    db.refresh(row)
    return row


def reset(db: Session, key: str) -> None:
    """删除覆盖,回到默认。"""
    registry_get(key)
    row = db.get(PromptTemplate, key)
    if row is not None:
        db.delete(row)
        db.commit()


def render(db: Session | None, key: str, values: dict[str, str]) -> list[dict]:
    """加载模板并填充占位符,返回 messages 列表。

    缺失的占位符按空字符串处理,渲染完后把 3+ 连续换行折叠成 2 个,
    避免某些块为空时留下大块空白。db=None 时走默认模板。
    """
    system_text, user_template, _ = load(db, key)
    user = user_template
    pdef = registry_get(key)
    for ph in pdef.placeholders:
        user = user.replace("{{" + ph + "}}", str(values.get(ph, "")))
    user = _BLANK_LINES.sub("\n\n", user).strip()
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user},
    ]
