import { describe, expect, it } from "vitest";

import { normalizeAssistantMarkdown } from "./markdownNormalize";

describe("normalizeAssistantMarkdown", () => {
  it("inserts line breaks before inline headings and list items", () => {
    const input =
      "以下是当天的 AI 相关新闻汇总： ### 1. 大模型与技术创新 * **谷歌发布 Gemini 3.5 系列：** 介绍内容。* **OpenAI 引入水印技术：** 更多内容。";

    const output = normalizeAssistantMarkdown(input);

    expect(output).toContain("汇总：\n\n### 1. 大模型与技术创新");
    expect(output).toContain("技术创新\n\n* **谷歌发布");
    expect(output).toContain("介绍内容。\n\n* **OpenAI");
  });
});
