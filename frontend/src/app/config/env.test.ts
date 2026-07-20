import { describe, expect, it } from "vitest";

import { loadFrontendConfig } from "./env";

describe("loadFrontendConfig", () => {
  it("uses the local backend default", () => {
    expect(loadFrontendConfig({}).apiBaseUrl).toBe("http://127.0.0.1:8000");
  });

  it("accepts a configured API base URL", () => {
    expect(loadFrontendConfig({ VITE_API_BASE_URL: "https://api.example.test" }).apiBaseUrl).toBe(
      "https://api.example.test",
    );
  });

  it("rejects invalid API base URLs", () => {
    expect(() => loadFrontendConfig({ VITE_API_BASE_URL: "not-a-url" })).toThrow();
  });
});
