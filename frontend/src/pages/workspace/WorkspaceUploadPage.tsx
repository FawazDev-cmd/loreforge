import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { EmptyState } from "../../components/feedback/EmptyState";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { UploadForm } from "../../features/documents/UploadForm";

export function WorkspaceUploadPage() {
  return (
    <section className="split">
      <div>
        <PageHeader
          title="Upload"
          description="Upload one PDF at a time. Acceptance starts ingestion; READY status is reported later on the document list."
          actions={
            <Button as={Link} to={routes.workspaceDocuments} variant="secondary">
              View documents
            </Button>
          }
        />
        <UploadForm />
      </div>
      <EmptyState
        title="Acceptance is not completion"
        message="A successful upload means LoreForge accepted the file for ingestion. The browser waits for the backend to report READY before AskMe can retrieve from it."
      />
    </section>
  );
}