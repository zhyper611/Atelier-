import type { AttachmentRef } from "../api/types";

export type AttachmentKind = "image" | "document" | "video" | "audio" | "file";

export type AttachmentDisplayInfo = {
  kind: AttachmentKind;
  label: string;
  shortLabel: string;
};

export function attachmentKindFromMime(mimeType: string): AttachmentKind {
  if (mimeType.startsWith("image/")) {
    return "image";
  }
  if (mimeType.startsWith("video/")) {
    return "video";
  }
  if (mimeType.startsWith("audio/")) {
    return "audio";
  }
  if (
    mimeType === "application/pdf" ||
    mimeType === "text/plain" ||
    mimeType === "text/markdown"
  ) {
    return "document";
  }
  return "file";
}

export function attachmentDisplayInfo(mimeType: string): AttachmentDisplayInfo {
  const kind = attachmentKindFromMime(mimeType);
  const map: Record<AttachmentKind, AttachmentDisplayInfo> = {
    image: { kind, label: "图片", shortLabel: "图" },
    document: { kind, label: "文档", shortLabel: "文档" },
    video: { kind, label: "视频", shortLabel: "视频" },
    audio: { kind, label: "音频", shortLabel: "音频" },
    file: { kind, label: "文件", shortLabel: "文件" },
  };
  return map[kind];
}

export function formatAttachmentSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function buildPreviewMap(
  files: File[],
  refs: AttachmentRef[],
): Record<string, string> {
  const previews: Record<string, string> = {};
  const count = Math.min(files.length, refs.length);
  for (let index = 0; index < count; index += 1) {
    const file = files[index];
    const ref = refs[index];
    if (file && ref.mime_type.startsWith("image/")) {
      previews[ref.id] = URL.createObjectURL(file);
    }
  }
  return previews;
}

export function revokePreviewMap(previews: Record<string, string> | undefined) {
  if (!previews) {
    return;
  }
  for (const url of Object.values(previews)) {
    URL.revokeObjectURL(url);
  }
}
