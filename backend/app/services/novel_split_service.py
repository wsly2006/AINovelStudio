"""把整段小说文本按章节标题切分。

支持的章节标记(按优先级):
1. Markdown 一/二级标题(# / ##),整文出现 >= 2 次才生效
2. 中文章回:第一章 / 第1章 / 第 1 章 / 第一回 / 第百零一章 等,行首
3. 英文章节:Chapter 1 / Chapter One,行首,大小写不敏感

未识别到章节标记时,整文作为单章返回。
拆分严格按行处理,不破坏正文格式。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 中文数字 → 阿拉伯数字(支持到「九千九百九十九」量级,够用)
_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "壹": 1, "贰": 2, "叁": 3,
             "肆": 4, "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9, "两": 2}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000, "拾": 10, "佰": 100, "仟": 1000}

# 行首中文章回:「第」+ 数字/中文数字 + 「章/回/节/卷」+ 可选标题
_RE_CN_CHAPTER = re.compile(
    r"^\s*第\s*([0-9一二三四五六七八九十百千万零壹贰叁肆伍陆柒捌玖拾佰仟两]+)\s*[章回节卷篇]\s*[:：]?\s*(.*?)\s*$"
)
# 行首英文章节:Chapter 1 / Chapter One / CHAPTER I
_RE_EN_CHAPTER = re.compile(
    r"^\s*chapter\s+([0-9]+|[ivxlcdm]+|[a-z]+)\s*[:.\-]?\s*(.*?)\s*$",
    re.IGNORECASE,
)
# Markdown 一级/二级标题(# 或 ##)
_RE_MD_HEADING = re.compile(r"^\s*(#{1,2})\s+(.+?)\s*#*\s*$")


@dataclass
class ParsedChapter:
    title: str
    content: str  # 不含标题行


def _cn_to_int(s: str) -> int | None:
    """把中文数字串转成 int。失败返回 None。
    支持 一二三 / 十一 / 二十一 / 一百零一 / 一千零八 等常见写法。
    """
    if not s:
        return None
    if s.isdigit():
        return int(s)

    total = 0
    section = 0  # 当前节(万以下)的累积值
    current = 0  # 等待下一个单位的数字
    for ch in s:
        if ch in _CN_DIGIT:
            current = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            if unit == 10000:
                section = (section + (current or 1)) * unit
                total += section
                section = 0
                current = 0
            else:
                # 「十」直接出现表示 10
                section += (current or 1) * unit
                current = 0
        else:
            return None
    return total + section + current


def _detect_md_headings(lines: list[str]) -> list[int]:
    """返回 Markdown 标题所在行号(0-based)。少于 2 个不算。"""
    hits = [i for i, ln in enumerate(lines) if _RE_MD_HEADING.match(ln)]
    return hits if len(hits) >= 2 else []


def _detect_cn_chapters(lines: list[str]) -> list[int]:
    return [i for i, ln in enumerate(lines) if _RE_CN_CHAPTER.match(ln)]


def _detect_en_chapters(lines: list[str]) -> list[int]:
    return [i for i, ln in enumerate(lines) if _RE_EN_CHAPTER.match(ln)]


def _build_chapters(lines: list[str], heads: list[int], titler) -> list[ParsedChapter]:
    """按命中行号切片,titler(line) 返回章节副标题(不含「第 N 章」前缀)。"""
    chapters: list[ParsedChapter] = []
    # 第一段头部正文(可能是序言),命中行前的内容若非空则作为「序章」
    if heads and heads[0] > 0:
        prelude = "\n".join(lines[: heads[0]]).strip()
        if prelude:
            chapters.append(ParsedChapter(title="序章", content=prelude))

    for idx, start in enumerate(heads):
        end = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
        title = titler(lines[start])
        body = "\n".join(lines[start + 1 : end]).strip()
        chapters.append(ParsedChapter(title=title, content=body))
    return chapters


# 用于从 Markdown 标题文本里剥掉「第 N 章」/ "Chapter N" 这种已有前缀
_RE_MD_TITLE_CN_PREFIX = re.compile(
    r"^\s*第\s*[0-9一二三四五六七八九十百千万零壹贰叁肆伍陆柒捌玖拾佰仟两]+\s*[章回节卷篇]\s*[:：]?\s*"
)
_RE_MD_TITLE_EN_PREFIX = re.compile(
    r"^\s*chapter\s+(?:[0-9]+|[ivxlcdm]+|[a-z]+)\s*[:.\-]?\s*",
    re.IGNORECASE,
)


def _title_from_md(line: str) -> str:
    m = _RE_MD_HEADING.match(line)
    if not m:
        return ""
    raw = m.group(2).strip()
    raw = _RE_MD_TITLE_CN_PREFIX.sub("", raw)
    raw = _RE_MD_TITLE_EN_PREFIX.sub("", raw)
    return raw.strip()


def _title_from_cn(line: str) -> str:
    m = _RE_CN_CHAPTER.match(line)
    if not m:
        return ""
    return m.group(2).strip()


def _title_from_en(line: str) -> str:
    m = _RE_EN_CHAPTER.match(line)
    if not m:
        return ""
    return m.group(2).strip()


def split_novel_text(text: str) -> list[ParsedChapter]:
    """把小说原文切成章节列表。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return []

    lines = text.split("\n")

    # 三种模式按优先级尝试
    md_heads = _detect_md_headings(lines)
    if md_heads:
        return _build_chapters(lines, md_heads, _title_from_md)

    cn_heads = _detect_cn_chapters(lines)
    if cn_heads:
        return _build_chapters(lines, cn_heads, _title_from_cn)

    en_heads = _detect_en_chapters(lines)
    if en_heads:
        return _build_chapters(lines, en_heads, _title_from_en)

    # 无章节标记,整文作为单章
    body = text.strip()
    return [ParsedChapter(title="", content=body)]
