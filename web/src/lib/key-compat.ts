import { parseKey } from "./key-color";

const NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

function noteIndex(note: string): number {
  return NOTES.indexOf(note);
}

function relativeKey(root: string, mode: string): string {
  const idx = noteIndex(root);
  if (idx < 0) return "";
  if (mode === "minor") return NOTES[(idx + 3) % 12] + "_major";
  return NOTES[(idx + 9) % 12] + "_minor";
}

function dominantKey(root: string, mode: string): string {
  const idx = noteIndex(root);
  if (idx < 0) return "";
  return NOTES[(idx + 7) % 12] + "_" + mode;
}

function subdominantKey(root: string, mode: string): string {
  const idx = noteIndex(root);
  if (idx < 0) return "";
  return NOTES[(idx + 5) % 12] + "_" + mode;
}

function parallelKey(root: string, mode: string): string {
  return root + "_" + (mode === "major" ? "minor" : "major");
}

export type FitLevel = "same" | "compatible" | "out" | "none";

export function checkFit(sampleKey: string | null, projectKey: string | null): FitLevel {
  if (!projectKey) return "none";
  if (!sampleKey) return "none";

  if (sampleKey === projectKey) return "same";

  const proj = parseKey(projectKey);
  if (!proj.root) return "none";

  const compatibleKeys = new Set([
    relativeKey(proj.root, proj.mode),
    dominantKey(proj.root, proj.mode),
    subdominantKey(proj.root, proj.mode),
    parallelKey(proj.root, proj.mode),
  ]);

  if (compatibleKeys.has(sampleKey)) return "compatible";

  return "out";
}

export function fitLabel(fit: FitLevel): string {
  switch (fit) {
    case "same": return "Same key";
    case "compatible": return "Compatible";
    case "out": return "Out of key";
    case "none": return "No key";
  }
}
