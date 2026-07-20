import type { DocumentResponse } from "../../api/contracts";
import { EmptyState } from "../../components/feedback/EmptyState";
import { DocumentStatusBadge } from "./DocumentStatusBadge";

type DocumentListProps = {
  documents: DocumentResponse[];
};

export function DocumentList({ documents }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <EmptyState
        title="No documents yet"
        message="Upload a PDF to begin building your LoreForge workspace."
      />
    );
  }

  return (
    <div className="document-table-wrap">
      <table className="document-table">
        <thead>
          <tr>
            <th scope="col">Filename</th>
            <th scope="col">Uploaded</th>
            <th scope="col">Status</th>
            <th scope="col">Pages</th>
            <th scope="col">Chunks</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.document_id}>
              <td>{document.filename}</td>
              <td>{formatUploadedAt(document.uploaded_at)}</td>
              <td>
                <DocumentStatusBadge status={document.status} />
              </td>
              <td>{document.page_count}</td>
              <td>{document.chunk_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatUploadedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

