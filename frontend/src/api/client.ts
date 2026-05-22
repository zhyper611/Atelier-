import type {
  AttachmentUploadResponse,
  AuthTokenResponse,
  ChatRequest,
  ChatResponse,
  IndexDocumentResponse,
  KnowledgeDocumentListResponse,
  SessionHistoryResponse,
  SseEvent,
  SseEventName,
  User,
} from "./types";
import { apiErrorFromResponse } from "../utils/apiError";
import { getAccessToken } from "../utils/authToken";

const API_BASE = "/api";

function apiHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const apiKey = import.meta.env.VITE_API_KEY;
  if (typeof apiKey === "string" && apiKey.trim()) {
    headers["X-API-Key"] = apiKey.trim();
  }
  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return { ...headers, ...extra };
}

function uploadHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const apiKey = import.meta.env.VITE_API_KEY;
  if (typeof apiKey === "string" && apiKey.trim()) {
    headers["X-API-Key"] = apiKey.trim();
  }
  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export type ParseSseResult = {
  events: SseEvent[];
  remainder: string;
};

export function parseSseChunk(buffer: string): ParseSseResult {
  const blocks = buffer.split("\n\n");
  const remainder = blocks.pop() ?? "";
  const events: SseEvent[] = [];

  for (const block of blocks) {
    const trimmed = block.trim();
    if (!trimmed) {
      continue;
    }

    let eventName = "message";
    let dataLine = "";

    for (const line of trimmed.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLine = line.slice(5).trim();
      }
    }

    if (!dataLine) {
      continue;
    }

    try {
      events.push({
        event: eventName as SseEventName,
        data: JSON.parse(dataLine) as Record<string, unknown>,
      });
    } catch {
      // skip malformed JSON
    }
  }

  return { events, remainder };
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: apiHeaders(init?.headers),
  });

  if (!response.ok) {
    const text = await response.text();
    throw apiErrorFromResponse(response.status, text);
  }

  return response.json() as Promise<T>;
}

export async function register(
  username: string,
  password: string,
): Promise<AuthTokenResponse> {
  return requestJson("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function login(
  username: string,
  password: string,
): Promise<AuthTokenResponse> {
  return requestJson("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe(): Promise<User> {
  return requestJson("/auth/me");
}

export async function sendChat(body: ChatRequest): Promise<ChatResponse> {
  return requestJson("/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getSession(sessionId: string): Promise<SessionHistoryResponse> {
  return requestJson(`/sessions/${encodeURIComponent(sessionId)}`);
}

export async function clearSession(sessionId: string): Promise<{ deleted: boolean }> {
  return requestJson(`/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

export async function listKnowledgeDocuments(): Promise<KnowledgeDocumentListResponse> {
  return requestJson("/knowledge/documents");
}

export async function uploadKnowledgeDocuments(
  files: File[],
): Promise<IndexDocumentResponse[]> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const response = await fetch(`${API_BASE}/knowledge/documents`, {
    method: "POST",
    headers: uploadHeaders(),
    body: form,
  });
  if (!response.ok) {
    const text = await response.text();
    throw apiErrorFromResponse(response.status, text);
  }
  return response.json() as Promise<IndexDocumentResponse[]>;
}

export async function deleteKnowledgeDocument(docId: string): Promise<{ deleted: boolean }> {
  return requestJson(`/knowledge/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
}

export async function indexAttachmentToKnowledge(
  sessionId: string,
  attachmentId: string,
): Promise<IndexDocumentResponse> {
  return requestJson("/knowledge/documents/from-attachment", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, attachment_id: attachmentId }),
  });
}

export async function uploadAttachments(
  sessionId: string,
  files: File[],
): Promise<AttachmentUploadResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }

  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/attachments`,
    {
      method: "POST",
      headers: uploadHeaders(),
      body: form,
    },
  );

  if (!response.ok) {
    const text = await response.text();
    throw apiErrorFromResponse(response.status, text);
  }

  return response.json() as Promise<AttachmentUploadResponse>;
}

export async function streamChat(
  body: ChatRequest,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: apiHeaders(),
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const text = await response.text();
    throw apiErrorFromResponse(response.status, text);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Streaming body is not available");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: ChatResponse | null = null;

  while (true) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.remainder;

    for (const event of parsed.events) {
      onEvent(event);
      if (event.event === "final") {
        finalResponse = event.data as unknown as ChatResponse;
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      onEvent(event);
      if (event.event === "final") {
        finalResponse = event.data as unknown as ChatResponse;
      }
    }
  }

  if (!finalResponse) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    throw new Error("Stream ended without a final event");
  }

  return finalResponse;
}
