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
          description="Upload one PDF to the document boundary. LoreForge accepts the file and reports ingestion status through the document list."
          actions={
            <Button as={Link} to={routes.workspaceDocuments} variant="secondary">
              Documents
            </Button>
          }
        />
        <UploadForm />
      </div>
      <EmptyState
        title="Ingestion status remains backend-owned"
        message="A successful upload is accepted by the upload boundary. The document list refreshes after upload, but completion is never faked in the browser."
      />
    </section>
  );
}
