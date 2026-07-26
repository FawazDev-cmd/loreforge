import type {
  DocumentListResponse,
  DocumentStatus,
} from "../../api/contracts";
import {
  ApiClientError,
  UnauthorizedApiError,
  type ApiClient,
} from "../../api/client";
import { frontendConfig } from "../../app/config/env";


export const documentsQueryKey = ["documents"] as const;
export const pdfMediaType = "application/pdf";
export const maxUploadSizeBytes = 10 * 1024 * 1024;


type RegisteredDocumentResponse = {
  document_id: string;
  filename: string;
  uploaded_at: string;
  page_count: number;
  chunk_count: number;
  status: DocumentStatus;
};


export type DocumentUploadResponse = {
  document_id: string;
  filename: string;
  chunk_count: number;
  semantic_indexed_count: number;
  lexical_indexed_count: number;
};


type IndexedDocumentResponse = {
  document_id: string;
  chunk_count: number;
  semantic_indexed_count: number;
  lexical_indexed_count: number;
};


export type UploadDocumentOptions = {
  apiKey: string;
  file: File;
  onProgress?: (progress: number) => void;
  xhrFactory?: () => XMLHttpRequest;
};


type IndexRegisteredDocumentOptions = {
  apiBaseUrl: string;
  apiKey: string;
  documentId: string;
  file: File;
  onProgress?: (progress: number) => void;
  xhrFactory: () => XMLHttpRequest;
};


export function listDocuments(
  apiClient: ApiClient,
): Promise<DocumentListResponse> {
  return apiClient.request<DocumentListResponse>("/admin/documents");
}


export function isActiveDocumentStatus(
  status: DocumentStatus,
): boolean {
  return status === "UPLOADED" || status === "INGESTING";
}


export function hasActiveDocuments(
  response: DocumentListResponse | undefined,
): boolean {
  return (
    response?.documents.some((document) =>
      isActiveDocumentStatus(document.status),
    ) ?? false
  );
}


export async function uploadDocument({
  apiKey,
  file,
  onProgress,
  xhrFactory = () => new XMLHttpRequest(),
}: UploadDocumentOptions): Promise<DocumentUploadResponse> {
  const apiBaseUrl = frontendConfig.apiBaseUrl.replace(/\/+$/, "");

  /*
   * Stage 1: Register the document in the durable catalogue.
   */
  const registerResponse = await fetch(
    `${apiBaseUrl}/admin/documents`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        filename: file.name,
        page_count: 0,
        chunk_count: 0,
      }),
    },
  );

  const registerRequestId =
    registerResponse.headers.get("X-Request-ID");

  const registerPayload =
    await parseFetchPayload(registerResponse);

  if (registerResponse.status === 401) {
    throw new UnauthorizedApiError({
      detail: registerPayload,
      requestId: registerRequestId,
    });
  }

  if (!registerResponse.ok) {
    throw new ApiClientError(
      "Failed to register document.",
      {
        detail: registerPayload,
        requestId: registerRequestId,
        status: registerResponse.status,
      },
    );
  }

  const registeredDocument =
    registerPayload as RegisteredDocumentResponse;

  /*
   * Stage 2: Upload and index the PDF using its persisted ID.
   */
  const indexedDocument = await indexRegisteredDocument({
    apiBaseUrl,
    apiKey,
    documentId: registeredDocument.document_id,
    file,
    onProgress,
    xhrFactory,
  });

  return {
    document_id: indexedDocument.document_id,
    filename: registeredDocument.filename,
    chunk_count: indexedDocument.chunk_count,
    semantic_indexed_count:
      indexedDocument.semantic_indexed_count,
    lexical_indexed_count:
      indexedDocument.lexical_indexed_count,
  };
}


function indexRegisteredDocument({
  apiBaseUrl,
  apiKey,
  documentId,
  file,
  onProgress,
  xhrFactory,
}: IndexRegisteredDocumentOptions): Promise<IndexedDocumentResponse> {
  return new Promise((resolve, reject) => {
    const xhr = xhrFactory();
    const formData = new FormData();

    formData.append("file", file);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(
          Math.round((event.loaded / event.total) * 100),
        );
      }
    };

    xhr.onerror = () => {
      reject(
        new Error(
          "Network failure during document indexing.",
        ),
      );
    };

    xhr.onload = () => {
      const requestId =
        xhr.getResponseHeader("X-Request-ID");
      const payload = parseUploadPayload(xhr.responseText);

      if (xhr.status === 401) {
        reject(
          new UnauthorizedApiError({
            detail: payload,
            requestId,
          }),
        );
        return;
      }

      if (xhr.status < 200 || xhr.status >= 300) {
        reject(
          new ApiClientError(
            "Document indexing failed.",
            {
              detail: payload,
              requestId,
              status: xhr.status,
            },
          ),
        );
        return;
      }

      onProgress?.(100);
      resolve(payload as IndexedDocumentResponse);
    };

    xhr.open(
      "POST",
      `${apiBaseUrl}/admin/documents/${documentId}/index`,
    );

    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader(
      "Authorization",
      `Bearer ${apiKey}`,
    );

    xhr.send(formData);
  });
}


async function parseFetchPayload(
  response: Response,
): Promise<unknown> {
  return parseUploadPayload(await response.text());
}


function parseUploadPayload(
  responseText: string,
): unknown {
  if (!responseText) {
    return undefined;
  }

  try {
    return JSON.parse(responseText) as unknown;
  } catch {
    return responseText;
  }
}
