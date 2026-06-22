import type { CatalogResponse, Sample, SampleDetail } from "../types/api";

const BASE = "";

export async function fetchCatalog(): Promise<CatalogResponse> {
  const res = await fetch(`${BASE}/api/catalog`);
  if (!res.ok) throw new Error(`catalog: ${res.status}`);
  return res.json();
}

export interface SamplesResponse {
  total: number;
  offset: number;
  limit: number;
  returned: number;
  samples: Sample[];
}

export async function fetchSamples(
  libraryId: string,
  offset: number = 0,
  limit: number = 15000,
): Promise<SamplesResponse> {
  const params = new URLSearchParams({
    library_id: libraryId,
    offset: String(offset),
    limit: String(limit),
  });
  const res = await fetch(`${BASE}/api/samples?${params}`);
  if (!res.ok) throw new Error(`samples: ${res.status}`);
  return res.json();
}

export async function fetchSampleDetail(id: number): Promise<SampleDetail> {
  const res = await fetch(`${BASE}/api/sample?id=${id}`);
  if (!res.ok) throw new Error(`sample detail: ${res.status}`);
  const data = await res.json();
  return (data.sample ?? data) as SampleDetail;
}

export function getAudioUrl(id: number): string {
  return `${BASE}/api/audio?id=${id}`;
}

export function getMidiUrl(id: number, progressionIndex: number): string {
  return `${BASE}/api/sample-midi?id=${id}&progression=${progressionIndex}`;
}

export async function postReview(
  id: number,
  reviewed: boolean,
): Promise<void> {
  const res = await fetch(`${BASE}/api/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, reviewed }),
  });
  if (!res.ok) throw new Error(`review: ${res.status}`);
}
