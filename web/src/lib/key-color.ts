/* ============================================================
   KEY INDEX — Pitch-class colour system
   ------------------------------------------------------------
   Every musical key gets ONE stable colour, derived from its
   position on the circle of fifths. Use these everywhere a key
   appears (table chips, dots, the circle-of-fifths wheel, the
   detail badge) so users learn to read keys by colour.

   Hue  = position on the circle of fifths  (C=0°, G=30°, D=60° …)
   so harmonically-near keys sit near each other in hue too.
   Lightness/chroma are tuned per mode (minor a touch darker)
   and per theme (lighter ink on dark backgrounds).

   Colours are emitted as oklch() — supported in all current
   browsers. If you must support old engines, pre-convert to hex.
   ============================================================ */

// Clockwise circle of fifths, starting at C (top of the wheel).
export const CIRCLE_OF_FIFTHS = [
  'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F',
] as const;

export type Mode = 'major' | 'minor';

export interface KeyColor {
  /** Solid fill — dots, wheel wedges, the active key. */
  solid: string;
  /** Translucent fill — chip backgrounds. */
  bg: string;
  /** Readable text colour for use on `bg`. */
  ink: string;
  /** Hairline / outline colour. */
  border: string;
}

/**
 * Colour for a musical key.
 * @param root  e.g. "D", "F#"  (sharp spelling). null/"" → neutral grey.
 * @param mode  "major" | "minor"
 * @param dark  true when the active theme is dark.
 */
export function keyColor(
  root: string | null,
  mode: Mode = 'minor',
  dark = false,
): KeyColor {
  if (!root) {
    return dark
      ? { solid: '#6f6a60', bg: 'rgba(255,255,255,.07)', ink: '#a39d92', border: 'rgba(255,255,255,.16)' }
      : { solid: '#a9a499', bg: 'rgba(160,156,148,.14)', ink: '#79756c', border: 'rgba(160,156,148,.3)' };
  }

  const idx = CIRCLE_OF_FIFTHS.indexOf(root as (typeof CIRCLE_OF_FIFTHS)[number]);
  const hue = Math.round((Math.max(idx, 0) / 12) * 360);
  const L = mode === 'minor' ? 0.64 : 0.70;
  const C = mode === 'minor' ? 0.12 : 0.13;

  return {
    solid:  `oklch(${dark ? L + 0.06 : L} ${C} ${hue})`,
    bg:     `oklch(${L} ${C} ${hue} / ${dark ? 0.22 : 0.15})`,
    ink:    dark ? `oklch(0.82 ${C} ${hue})` : `oklch(0.46 ${C + 0.03} ${hue})`,
    border: `oklch(${L} ${C} ${hue} / ${dark ? 0.4 : 0.35})`,
  };
}

/** Convenience: parse a stored key string like "D_minor" → {root, mode}. */
export function parseKey(key: string | null): { root: string | null; mode: Mode } {
  if (!key) return { root: null, mode: 'minor' };
  const [root, mode] = key.split('_');
  return { root, mode: mode === 'major' ? 'major' : 'minor' };
}
