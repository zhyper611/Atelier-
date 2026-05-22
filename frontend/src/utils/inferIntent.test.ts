import { describe, expect, it } from "vitest";

import { intentFromActiveTool, intentFromToolResult } from "./inferIntent";

describe("inferIntent", () => {
  it("maps search tool from SSE", () => {
    expect(intentFromActiveTool("search")).toBe("search");
  });

  it("maps search tool result", () => {
    expect(
      intentFromToolResult({
        type: "search",
        content: "summary",
      }),
    ).toBe("search");
  });

  it("returns null for non-media tools", () => {
    expect(intentFromActiveTool("calc")).toBeNull();
  });
});
