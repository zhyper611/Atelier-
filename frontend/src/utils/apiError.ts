/** 将 FastAPI / 网关返回体解析为可读的中文提示 */

const DETAIL_ZH: Record<string, string> = {
  "Invalid username or password": "用户名或密码错误，请检查后重试",
  "用户名或密码错误": "用户名或密码错误，请检查后重试",
  "username already exists": "该用户名已被注册，请更换用户名或直接登录",
  "用户名已被注册": "该用户名已被注册，请更换用户名或直接登录",
  "Not authenticated": "登录已失效，请重新登录",
  "Invalid or expired token": "登录已过期，请重新登录",
  "Invalid or missing API key": "服务鉴权失败，请联系管理员",
};

const VALIDATION_ZH: Record<string, string> = {
  "String should have at least 8 characters": "密码至少需要 8 个字符",
  "String should have at least 3 characters": "用户名至少需要 3 个字符",
  "String should have at most 32 characters": "用户名不能超过 32 个字符",
  "Field required": "请填写完整信息",
  "value is not a valid": "输入格式不正确",
};

type ValidationItem = {
  msg?: string;
  loc?: (string | number)[];
  type?: string;
};

function translateDetail(detail: string): string {
  const trimmed = detail.trim();
  if (DETAIL_ZH[trimmed]) {
    return DETAIL_ZH[trimmed];
  }
  for (const [key, zh] of Object.entries(VALIDATION_ZH)) {
    if (trimmed.includes(key)) {
      return zh;
    }
  }
  return trimmed;
}

function fieldLabel(loc: (string | number)[] | undefined): string | null {
  if (!loc || loc.length === 0) {
    return null;
  }
  const field = String(loc[loc.length - 1]);
  if (field === "username") {
    return "用户名";
  }
  if (field === "password") {
    return "密码";
  }
  return null;
}

function formatValidationItem(item: ValidationItem): string {
  const label = fieldLabel(item.loc);
  const msg = item.msg ? translateDetail(item.msg) : "输入不符合要求";
  if (label) {
    return `${label}：${msg}`;
  }
  return msg;
}

function parseJsonBody(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export function parseApiErrorMessage(status: number, bodyText: string): string {
  const trimmed = bodyText.trim();
  if (!trimmed) {
    return statusHint(status);
  }

  const parsed = parseJsonBody(trimmed);
  if (parsed && typeof parsed === "object" && parsed !== null && "detail" in parsed) {
    const detail = (parsed as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return translateDetail(detail);
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const lines = detail
        .filter((item): item is ValidationItem => typeof item === "object" && item !== null)
        .map(formatValidationItem);
      if (lines.length > 0) {
        return lines.join("；");
      }
    }
  }

  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    return statusHint(status);
  }

  return trimmed.length > 120 ? statusHint(status) : trimmed;
}

function statusHint(status: number): string {
  if (status === 401) {
    return "登录已过期，请重新登录";
  }
  if (status === 409) {
    return "该用户名已被注册，请更换用户名或直接登录";
  }
  if (status === 422) {
    return "提交的信息不符合要求，请检查用户名和密码";
  }
  if (status === 413) {
    return "文件过大，请缩小后重试";
  }
  if (status === 429) {
    return "请求过于频繁，请稍后再试";
  }
  if (status >= 500) {
    return "服务暂时不可用，请稍后重试";
  }
  return "操作失败，请稍后重试";
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function apiErrorFromResponse(status: number, bodyText: string): ApiError {
  return new ApiError(status, parseApiErrorMessage(status, bodyText));
}
