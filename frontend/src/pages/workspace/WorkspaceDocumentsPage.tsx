import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { ErrorState } from "../../components/feedback/ErrorState";
import { LoadingState } from "../../components/feedback/LoadingState";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { DocumentList } from "../../features/documents/DocumentList";
import { hasActiveDocuments } from "../../features/documents/api";
import { useDocumentsQuery } from "../../features/documents/hooks";

export function WorkspaceDocumentsPage() {
  const documentsQuery = useDocumentsQuery();
  const isPollingActiveDocuments = hasActiveDocuments(documentsQuery.data);

  return (
    <section>
      <PageHeader
        title="Documents"
        description="Monitor ingestion here. AskMe can use a document only after the backend reports READY."
        actions={
          <>
            <Button disabled={documentsQuery.isFetching} onClick={() => void documentsQuery.refetch()} type="button" variant="secondary">
              Refresh
            </Button>
            <Button as={Link} to={routes.workspaceUpload}>
              Upload PDF
            </Button>
          </>
        }
      />
      {documentsQuery.isLoading ? <LoadingState label="Loading document status." /> : null}
      {documentsQuery.isError ? (
        <ErrorState message="LoreForge could not load your document list. Refresh or sign in again if the session expired." title="Documents unavailable" />
      ) : null}
      {isPollingActiveDocuments ? (
        <p className="muted" role="status">
          Ingestion is still active. This list refreshes automatically until every document reaches READY, FAILED, or DELETED.
        </p>
      ) : null}
      {documentsQuery.data ? <DocumentList documents={documentsQuery.data.documents} /> : null}
    </section>
  );
}