import { useMutation } from "@tanstack/react-query";

import { useAuth } from "../auth/useAuth";
import { askErrorMessage, askQuestion, isInsufficientEvidenceError } from "./api";

export function useAskQuestion() {
  const { apiClient } = useAuth();
  const mutation = useMutation({
    mutationFn: (question: string) => askQuestion(apiClient, { question }),
  });

  return {
    ...mutation,
    errorMessage: mutation.error ? askErrorMessage(mutation.error) : null,
    isInsufficientEvidence: mutation.error ? isInsufficientEvidenceError(mutation.error) : false,
  };
}

