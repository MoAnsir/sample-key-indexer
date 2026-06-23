import type { Sample } from "../types/api";

export function uniqueValues(samples: Sample[], key: keyof Sample): string[] {
  const set = new Set<string>();
  for (const s of samples) {
    const v = s[key];
    if (v != null && v !== "") set.add(String(v));
  }
  return [...set].sort();
}
