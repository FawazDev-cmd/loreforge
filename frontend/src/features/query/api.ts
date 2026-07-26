import { ApiClientError, UnauthorizedApiError, type ApiClient } from "../../api/client";

export type AskCitation = {
  citation_id: string;
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number;
};

export type AskResponse = {
  answer: string;
  citations: AskCitation[];
  question: string;
  request_id: string;
};

export type AskRequest = {
  question: string;
};

export function askQuestion(apiClient: ApiClient, request: AskRequest): Promise<AskResponse> {
  return apiClient.request<AskResponse>("/ask", {
    body: request,
    method: "POST",
  });
}

export function askErrorMessage(error: unknown): string {
  if (error instanceof UnauthorizedApiError) {
    return "Your session is no longer authorized. Sign in again.";
  }
  if (error instanceof ApiClientError) {
    if (error.status === 422) {
      return "Enter a valid non-empty question.";
    }
    if (error.status === 502) {
      return "AskMe could not produce a safely grounded answer from the available evidence.";
    }
    if (error.status === 503) {
      return "AskMe is temporarily unavailable.";
    }
    if (error.status >= 500) {
      return "LoreForge could not answer right now.";
    }
  }
  return "Network failure while asking AskMe.";
}

export function isInsufficientEvidenceError(error: unknown): boolean {
  return error instanceof ApiClientError && error.status === 502;
}

