"""style_signals 单元测试 — 纯本地计算,不需要 client/db。"""

from app.services import style_signals


def test_empty_text_safe():
    s = style_signals.compute_signals("")
    assert s["char_count"] == 0
    assert s["sentence"]["count"] == 0
    assert s["paragraph"]["count"] == 0
    assert s["vocab_richness"] == 0.0


def test_sentence_split_chinese():
    s = style_signals.compute_signals("他来了。她笑了!真的吗?")
    assert s["sentence"]["count"] == 3
    assert s["sentence"]["mean_len"] > 0


def test_paragraph_split_blank_line():
    text = "第一段第一句。第一段第二句。\n\n第二段。\n\n第三段。"
    s = style_signals.compute_signals(text)
    assert s["paragraph"]["count"] == 3


def test_vocab_richness_more_diverse_higher():
    repetitive = "啊" * 100
    diverse = "天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏"
    s_rep = style_signals.compute_signals(repetitive)
    s_div = style_signals.compute_signals(diverse)
    assert s_div["vocab_richness"] > s_rep["vocab_richness"]
    # 完全重复时丰富度应该接近 1/字符数(=0.01)
    assert s_rep["vocab_richness"] < 0.05


def test_dialogue_ratio_detects_quotes():
    # 用 unicode 转义避免文件保存时被编码乱码 — 「 是「,」 是」
    text = "「你来了。」\n\n他点点头。\n\n「真的？」"
    s = style_signals.compute_signals(text)
    assert s["paragraph"]["count"] == 3
    # 3 段里 2 段引号开头
    assert s["dialogue_ratio"] > 0.5


def test_stdev_zero_when_sentences_uniform():
    # 4 句长度都相同,方差应为 0
    text = "一二三四。一二三四。一二三四。一二三四。"
    s = style_signals.compute_signals(text)
    assert s["sentence"]["count"] == 4
    assert s["sentence"]["stdev_len"] == 0.0


def test_percentiles_monotonic():
    # 句长 5/10/15/20/25,p10 应在低位,p90 在高位
    sentences = [
        "一二三四五。",
        "一二三四五六七八九十。",
        "一二三四五六七八九十一二三四五。",
        "一二三四五六七八九十一二三四五六七八九十。",
        "一二三四五六七八九十一二三四五六七八九十一二三四五。",
    ]
    s = style_signals.compute_signals("".join(sentences))
    sent = s["sentence"]
    assert sent["p10"] <= sent["p50"] <= sent["p90"]


def test_punctuation_ratio_in_zero_one():
    text = "一段普通的中文,带几个标点。还有一句!"
    s = style_signals.compute_signals(text)
    assert 0 <= s["punctuation_ratio"] <= 1
    assert s["punctuation_ratio"] > 0
