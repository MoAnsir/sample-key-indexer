// The File System Access API (showDirectoryPicker) can't provide full
// filesystem paths to send to the backend — it only gives a handle name.
// Since this is a local tool, users paste/type paths directly.
// This module provides validation helpers.

export function isAbsolutePath(path: string): boolean {
  return path.startsWith("/") || /^[A-Z]:\\/i.test(path);
}

export function normalizePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/\/+$/, "");
}

export function suggestLibraryId(path: string): string {
  const normalized = normalizePath(path);
  const lastPart = normalized.split("/").pop() ?? "library";
  return lastPart.replace(/[^a-zA-Z0-9_-]/g, "_").toLowerCase();
}
