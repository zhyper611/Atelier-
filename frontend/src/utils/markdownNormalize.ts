/**
 * LLM 输出常把标题、列表写在同一行（如 "汇总： ### 1. 标题 * **条目"），
 * 标准 Markdown 需要换行才能解析。渲染前做轻量规范化。
 */
export function normalizeAssistantMarkdown(text: string): string {
  let result = text.replace(/\r\n/g, "\n").trim();
  if (!result) {
    return result;
  }

  // 标题前补空行（### / ## / #）
  result = result.replace(/([^\n])\s*(#{1,6}\s+)/g, "$1\n\n$2");

  // 标题行后直接跟无序列表
  result = result.replace(/(#{1,6}\s+[^\n]+?)\s+(\*\s)/g, "$1\n\n$2");

  // 句号、冒号等后接无序列表（允许无空格，如 "内容。* **"）
  result = result.replace(/([。：；!?！？])\s*(\*\s)/g, "$1\n\n$2");

  // 普通文字与列表项之间（如 "技术创新 * **谷歌"）
  result = result.replace(/([^\n*])\s+(\*\s+(?:\*\*|[\u4e00-\u9fffA-Za-z0-9]))/g, "$1\n\n$2");

  // 合并多余空行
  result = result.replace(/\n{3,}/g, "\n\n");

  return result;
}
