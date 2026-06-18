from app.services.novel_split_service import split_novel_text


def test_empty_text() -> None:
    assert split_novel_text("") == []
    assert split_novel_text("   \n  ") == []


def test_no_chapter_marker_single_chapter() -> None:
    text = "这是一段没有章节标记的连续小说正文,占据多行。\n第二行内容。"
    chapters = split_novel_text(text)
    assert len(chapters) == 1
    # 无章节标记时,title 留空,前端会用「第 N 章」自动补足
    assert chapters[0].title == ""
    assert "没有章节标记" in chapters[0].content


def test_chinese_chapter_marker() -> None:
    text = "\n".join([
        "第一章 初出茅庐",
        "第一段正文。",
        "第二段正文。",
        "第二章 大显身手",
        "新章节正文。",
        "第三章 决战",
        "终章正文。",
    ])
    chapters = split_novel_text(text)
    assert len(chapters) == 3
    # title 只保留副标题部分,「第 N 章」由 order_index 自动生成
    assert chapters[0].title == "初出茅庐"
    assert chapters[1].title == "大显身手"
    assert chapters[2].title == "决战"
    assert "第一段正文" in chapters[0].content
    assert "新章节正文" in chapters[1].content


def test_chinese_chapter_with_arabic_number() -> None:
    text = "第1章 序章\nA\n第 2 章 中章\nB\n第10章 末章\nC"
    chapters = split_novel_text(text)
    assert [c.title for c in chapters] == ["序章", "中章", "末章"]


def test_chinese_complex_number() -> None:
    text = "第一百零一章 章名一\nA\n第二百三十五章 章名二\nB"
    chapters = split_novel_text(text)
    assert chapters[0].title == "章名一"
    assert chapters[1].title == "章名二"


def test_prelude_before_first_chapter() -> None:
    text = "这是序言段落,在第一章之前。\n\n第一章 开篇\n正文一。\n第二章 续\n正文二。"
    chapters = split_novel_text(text)
    assert len(chapters) == 3
    assert chapters[0].title == "序章"
    assert "序言段落" in chapters[0].content
    assert chapters[1].title == "开篇"


def test_markdown_heading_priority() -> None:
    """Markdown 标题优先于中文章回(即使两者并存)。"""
    text = "# 第一卷\n\n## 第一章 引子\n\n章节A\n\n## 第二章 进展\n\n章节B"
    chapters = split_novel_text(text)
    # # 第一卷 + ## 第一章 + ## 第二章 = 3 个标题命中
    assert len(chapters) == 3
    # 「第一卷」剥掉前缀后副标题为空
    assert chapters[0].title == ""
    assert chapters[1].title == "引子"


def test_english_chapter() -> None:
    text = "Chapter 1 Beginning\nbody one\nChapter 2: Middle\nbody two\nChapter 3\nbody three"
    chapters = split_novel_text(text)
    assert len(chapters) == 3
    assert chapters[0].title == "Beginning"
    assert chapters[1].title == "Middle"
    assert chapters[2].title == ""


def test_crlf_line_endings() -> None:
    text = "第一章 一\r\nA\r\n第二章 二\r\nB"
    chapters = split_novel_text(text)
    assert len(chapters) == 2
    assert "A" in chapters[0].content


def test_hui_marker_for_classical_novels() -> None:
    """红楼梦那种「第几回」也算章节。"""
    text = "第一回 甄士隐\n正文A\n第二回 贾雨村\n正文B"
    chapters = split_novel_text(text)
    assert len(chapters) == 2
    assert chapters[0].title == "甄士隐"
