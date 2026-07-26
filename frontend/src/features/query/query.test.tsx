import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/providers/queryClient";
import { WorkspaceChatPage } from "../../pages/workspace/WorkspaceChatPage";
import { AuthProvider } from "../auth/AuthProvider";
import { authStorageKey } from "../auth/storage";

const authSession = JSON.stringify({
  apiKey: "safe-test-key",
  label: "Demo Operator",
});

const readyDocument = {
  chunk_count: 3,
  document_id: "ready-doc",
  filename: "refund-policy.pdf",
  page_count: 2,
  status: "READY",
  uploaded_at: "2026-01-01T00:00:00Z",
};

const secondReadyDocument = {
  ...readyDocument,
  document_id: "ready-doc-2",
  filename: "employee-handbook.pdf",
};

const uploadedDocument = {
  ...readyDocument,
  document_id: "uploaded-doc",
  filename: "draft.pdf",
  status: "UPLOADED",
};

function renderChat(fetchImpl: typeof fetch) {
  window.sessionStorage.setItem(authStorageKey, authSession);
  render(
    <QueryClientProvider client={createQueryClient()}>
      <AuthProvider fetchImpl={fetchImpl}>
        <MemoryRouter>
          <WorkspaceChatPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("AskMe query experience", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not display a fake document selector", async () => {
    renderChat(fetchDocuments({ documents: [readyDocument, uploadedDocument] }));

    expect(await screen.findByText("Collection-wide retrieval")).toBeInTheDocument();
    expect(screen.queryByLabelText("READY document")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("explains collection-wide retrieval across READY documents", async () => {
    renderChat(fetchDocuments({ documents: [readyDocument, secondReadyDocument, uploadedDocument] }));

    expect(await screen.findByText(/AskMe searches across all 2 READY indexed documents/)).toBeInTheDocument();
    expect(screen.getByText(/Documents still marked UPLOADED or INGESTING/)).toBeInTheDocument();
    expect(screen.getByText(/refund-policy.pdf, employee-handbook.pdf/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View document statuses" })).toHaveAttribute("href", "/workspace/documents");
  });

  it("shows a no-document state before uploads exist", async () => {
    renderChat(fetchDocuments({ documents: [] }));

    expect(await screen.findByRole("heading", { name: "No uploaded documents" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload document" })).toHaveAttribute("href", "/workspace/documents/upload");
  });

  it("shows a no-READY state while indexing is active", async () => {
    renderChat(fetchDocuments({ documents: [uploadedDocument] }));

    expect(await screen.findByRole("heading", { name: "No READY documents" })).toBeInTheDocument();
    expect(screen.getByText(/Indexing is still running/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View documents" })).toHaveAttribute("href", "/workspace/documents");
  });

  it("submits a successful query and renders answer citations", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (_url, init) => {
      if (init?.method === "POST") {
        return jsonResponse({
          answer: "Refund requests must be submitted within 14 days [S1].",
          citations: [
            {
              chunk_id: "00000000-0000-0000-0000-000000000101",
              citation_id: "S1",
              document_id: "00000000-0000-0000-0000-000000000201",
              filename: "refund-policy.pdf",
              page_number: 2,
            },
          ],
          question: "What is the refund policy?",
          request_id: "00000000-0000-0000-0000-000000000001",
        });
      }
      return jsonResponse({ documents: [readyDocument] });
    });
    renderChat(fetchImpl);

    await screen.findByText("Collection-wide retrieval");
    await userEvent.type(screen.getByLabelText("Question"), "What is the refund policy?");
    await userEvent.click(screen.getByRole("button", { name: "AskMe" }));

    expect(await screen.findByRole("heading", { name: "Grounded answer" })).toBeInTheDocument();
    expect(screen.getByText("Collection-wide answer")).toBeInTheDocument();
    expect(screen.getByText("Refund requests must be submitted within 14 days [S1].")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "S1" })).toBeInTheDocument();
    expect(screen.getAllByText("refund-policy.pdf").length).toBeGreaterThanOrEqual(2);

    const askCall = fetchImpl.mock.calls.find((call) => call[1]?.method === "POST");
    expect(askCall?.[0]).toBe("http://127.0.0.1:8000/ask");
    expect(askCall?.[1]?.body).toBe('{"question":"What is the refund policy?"}');
    expect(new Headers(askCall?.[1]?.headers).get("Authorization")).toBe("Bearer safe-test-key");
  });

  it("expands citation evidence metadata truthfully", async () => {
    renderChat(fetchSuccessfulAsk());

    await screen.findByText("Collection-wide retrieval");
    await userEvent.type(screen.getByLabelText("Question"), "What is the refund policy?");
    await userEvent.click(screen.getByRole("button", { name: "AskMe" }));
    await userEvent.click(await screen.findByRole("button", { name: "Show evidence" }));

    expect(screen.getByText("Evidence excerpts are not yet returned by the backend.")).toBeInTheDocument();
    expect(screen.getByText("Chunk ID")).toBeInTheDocument();
    expect(screen.getByText("00000000-0000-0000-0000-000000000101")).toBeInTheDocument();
  });

  it("shows validation when the question is blank", async () => {
    renderChat(fetchDocuments({ documents: [readyDocument] }));

    await screen.findByText("Collection-wide retrieval");
    await userEvent.click(screen.getByRole("button", { name: "AskMe" }));

    expect(screen.getByRole("heading", { name: "Question not ready" })).toBeInTheDocument();
    expect(screen.getByText("Enter a question.")).toBeInTheDocument();
  });

  it("renders insufficient evidence distinctly", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (_url, init) => {
      if (init?.method === "POST") {
        return jsonResponse(
          { detail: "AskMe could not produce a safely grounded answer." },
          { status: 502 },
        );
      }
      return jsonResponse({ documents: [readyDocument] });
    });
    renderChat(fetchImpl);

    await screen.findByText("Collection-wide retrieval");
    await userEvent.type(screen.getByLabelText("Question"), "What is the refund policy?");
    await userEvent.click(screen.getByRole("button", { name: "AskMe" }));

    expect(await screen.findByRole("heading", { name: "Insufficient evidence" })).toBeInTheDocument();
  });

  it("renders loading while asking", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation((_url, init) => {
      if (init?.method === "POST") {
        return new Promise<Response>(() => undefined);
      }
      return Promise.resolve(jsonResponse({ documents: [readyDocument] }));
    });
    renderChat(fetchImpl);

    await screen.findByText("Collection-wide retrieval");
    await userEvent.type(screen.getByLabelText("Question"), "What is the refund policy?");
    await userEvent.click(screen.getByRole("button", { name: "AskMe" }));

    expect(await screen.findByText("Retrieving evidence and generating an answer.")).toBeInTheDocument();
  });

  it("clears authentication on unauthorized AskMe responses", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (_url, init) => {
      if (init?.method === "POST") {
        return jsonResponse({ detail: "authentication required" }, { status: 401 });
      }
      return jsonResponse({ documents: [readyDocument] });
    });
    renderChat(fetchImpl);

    await screen.findByText("Collection-wide retrieval");
    await userEvent.type(screen.getByLabelText("Question"), "What is the refund policy?");
    await userEvent.click(screen.getByRole("button", { name: "AskMe" }));

    await waitFor(() => expect(window.sessionStorage.getItem(authStorageKey)).toBeNull());
  });
});

function fetchDocuments(body: unknown) {
  return vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body));
}

function fetchSuccessfulAsk() {
  return vi.fn<typeof fetch>().mockImplementation(async (_url, init) => {
    if (init?.method === "POST") {
      return jsonResponse({
        answer: "Refund requests must be submitted within 14 days [S1].",
        citations: [
          {
            chunk_id: "00000000-0000-0000-0000-000000000101",
            citation_id: "S1",
            document_id: "00000000-0000-0000-0000-000000000201",
            filename: "refund-policy.pdf",
            page_number: 2,
          },
        ],
        question: "What is the refund policy?",
        request_id: "00000000-0000-0000-0000-000000000001",
      });
    }
    return jsonResponse({ documents: [readyDocument] });
  });
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: init.status ?? 200,
  });
}