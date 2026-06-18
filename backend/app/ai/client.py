"""LiteLLM 客户端封装。

调用流程:
1. 从 DB 读 AI 设置(provider/model/api_key/base_url/...)
2. 若 DB 没配置且 env 也没 key → 抛 AINotConfiguredError
3. 把参数显式传给 litellm,不依赖环境变量被自动读取
4. 调用结束后(成功 / 失败 / 流式)写一条日志:
   - INFO 行进 data/logs/ai-*.log
   - 一条记录入 ai_call_logs 表(短事务,独立 session)
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.ai.runtime import RuntimeAIConfig, resolve
from app.database import SessionLocal
from app.logging_config import get_ai_logger
from app.models.ai_call_log import AICallLog


class AINotConfiguredError(Exception):
    """没有任何 API key,AI 功能不可用"""


class AIError(Exception):
    """AI 调用失败的统一错误"""


def _build_kwargs(cfg: RuntimeAIConfig) -> dict:
    if not cfg.configured:
        raise AINotConfiguredError(
            "尚未配置 AI key。点击右上角的「模型配置」选择 provider 并填入 key,"
            "或在 backend/.env 设置 ANTHROPIC_API_KEY / OPENAI_API_KEY 等。"
        )
    kwargs: dict = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if cfg.api_base:
        kwargs["api_base"] = cfg.api_base
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    return kwargs


def _extract_usage(usage_obj) -> tuple[int | None, int | None, int | None]:
    """从 litellm 响应的 usage 结构里抠出三个 token 数,容错。"""
    if usage_obj is None:
        return None, None, None
    # litellm 可能给 dict / pydantic / 自定义对象,都用 getattr 取
    def _g(o, k):
        if isinstance(o, dict):
            return o.get(k)
        return getattr(o, k, None)

    pt = _g(usage_obj, "prompt_tokens")
    ct = _g(usage_obj, "completion_tokens")
    tt = _g(usage_obj, "total_tokens")
    if tt is None and pt is not None and ct is not None:
        tt = pt + ct
    return pt, ct, tt


def _persist_log(
    *,
    scene: str,
    cfg: RuntimeAIConfig,
    stream: bool,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    duration_ms: int,
    status: str,
    error: str | None,
    project_id: int | None,
) -> None:
    """写文件日志 + 落库。所有异常本地吃掉,记日志不应让主流程崩。"""
    payload = {
        "scene": scene,
        "model": cfg.model,
        "provider": cfg.provider,
        "stream": stream,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
        "status": status,
    }
    if error:
        payload["error"] = error
    if project_id is not None:
        payload["project_id"] = project_id

    try:
        get_ai_logger().info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass

    db = SessionLocal()
    try:
        row = AICallLog(
            scene=scene,
            model=cfg.model,
            provider=cfg.provider,
            stream=stream,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            status=status,
            error=error,
            project_id=project_id,
        )
        db.add(row)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


async def stream_chat(
    db: Session,
    messages: list[dict],
    *,
    scene: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    project_id: int | None = None,
) -> AsyncGenerator[str, None]:
    """流式 chat completion,只 yield 文本增量。"""
    cfg = resolve(db)
    kwargs = _build_kwargs(cfg)
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    kwargs["messages"] = messages
    kwargs["stream"] = True
    # 让 OpenAI 兼容 provider 在最后一个 chunk 给出 usage;
    # Anthropic / 其它 provider 不识别也会被 litellm 忽略
    kwargs["stream_options"] = {"include_usage": True}

    import litellm

    started = time.monotonic()
    prompt_tokens = completion_tokens = total_tokens = None
    status = "ok"
    err_text: str | None = None
    try:
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            # usage 可能挂在 chunk 自己上(OpenAI 风格的最终 chunk)或 chunk.choices[0]
            usage_attr = getattr(chunk, "usage", None)
            if usage_attr is not None:
                pt, ct, tt = _extract_usage(usage_attr)
                if pt is not None:
                    prompt_tokens = pt
                if ct is not None:
                    completion_tokens = ct
                if tt is not None:
                    total_tokens = tt
            try:
                delta = chunk.choices[0].delta
            except (AttributeError, IndexError):
                continue
            text = getattr(delta, "content", None)
            if text:
                yield text
    except Exception as e:
        status = "error"
        err_text = str(e)
        # 写完日志再抛,保证失败也有统计
        _persist_log(
            scene=scene,
            cfg=cfg,
            stream=True,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=int((time.monotonic() - started) * 1000),
            status=status,
            error=err_text,
            project_id=project_id,
        )
        raise AIError(err_text) from e

    _persist_log(
        scene=scene,
        cfg=cfg,
        stream=True,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        duration_ms=int((time.monotonic() - started) * 1000),
        status=status,
        error=err_text,
        project_id=project_id,
    )


async def complete(
    db: Session,
    messages: list[dict],
    *,
    scene: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    project_id: int | None = None,
) -> str:
    cfg = resolve(db)
    kwargs = _build_kwargs(cfg)
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    kwargs["messages"] = messages

    import litellm

    started = time.monotonic()
    prompt_tokens = completion_tokens = total_tokens = None
    status = "ok"
    err_text: str | None = None
    try:
        response = await litellm.acompletion(**kwargs)
        usage_attr = getattr(response, "usage", None)
        prompt_tokens, completion_tokens, total_tokens = _extract_usage(usage_attr)
        return response.choices[0].message.content or ""
    except Exception as e:
        status = "error"
        err_text = str(e)
        raise AIError(err_text) from e
    finally:
        _persist_log(
            scene=scene,
            cfg=cfg,
            stream=False,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=int((time.monotonic() - started) * 1000),
            status=status,
            error=err_text,
            project_id=project_id,
        )
