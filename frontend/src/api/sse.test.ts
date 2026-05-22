import { describe, expect, it } from "vitest";

import { parseSseChunk } from "./client";

describe("parseSseChunk", () => {
  it("parses named SSE events with JSON payloads", () => {
    const result = parseSseChunk(
      'event: delta\ndata: {"text":"hello"}\n\nevent: final\ndata: {"answer":"done"}\n\n',
    );

    expect(result.events).toEqual([
      { event: "delta", data: { text: "hello" } },
      { event: "final", data: { answer: "done" } },
    ]);
    expect(result.remainder).toBe("");
  });

  it("keeps incomplete events as a remainder", () => {
    const result = parseSseChunk('event: delta\ndata: {"text":"hel');

    expect(result.events).toEqual([]);
    expect(result.remainder).toBe('event: delta\ndata: {"text":"hel');
  });
});
