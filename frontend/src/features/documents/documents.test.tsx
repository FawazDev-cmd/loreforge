import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/providers/queryClient";
import { AuthProvider } from "../auth/AuthProvider";
import { authStorageKey } from "../auth/storage";
import { WorkspaceDocumentsPage } from "../../pages/workspace/WorkspaceDocumentsPage";
import { WorkspaceUploadPage } from "../../pages/workspace/WorkspaceUploadPage";
import { uploadDocument } from "./api";

const authSession = JSON.stringify({
  apiKey: "safe-test-key",
  label: "Demo Operator",
});

function renderWithAuth(
  ui: React.ReactElement,
  {
    fetchImpl = vi.fn<typeof fetch>(),
    queryClient = createQueryClient(),
  }: {
    fetchImpl?: typeof fetch;
    queryClient?: ReturnType<typeof createQueryClient>;
  } = {},
) {
  window.sessionStorage.setItem(authStorageKey, authSession);
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider fetchImpl={fetchImpl}>
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { queryClient };
}

describe("documents workspace", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("renders the loading state while documents load", () => {
    const fetchImpl = vi.fn<typeof fetch>().mockReturnValue(new Promise<Response>(() => undefined));

    renderWithAuth(<WorkspaceDocumentsPage />, { fetchImpl });

    expect(screen.getByText("Loading documents.")).toBeInTheDocument();
  });

  it("renders an empty documents state", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ documents: [] }));

    renderWithAuth(<WorkspaceDocumentsPage />, { fetchImpl });

    expect(await screen.findByRole("heading", { name: "No documents yet" })).toBeInTheDocument();
  });

  it("renders document list rows with exact backend statuses", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        documents: [
          {
            chunk_count: 4,
            document_id: "doc-1",
            filename: "policy.pdf",
            page_count: 2,
            status: "INGESTING",
            uploaded_at: "2026-01-01T00:00:00Z",
          },
        ],
      }),
    );

    renderWithAuth(<WorkspaceDocumentsPage />, { fetchImpl });

    expect(await screen.findByText("policy.pdf")).toBeInTheDocument();
    expect(screen.getByText("INGESTING")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders an API failure state", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse({ detail: "server unavailable" }, { status: 503 })),
    );

    renderWithAuth(<WorkspaceDocumentsPage />, { fetchImpl });

    expect(await screen.findByRole("heading", { name: "Documents unavailable" })).toBeInTheDocument();
  });

  it("rejects non-PDF uploads before making a request", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ documents: [] }));

    renderWithAuth(<WorkspaceUploadPage />, { fetchImpl });

    const input = screen.getByLabelText("PDF file");
    await userEvent.upload(input, new File(["hello"], "notes.txt", { type: "text/plain" }), { applyAccept: false });

    expect(screen.getByText("Only .pdf files are supported.")).toBeInTheDocument();
  });

  it("uploads a PDF, reports success, and refreshes document queries", async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const xhr = new FakeUploadRequest({
      responseText: JSON.stringify({
        document_id: "doc-2",
        filename: "handbook.pdf",
        media_type: "application/pdf",
        size_bytes: 15,
        status: "accepted",
      }),
      status: 201,
    });
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => xhr));

    renderWithAuth(<WorkspaceUploadPage />, { queryClient });

    const input = screen.getByLabelText("PDF file");
    await userEvent.upload(input, new File(["%PDF-1.7 content"], "handbook.pdf", { type: "application/pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Upload PDF" }));

    expect(await screen.findByRole("heading", { name: "Upload accepted" })).toBeInTheDocument();
    expect(invalidateSpy).toHaveBeenCalled();
  });

  it("shows upload failure details for backend validation failures", async () => {
    const xhr = new FakeUploadRequest({
      responseText: JSON.stringify({ detail: "invalid PDF signature" }),
      status: 415,
    });
    vi.stubGlobal("XMLHttpRequest", vi.fn(() => xhr));

    renderWithAuth(<WorkspaceUploadPage />);

    await userEvent.upload(
      screen.getByLabelText("PDF file"),
      new File(["%PDF-1.7 content"], "handbook.pdf", { type: "application/pdf" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Upload PDF" }));

    expect(await screen.findByRole("heading", { name: "Upload failed" })).toBeInTheDocument();
    expect(screen.getByText("Only valid PDF files are supported.")).toBeInTheDocument();
  });
});

describe("document upload API", () => {
  it("uses authenticated multipart upload requests and progress callbacks", async () => {
    const xhr = new FakeUploadRequest({
      responseText: JSON.stringify({
        document_id: "doc-3",
        filename: "policy.pdf",
        media_type: "application/pdf",
        size_bytes: 12,
        status: "accepted",
      }),
      status: 201,
    });
    const progress: number[] = [];

    await uploadDocument({
      apiKey: "safe-test-key",
      file: new File(["%PDF-1.7"], "policy.pdf", { type: "application/pdf" }),
      onProgress: (value) => progress.push(value),
      xhrFactory: () => xhr as unknown as XMLHttpRequest,
    });

    expect(xhr.headers.Authorization).toBe("Bearer safe-test-key");
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("http://127.0.0.1:8000/documents/upload");
    expect(progress).toContain(50);
    expect(progress).toContain(100);
  });
});

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: init.status ?? 200,
  });
}

class FakeUploadRequest {
  headers: Record<string, string> = {};
  method = "";
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  responseText: string;
  status: number;
  upload = {
    onprogress: null as ((event: ProgressEvent) => void) | null,
  };
  url = "";

  constructor({ responseText, status }: { responseText: string; status: number }) {
    this.responseText = responseText;
    this.status = status;
  }

  getResponseHeader(name: string) {
    return name === "X-Request-ID" ? "request-1" : null;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  send() {
    this.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 2 } as ProgressEvent);
    this.onload?.();
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }
}

