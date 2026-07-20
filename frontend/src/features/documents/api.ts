import {
  ApiClientError,
  UnauthorizedApiError,
  type ApiClient,
} from "../../api/client";
import type { DocumentListResponse } from "../../api/contracts";
import { frontendConfig } from "../../app/config/env";

export const documentsQueryKey = ["documents"] as const;
export const pdfMediaType = "application/pdf";
export const maxUploadSizeBytes = 10 * 1024 * 1024;

export type DocumentUploadResponse = {
  document_id: string;
  filename: string;
  media_type: typeof pdfMediaType;
  size_bytes: number;
  status: "accepted";
};

export type UploadDocumentOptions = {
  apiKey: string;
  file: File;
  onProgress?: (progress: number) => void;
  xhrFactory?: () => XMLHttpRequest;
};

export function listDocuments(apiClient: ApiClient): Promise<DocumentListResponse> {
  return apiClient.request<DocumentListResponse>("/admin/documents");
}

export function uploadDocument({
  apiKey,
  file,
  onProgress,
  xhrFactory = () => new XMLHttpRequest(),
}: UploadDocumentOptions): Promise<DocumentUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = xhrFactory();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onerror = () => reject(new Error("Network failure during document upload."));
    xhr.onload = () => {
      const requestId = xhr.getResponseHeader("X-Request-ID");
      const payload = parseUploadPayload(xhr.responseText);

      if (xhr.status === 401) {
        reject(new UnauthorizedApiError({ detail: payload, requestId }));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(
          new ApiClientError("API request failed.", {
            detail: payload,
            requestId,
            status: xhr.status,
          }),
        );
        return;
      }

      onProgress?.(100);
      resolve(payload as DocumentUploadResponse);
    };

    xhr.open("POST", `${frontendConfig.apiBaseUrl.replace(/\/+$/, "")}/documents/upload`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("Authorization", `Bearer ${apiKey}`);
    xhr.send(formData);
  });
}

function parseUploadPayload(responseText: string): unknown {
  if (!responseText) {
    return undefined;
  }

  try {
    return JSON.parse(responseText) as unknown;
  } catch {
    return responseText;
  }
}

