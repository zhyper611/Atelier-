import type { IntentType, ToolResult } from "../api/types";

/** 与后端 loop._tool_sse_name 发出的 SSE tool 名一致 */
const ACTIVE_TOOL_INTENT: Record<string, IntentType> = {
  search: "search",
  image: "image",
  video: "video",
  knowledge: "chat",
};

const TOOL_RESULT_INTENT: Partial<Record<ToolResult["type"], IntentType>> = {
  search: "search",
  image: "image",
  video: "video",
};

export function intentFromActiveTool(tool: string): IntentType | null {
  return ACTIVE_TOOL_INTENT[tool] ?? null;
}

export function intentFromToolResult(result: ToolResult): IntentType | null {
  return TOOL_RESULT_INTENT[result.type] ?? null;
}
