import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiClientError, UnauthorizedApiError } from "../../api/client";
import { useAuth } from "../auth/useAuth";
import {
  documentsQueryKey,
  listDocuments,
  uploadDocument,
  type DocumentUploadResponse,
} from "./api";

export function useDocumentsQuery() {
  const { apiClient } = useAuth();

  return useQuery({
    queryFn: () => listDocuments(apiClient),
    queryKey: documentsQueryKey,
    retry: false,
  });
}

export function useDocumentUpload() {
  const queryClient = useQueryClient();
  const { credential, logout } = useAuth();
  const [progress, setProgress] = useState(0);

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      if (!credential) {
        throw new UnauthorizedApiError({
          detail: { detail: "authentication required" },
          requestId: null,
        });
      }

      return uploadDocument({
        apiKey: credential.apiKey,
        file,
        onProgress: setProgress,
      });
    },
    onError: (error) => {
      if (error instanceof UnauthorizedApiError) {
        logout();
      }
    },
    onMutate: () => {
      setProgress(0);
    },
    onSuccess: async () => {
      setProgress(100);
      await queryClient.invalidateQueries({ queryKey: documentsQueryKey });
    },
  });

  return {
    ...mutation,
    errorMessage: mutation.error ? documentUploadErrorMessage(mutation.error) : null,
    progress,
  };
}

export function documentUploadErrorMessage(error: unknown): string {
  if (error instanceof UnauthorizedApiError) {
    return "Your session is no longer authorized. Sign in again.";
  }
  if (error instanceof ApiClientError) {
    if (error.status === 413) {
      return "The PDF is larger than the 10 MB upload limit.";
    }
    if (error.status === 415) {
      return "Only valid PDF files are supported.";
    }
    if (error.status === 400 || error.status === 422) {
      return "The selected file could not be accepted. Choose a valid PDF.";
    }
    if (error.status >= 500) {
      return "LoreForge could not accept the upload right now.";
    }
  }
  if (error instanceof Error && error.message.includes("Network")) {
    return "Network failure during document upload.";
  }
  return "Document upload failed.";
}

export type DocumentUploadMutationResult = ReturnType<typeof useDocumentUpload> & {
  data: DocumentUploadResponse | undefined;
};

