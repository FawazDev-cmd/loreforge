import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/providers/queryClient";
import { LoginPage } from "../../pages/public/LoginPage";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";
import { AuthContext } from "./AuthContext";
import { AuthControls } from "./AuthControls";
import { ProtectedRoute } from "./ProtectedRoute";
import { authStorageKey } from "./storage";

const storedSession = JSON.stringify({
  apiKey: "safe-test-key",
  label: "Demo Operator",
});

function renderAuthRoutes({
  fetchImpl = vi.fn<typeof fetch>(),
  initialPath = "/workspace",
}: {
  fetchImpl?: typeof fetch;
  initialPath?: string;
} = {}) {
  const queryClient = createQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider fetchImpl={fetchImpl}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/workspace"
              element={
                <ProtectedRoute>
                  <h1>Workspace</h1>
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <h1>Admin</h1>
                </ProtectedRoute>
              }
            />
            <Route
              path="/protected-action"
              element={
                <ProtectedRoute>
                  <ProtectedAction />
                </ProtectedRoute>
              }
            />
            <Route
              path="/logout"
              element={
                <ProtectedRoute>
                  <AuthControls />
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("authentication integration", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("redirects unauthenticated workspace users to login", async () => {
    renderAuthRoutes({ initialPath: "/workspace" });

    expect(await screen.findByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
  });

  it("renders a loading state while authentication initializes", () => {
    render(
      <AuthContext.Provider
        value={{
          apiClient: { request: vi.fn() },
          clearAuthError: vi.fn(),
          credential: null,
          error: null,
          identity: null,
          login: vi.fn(),
          logout: vi.fn(),
          status: "initializing",
        }}
      >
        <MemoryRouter initialEntries={["/workspace"]}>
          <ProtectedRoute>
            <h1>Workspace</h1>
          </ProtectedRoute>
        </MemoryRouter>
      </AuthContext.Provider>,
    );

    expect(screen.getByText("Restoring authentication.")).toBeInTheDocument();
  });

  it("redirects unauthenticated admin users to login", async () => {
    renderAuthRoutes({ initialPath: "/admin" });

    expect(await screen.findByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
  });

  it("authenticates with a bearer API key and opens the intended route", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ documents: [] }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    renderAuthRoutes({ fetchImpl, initialPath: "/login" });

    await userEvent.type(screen.getByLabelText("Workspace label"), "Demo Operator");
    await userEvent.type(screen.getByLabelText("API key"), "safe-test-key");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Workspace" })).toBeInTheDocument();
    const headers = new Headers(fetchImpl.mock.calls[0]?.[1]?.headers);
    expect(fetchImpl.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8000/admin/documents");
    expect(headers.get("Authorization")).toBe("Bearer safe-test-key");
    expect(window.sessionStorage.getItem(authStorageKey)).not.toContain("wrong-key");
  });

  it("shows an invalid-credential state when the backend rejects the API key", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "authentication required" }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      }),
    );
    renderAuthRoutes({ fetchImpl, initialPath: "/login" });

    await userEvent.type(screen.getByLabelText("Workspace label"), "Demo Operator");
    await userEvent.type(screen.getByLabelText("API key"), "wrong-key");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("heading", { name: "Authentication failed" })).toBeInTheDocument();
    expect(window.sessionStorage.getItem(authStorageKey)).toBeNull();
  });

  it("clears authentication state on logout", async () => {
    window.sessionStorage.setItem(authStorageKey, storedSession);
    renderAuthRoutes({ initialPath: "/logout" });

    await userEvent.click(await screen.findByRole("button", { name: "Log out" }));

    expect(window.sessionStorage.getItem(authStorageKey)).toBeNull();
    expect(await screen.findByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
  });

  it("invalidates authentication after a confirmed unauthorized API response", async () => {
    window.sessionStorage.setItem(authStorageKey, storedSession);
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "authentication required" }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      }),
    );
    renderAuthRoutes({ fetchImpl, initialPath: "/protected-action" });

    await userEvent.click(await screen.findByRole("button", { name: "Call protected API" }));

    await waitFor(() => expect(window.sessionStorage.getItem(authStorageKey)).toBeNull());
    expect(await screen.findByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
  });

  it("allows authenticated users into admin because backend exposes no admin role claim", async () => {
    window.sessionStorage.setItem(authStorageKey, storedSession);

    renderAuthRoutes({ initialPath: "/admin" });

    expect(await screen.findByRole("heading", { level: 1, name: "Admin" })).toBeInTheDocument();
  });
});

function ProtectedAction() {
  const { apiClient } = useAuth();

  async function handleClick() {
    await apiClient.request("/admin/documents");
  }

  return (
    <button onClick={() => void handleClick().catch(() => undefined)} type="button">
      Call protected API
    </button>
  );
}