export type HealthResponse = {
  service: "loreforge";
  status: "healthy";
};

export type ReadyResponse = {
  service: "loreforge";
  status: "ready" | "not_ready";
};

export type DocumentStatus = "UPLOADED" | "INGESTING" | "READY" | "FAILED" | "DELETED";

export type DocumentResponse = {
  chunk_count: number;
  document_id: string;
  filename: string;
  page_count: number;
  status: DocumentStatus;
  uploaded_at: string;
};

export type DocumentListResponse = {
  documents: DocumentResponse[];
};
