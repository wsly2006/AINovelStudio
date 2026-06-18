"""集中式日志配置。

策略:按天 + 单文件大小双触发滚动
- 主路径:data/logs/ai-YYYY-MM-DD.log
- 同日单文件超过 MAX_BYTES(20MB)→ ai-YYYY-MM-DD.1.log / .2.log ...
- 跨天 → 自动切到新日期
- 保留最近 RETAIN_DAYS(30)天

只暴露一个命名 logger:`ai.calls`,专门记 LLM 调用统计。其它模块以后要加
日志,直接用 `logging.getLogger(__name__)` 走 root,会同时输出到控制台和当日
文件。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from app.config import DATA_DIR

LOG_DIR: Path = DATA_DIR / "logs"
MAX_BYTES = 20 * 1024 * 1024  # 单文件 20MB
RETAIN_DAYS = 30

_AI_LOGGER_NAME = "ai.calls"


class _DailyRotatingHandler(logging.Handler):
    """按天 + 按大小滚动的简易 handler。

    没用 stdlib 的 TimedRotatingFileHandler 是因为它的"按时间 + 按大小"两个
    策略不能叠加,要么按天后缀,要么按大小后缀,不能两个一起。这里实现的版本
    优先按日期分文件,日期不变时若超过 MAX_BYTES 则用 .N 后缀分卷。
    """

    def __init__(self, log_dir: Path, max_bytes: int = MAX_BYTES) -> None:
        super().__init__()
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self._stream = None
        self._current_path: Path | None = None
        self._current_date: date | None = None

    def _today(self) -> date:
        # 用本地时间;跨日靠系统时钟,够用
        return datetime.now().date()

    def _resolve_path(self, today: date) -> Path:
        base = self.log_dir / f"ai-{today.isoformat()}.log"
        if not base.exists() or base.stat().st_size < self.max_bytes:
            return base
        # 找下一个可用的 .N
        n = 1
        while True:
            cand = self.log_dir / f"ai-{today.isoformat()}.{n}.log"
            if not cand.exists() or cand.stat().st_size < self.max_bytes:
                return cand
            n += 1

    def _open_if_needed(self) -> None:
        today = self._today()
        path = self._resolve_path(today)
        if self._stream is not None and self._current_path == path:
            return
        # 关旧的,开新的
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._stream = open(path, "a", encoding="utf-8")
        self._current_path = path
        self._current_date = today

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            self._open_if_needed()
            msg = self.format(record)
            assert self._stream is not None
            self._stream.write(msg + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        try:
            if self._stream is not None:
                self._stream.close()
        finally:
            super().close()


def _purge_old_logs(log_dir: Path, retain_days: int) -> None:
    """删除超过 retain_days 天的日志文件。失败静默。"""
    if not log_dir.exists():
        return
    today = datetime.now().date()
    for p in log_dir.glob("ai-*.log"):
        try:
            stem = p.stem  # ai-YYYY-MM-DD 或 ai-YYYY-MM-DD.N
            date_str = stem[3:13]  # 取 YYYY-MM-DD 子串
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            if (today - d).days > retain_days:
                p.unlink(missing_ok=True)
        except Exception:
            continue


_configured = False


def setup_logging() -> None:
    """应用启动时调用一次。重复调用幂等。"""
    global _configured
    if _configured:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _purge_old_logs(LOG_DIR, RETAIN_DAYS)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler:落到 data/logs/ai-*.log
    file_handler = _DailyRotatingHandler(LOG_DIR)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    # 控制台 handler:开发时看流水
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(fmt)

    # AI 调用统计专用 logger,不向 root 冒泡(避免重复打印)
    ai_logger = logging.getLogger(_AI_LOGGER_NAME)
    ai_logger.setLevel(logging.INFO)
    ai_logger.handlers = [file_handler, stream_handler]
    ai_logger.propagate = False

    _configured = True


def get_ai_logger() -> logging.Logger:
    return logging.getLogger(_AI_LOGGER_NAME)
