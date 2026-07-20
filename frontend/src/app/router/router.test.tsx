import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../features/auth/AuthProvider";
import { authStorageKey } from "../../features/auth/storage";
import { createQueryClient } from "../providers/queryClient";
import { appRoutes } from "./createAppRouter";

function renderRoute(path: string, authenticated = false) {
  if (authenticated) {
    window.sessionStorage.setItem(
      authStorageKey,
      JSON.stringify({ apiKey: "safe-test-key", label: "Demo Operator" }),
    );
  } else {
    window.sessionStorage.clear();
  }

  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={createQueryClient()}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("application routes", () => {
  it("renders the public product route", () => {
    renderRoute("/");

    expect(screen.getByRole("heading", { level: 1, name: "LoreForge" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open workspace" })).toHaveAttribute("href", "/workspace");
  });

  it("renders workspace routes in the workspace layout", () => {
    renderRoute("/workspace/documents/upload", true);

    expect(screen.getByRole("link", { name: "LoreForge Workspace" })).toHaveAttribute(
      "href",
      "/workspace",
    );
    expect(screen.getByRole("heading", { level: 1, name: "Upload" })).toBeInTheDocument();
  });

  it("renders admin routes in the admin layout", () => {
    renderRoute("/admin/evaluation", true);

    expect(screen.getByRole("link", { name: "LoreForge Admin" })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("heading", { level: 1, name: "Evaluation" })).toBeInTheDocument();
  });

  it("renders the not-found state for unsupported routes", () => {
    renderRoute("/unknown-route");

    expect(screen.getByRole("heading", { level: 2, name: "Page not found" })).toBeInTheDocument();
  });
});
