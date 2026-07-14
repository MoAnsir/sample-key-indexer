import { describe, it, expect } from "vitest";
import { server } from "../test/mocks/server";
import { http, HttpResponse } from "msw";
import {
  fetchCatalog,
  fetchSamples,
  fetchSampleDetail,
  postReview,
  browseFolders,
  getAudioUrl,
  getMidiUrl,
} from "./client";

describe("fetchCatalog", () => {
  it("returns catalog data", async () => {
    const data = await fetchCatalog();
    expect(data.total).toBe(3);
    expect(data.libraries).toHaveLength(2);
    expect(data.libraries[0].id).toBe("lib_1");
  });

  it("throws on non-ok response", async () => {
    server.use(http.get("/api/catalog", () => new HttpResponse(null, { status: 500 })));
    await expect(fetchCatalog()).rejects.toThrow("catalog: 500");
  });
});

describe("fetchSamples", () => {
  it("returns samples with pagination metadata", async () => {
    const data = await fetchSamples("lib_1");
    expect(data.samples).toHaveLength(3);
    expect(data.total).toBe(3);
    expect(data.offset).toBe(0);
  });

  it("passes library_id as query param", async () => {
    let capturedUrl = "";
    server.use(
      http.get("/api/samples", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ total: 0, offset: 0, limit: 100, returned: 0, samples: [] });
      }),
    );
    await fetchSamples("lib_test", 50, 100);
    expect(capturedUrl).toContain("library_id=lib_test");
    expect(capturedUrl).toContain("offset=50");
    expect(capturedUrl).toContain("limit=100");
  });
});

describe("fetchSampleDetail", () => {
  it("returns sample detail", async () => {
    const detail = await fetchSampleDetail(2);
    expect(detail.id).toBe(2);
    expect(detail.deep_key).toBe("D_minor");
  });
});

describe("postReview", () => {
  it("resolves without throwing on success", async () => {
    await expect(postReview(1, true)).resolves.toBeUndefined();
  });

  it("throws on error response", async () => {
    server.use(http.post("/api/review", () => new HttpResponse(null, { status: 400 })));
    await expect(postReview(1, true)).rejects.toThrow("review: 400");
  });
});

describe("browseFolders", () => {
  it("returns folder list", async () => {
    const data = await browseFolders();
    expect(data.folders).toHaveLength(2);
    expect(data.folders[0].name).toBe("samples");
  });

  it("passes path param when provided", async () => {
    let capturedUrl = "";
    server.use(
      http.get("/api/browse-folders", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ path: "/samples", parent: "/", folders: [] });
      }),
    );
    await browseFolders("/samples");
    expect(capturedUrl).toContain(encodeURIComponent("/samples"));
  });
});

describe("URL helpers", () => {
  it("getAudioUrl returns correct path", () => {
    expect(getAudioUrl(42)).toBe("/api/audio?id=42");
  });

  it("getMidiUrl returns correct path with progression", () => {
    expect(getMidiUrl(7, 2)).toBe("/api/sample-midi?id=7&progression=2");
  });
});
