import { describe, expect, it } from "vitest";

import { parseApiErrorMessage } from "./apiError";

describe("parseApiErrorMessage", () => {
  it("translates login failure detail", () => {
    const message = parseApiErrorMessage(
      401,
      JSON.stringify({ detail: "Invalid username or password" }),
    );
    expect(message).toBe("用户名或密码错误，请检查后重试");
  });

  it("translates duplicate username", () => {
    const message = parseApiErrorMessage(
      409,
      JSON.stringify({ detail: "username already exists" }),
    );
    expect(message).toBe("该用户名已被注册，请更换用户名或直接登录");
  });

  it("formats validation array", () => {
    const message = parseApiErrorMessage(
      422,
      JSON.stringify({
        detail: [
          {
            loc: ["body", "password"],
            msg: "String should have at least 8 characters",
            type: "string_too_short",
          },
        ],
      }),
    );
    expect(message).toContain("密码");
    expect(message).toContain("8");
  });

  it("falls back for empty body", () => {
    expect(parseApiErrorMessage(500, "")).toBe("服务暂时不可用，请稍后重试");
  });
});
