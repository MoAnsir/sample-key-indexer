import type { Sample } from "../types/api";

export function getSampleField(sample: Sample, key: string): unknown {
  return (sample as never)[key];
}
