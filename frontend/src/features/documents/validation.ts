import { maxUploadSizeBytes, pdfMediaType } from "./api";

export function validatePdfFile(file: File | null): string | null {
  if (!file) {
    return "Choose a PDF file.";
  }
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    return "Only .pdf files are supported.";
  }
  if (file.type && file.type !== pdfMediaType) {
    return "Only application/pdf files are supported.";
  }
  if (file.size === 0) {
    return "The selected PDF is empty.";
  }
  if (file.size > maxUploadSizeBytes) {
    return "The PDF must be 10 MB or smaller.";
  }
  return null;
}

