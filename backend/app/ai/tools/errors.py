"""把领域异常翻成对 LLM 友好的提示。

之前在 app/mcp/errors.py — Phase 2 跟着工具抽到 app/ai/tools/。

业务 service 抛的 *NotFoundError 内含一个 id,直接 str(e) 太裸,这里包一层提示
"用 list_xxx 先确认 id" — 给 LLM 当向导。

各适配器(FastMCP / LiteLLM tool calling / ...)都会把抛出的 ValueError
当作"工具执行失败,告诉模型重试"来处理。
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from app.services.chapter_service import ChapterNotFoundError, ProjectNotFoundForChapterError
from app.services.character_service import CharacterNotFoundError, ProjectNotFoundForCharacterError
from app.services.project_service import ProjectNotFoundError

F = TypeVar("F", bound=Callable[..., Any])


def friendly_errors(fn: F) -> F:
    """装饰器:把领域异常转成对 LLM 更友好的 ValueError。"""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ProjectNotFoundError as e:
            raise ValueError(
                f"工程 #{e.args[0]} 不存在。先调用 list_projects 确认可用的工程 id。"
            ) from e
        except (ProjectNotFoundForChapterError, ProjectNotFoundForCharacterError) as e:
            raise ValueError(
                f"工程 #{e.args[0]} 不存在。先调用 list_projects 确认可用的工程 id。"
            ) from e
        except ChapterNotFoundError as e:
            raise ValueError(
                f"章节 #{e.args[0]} 不存在。先调用 list_chapters 确认可用的章节 id。"
            ) from e
        except CharacterNotFoundError as e:
            raise ValueError(
                f"人物 #{e.args[0]} 不存在。先调用 list_characters 确认可用的人物 id。"
            ) from e

    return wrapper  # type: ignore[return-value]
