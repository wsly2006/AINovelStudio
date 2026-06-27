"""章节文本统计信号 — 纯本地计算,不调 LLM。

提供"AI 痕迹"的可量化参考,作为 chapter_style_check 主观判罚的客观补充。
目标是给作者**知情决策**,不做"刷分到阈值以下"那种闭环。

设计取舍:
- 全部用 stdlib,不引入分词依赖(jieba 等)
- 中文按字符级统计;无法精准识别"词",但能反映多样性趋势
- 信号都标了 hint,前端直接用,不需要二次翻译
"""

from __future__ import annotations

import math
import re
from typing import Any

# 中文句末标点 + 英文句末标点
_SENT_RE = re.compile(r"[^。!?!?…\.\n]+(?:[。!?!?…\.])?")
# 段落分隔:连续换行(允许夹空白)
_PARA_RE = re.compile(r"\n\s*\n")
# 整体标点:中文常见 + 英文
_PUNCT_CHARS = set("。,!?:;""''《》、…—,.!?;:\"'()()[]【】")
# 引号开头的行视作对话行 — 覆盖中英文常见引号
_DIALOGUE_RE = re.compile(r"^\s*[“”‘’「」『』\"']")


def _stdev(values: list[int]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def _percentile(sorted_values: list[int], p: float) -> int:
    if not sorted_values:
        return 0
    k = (len(sorted_values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    # 线性插值后取整,前端展示用整数更直观
    d = sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)
    return int(round(d))


def _split_sentences(text: str) -> list[str]:
    # 去掉空白条目,保留有内容的句子
    out: list[str] = []
    for m in _SENT_RE.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append(s)
    return out


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in _PARA_RE.split(text) if p.strip()]


def compute_signals(text: str) -> dict[str, Any]:
    """从章节正文算出客观风格信号。

    返回字段都是"轻量、可解释、跨章节可对比"的标量,避免黑盒分数。
    """
    text = text or ""
    char_count = len(text)
    if char_count == 0:
        return {
            "char_count": 0,
            "sentence": {"count": 0, "mean_len": 0.0, "stdev_len": 0.0, "p10": 0, "p50": 0, "p90": 0},
            "paragraph": {"count": 0, "mean_len": 0.0, "stdev_len": 0.0},
            "vocab_richness": 0.0,
            "punctuation_ratio": 0.0,
            "dialogue_ratio": 0.0,
        }

    sentences = _split_sentences(text)
    sent_lens = [len(s) for s in sentences]
    sent_lens_sorted = sorted(sent_lens)

    paragraphs = _split_paragraphs(text)
    para_lens = [len(p) for p in paragraphs]

    # 字符级"词汇丰富度":去重字符数 / 总有效字符数(剔除空白)
    non_ws = [c for c in text if not c.isspace()]
    unique_chars = len(set(non_ws))
    vocab_richness = (unique_chars / len(non_ws)) if non_ws else 0.0

    # 标点占比
    punct_count = sum(1 for c in text if c in _PUNCT_CHARS)
    punct_ratio = punct_count / char_count if char_count else 0.0

    # 对白占比(按段落计):段首是引号的算对白
    dialogue_paras = sum(1 for p in paragraphs if _DIALOGUE_RE.match(p))
    dialogue_ratio = (dialogue_paras / len(paragraphs)) if paragraphs else 0.0

    return {
        "char_count": char_count,
        "sentence": {
            "count": len(sentences),
            "mean_len": round(sum(sent_lens) / len(sent_lens), 2) if sent_lens else 0.0,
            "stdev_len": round(_stdev(sent_lens), 2),
            "p10": _percentile(sent_lens_sorted, 0.1),
            "p50": _percentile(sent_lens_sorted, 0.5),
            "p90": _percentile(sent_lens_sorted, 0.9),
        },
        "paragraph": {
            "count": len(paragraphs),
            "mean_len": round(sum(para_lens) / len(para_lens), 2) if para_lens else 0.0,
            "stdev_len": round(_stdev(para_lens), 2),
        },
        "vocab_richness": round(vocab_richness, 4),
        "punctuation_ratio": round(punct_ratio, 4),
        "dialogue_ratio": round(dialogue_ratio, 4),
    }
