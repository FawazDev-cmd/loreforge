import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../app/router/createAppRouter";
import { createQueryClient } from "../../app/providers/queryClient";
import { AuthProvider } from "../auth/AuthProvider";
import { authStorageKey } from "../auth/storage";
import { OperationalStatusCard } from "./OperationalStatusCard";

const authSession = JSON.stringify({
  apiKey: "safe-test-key",
  label: "Demo Operator",
});

function renderRoute(path: string, fetchImpl: typeof fetch = successfulOperationsFetch()) {
  window.sessionStorage.setItem(authStorageKey, authSession);
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });

  render(
    <QueryClientProvider client={createQueryClient()}>
      <AuthProvider fetchImpl={fetchImpl}>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("engineering operations panel", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("renders engineering navigation without unsupported admin sections", () => {
    renderRoute("/admin");

    expect(screen.getByRole("link", { name: "LoreForge Engineering" })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("heading", { level: 1, name: "Engineering Operations" })).toBeInTheDocument();
    const engineeringNavigation = screen.getByRole("navigation", { name: "Engineering navigation" });
    expect(within(engineeringNavigation).getByRole("link", { name: "System" })).toHaveAttribute("href", "/admin/system");
    expect(within(engineeringNavigation).getByRole("link", { name: "Metrics" })).toHaveAttribute("href", "/admin/metrics");
    expect(within(engineeringNavigation).getByRole("link", { name: "Evaluation" })).toHaveAttribute("href", "/admin/evaluation");
    expect(screen.queryByText("Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Billing")).not.toBeInTheDocument();
    expect(screen.queryByText("Roles")).not.toBeInTheDocument();
  });

  it("renders health and readiness from backend-supported fields", async () => {
    renderRoute("/admin/system");

    expect(await screen.findByText("Service loreforge reports healthy.")).toBeInTheDocument();
    expect(screen.getByText("Application startup and warm-up completed successfully.")).toBeInTheDocument();
    expect(screen.getByText("Application version")).toBeInTheDocument();
    expect(screen.getAllByText("Not available").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Version is not exposed by the backend API.")).toBeInTheDocument();
    expect(screen.queryByText("Unknown")).not.toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
  });

  it("renders unavailable backend fields safely", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      const path = new URL(String(url)).pathname;
      if (path === "/health") {
        return jsonResponse({ service: "loreforge", status: "healthy" });
      }
      if (path === "/ready") {
        return jsonResponse({ ready: false }, { status: 503 });
      }
      return jsonResponse({ detail: "not found" }, { status: 404 });
    });

    renderRoute("/admin/system", fetchImpl);

    expect(await screen.findByText("Service loreforge reports healthy.")).toBeInTheDocument();
    expect(screen.getByText("Readiness")).toBeInTheDocument();
    expect(screen.getAllByText("Not available").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Application startup or warm-up has not completed.")).toBeInTheDocument();
    expect(screen.queryByText("Unknown")).not.toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
    expect(screen.queryByText(/database URL/i)).not.toBeInTheDocument();
  });

  it("renders readiness retrieval failures with intentional wording", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      const path = new URL(String(url)).pathname;
      if (path === "/health") {
        return jsonResponse({ service: "loreforge", status: "healthy" });
      }
      if (path === "/ready") {
        return jsonResponse({ detail: "not found" }, { status: 404 });
      }
      return jsonResponse({ detail: "not found" }, { status: 404 });
    });

    renderRoute("/admin/system", fetchImpl);

    expect(await screen.findByText("Service loreforge reports healthy.")).toBeInTheDocument();
    expect(screen.getByText("Readiness status could not be retrieved.")).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
  });

  it("renders metrics snapshot summaries without fake dashboards", async () => {
    renderRoute("/admin/metrics");

    expect(await screen.findByText("Metrics snapshot loaded.")).toBeInTheDocument();
    expect(screen.getByText("1 counter series exposed.")).toBeInTheDocument();
    expect(screen.getByText("1 duration series exposed.")).toBeInTheDocument();
    expect(screen.getByText("http_request_total")).toBeInTheDocument();
    expect(screen.getByText("http_request_duration_ms")).toBeInTheDocument();
    expect(screen.getByText("Query trace count: 2")).toBeInTheDocument();
  });

  it("renders metrics unavailable state", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      const path = new URL(String(url)).pathname;
      if (path === "/metrics") {
        return jsonResponse({ detail: "metrics unavailable" }, { status: 503 });
      }
      return jsonResponse({ service: "loreforge", status: "healthy" });
    });

    renderRoute("/admin/metrics", fetchImpl);

    expect(await screen.findByRole("heading", { name: "Metrics unavailable" })).toBeInTheDocument();
  });

  it("renders the honest offline evaluation placeholder", () => {
    renderRoute("/admin/evaluation");

    expect(screen.getByRole("heading", { level: 1, name: "Evaluation" })).toBeInTheDocument();
    expect(screen.getByText("No evaluation summary endpoint is exposed by the backend.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evaluation runs offline" })).toBeInTheDocument();
  });

  it("renders reusable status card states", () => {
    render(<OperationalStatusCard detail="Backend responded." status="healthy" title="API health" />);

    expect(screen.getByRole("heading", { name: "API health" })).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Backend responded.")).toBeInTheDocument();
  });
});

function successfulOperationsFetch() {
  return vi.fn<typeof fetch>().mockImplementation(async (url) => {
    const path = new URL(String(url)).pathname;
    if (path === "/health") {
      return jsonResponse({ service: "loreforge", status: "healthy" });
    }
    if (path === "/ready") {
      return jsonResponse({ ready: true });
    }
    if (path === "/metrics") {
      return jsonResponse({
        metrics: {
          counters: [
            {
              labels: { method: "GET", route: "/health", status_category: "2xx" },
              name: "http_request_total",
              value: 4,
            },
          ],
          durations: [
            {
              count: 4,
              labels: { method: "GET", route: "/health", status_category: "2xx" },
              max_ms: 12.5,
              name: "http_request_duration_ms",
              total_ms: 20.5,
            },
          ],
        },
        query_trace_count: 2,
        status: "ok",
      });
    }
    return jsonResponse({ detail: "not found" }, { status: 404 });
  });
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: init.status ?? 200,
  });
}