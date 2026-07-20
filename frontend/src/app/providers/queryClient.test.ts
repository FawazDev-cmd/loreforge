import { describe, expect, it } from "vitest";

import { createQueryClient } from "./queryClient";

describe("createQueryClient", () => {
  it("uses conservative defaults for predictable product data loading", () => {
    const client = createQueryClient();
    const defaults = client.getDefaultOptions();

    expect(defaults.queries?.retry).toBe(1);
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false);
    expect(defaults.queries?.staleTime).toBe(30000);
    expect(defaults.mutations?.retry).toBe(0);
  });
});
