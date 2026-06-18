// 章节标题统一拼接:
// 「第 N 章」前缀由 order_index 自动生成,作者只填副标题(可空)
// 显示和导出时把两部分拼起来,空副标题时只展示前缀
export function formatChapterPrefix(orderIndex, t) {
  return t('workspace.chapterPrefix', { n: orderIndex || 0 })
}

export function formatChapterFullTitle(chapter, t) {
  if (!chapter) return ''
  const prefix = formatChapterPrefix(chapter.order_index, t)
  const sub = (chapter.title || '').trim()
  return sub ? `${prefix} ${sub}` : prefix
}
