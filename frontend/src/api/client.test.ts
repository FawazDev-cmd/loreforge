import { describe, expect, it, vi } from "vitest";

import { ForbiddenApiError, UnauthorizedApiError, createApiClient } from "./client";

describe("createApiClient", () => {
  it("reads JSON responses and preserves the request header contract", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "healthy", service: "loreforge" }), {
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "request-1",
        },
        status: 200,
      }),
    );
    const client = createApiClient({
      baseUrl: "https://api.example.test/",
      fetchImpl,
      getAuthToken: () => "token-value",
    });

    await expect(client.request("/health")).resolves.toEqual({
      service: "loreforge",
      status: "healthy",
    });

    const [_url, init] = fetchImpl.mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(_url).toBe("https://api.example.test/health");
    expect(headers.get("Authorization")).toBe("Bearer token-value");
    expect(headers.get("Accept")).toBe("application/json");
  });

  it("serializes JSON request bodies", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    const client = createApiClient({ baseUrl: "https://api.example.test", fetchImpl });

    await client.request("/admin/documents", {
      body: { filename: "handbook.pdf" },
      method: "POST",
    });

    const init = fetchImpl.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init?.body).toBe('{"filename":"handbook.pdf"}');
  });

  it("returns safe unauthorized errors and invokes the unauthorized hook", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "authentication required" }), {
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "request-2",
        },
        status: 401,
      }),
    );
    const onUnauthorized = vi.fn();
    const client = createApiClient({
      baseUrl: "https://api.example.test",
      fetchImpl,
      onUnauthorized,
    });

    let caughtError: unknown;
    try {
      await client.request("/metrics");
    } catch (error) {
      caughtError = error;
    }

    expect(caughtError).toBeInstanceOf(UnauthorizedApiError);
    expect(caughtError).toMatchObject({
      detail: { detail: "authentication required" },
      message: "Authentication is required.",
      requestId: "request-2",
      status: 401,
    });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });
});


describe("authorization-specific API errors", () => {
  it("maps forbidden responses to typed errors", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "forbidden" }), {
        headers: { "Content-Type": "application/json" },
        status: 403,
      }),
    );
    const client = createApiClient({ baseUrl: "https://api.example.test", fetchImpl });

    await expect(client.request("/admin/system")).rejects.toBeInstanceOf(ForbiddenApiError);
  });
});
