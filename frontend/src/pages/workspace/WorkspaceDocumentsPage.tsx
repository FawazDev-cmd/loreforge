import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { ErrorState } from "../../components/feedback/ErrorState";
import { LoadingState } from "../../components/feedback/LoadingState";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { DocumentList } from "../../features/documents/DocumentList";
import { useDocumentsQuery } from "../../features/documents/hooks";

export function WorkspaceDocumentsPage() {
  const documentsQuery = useDocumentsQuery();

  return (
    <section>
      <PageHeader
        title="Documents"
        description="View document metadata and ingestion lifecycle states returned by LoreForge."
        actions={
          <>
            <Button disabled={documentsQuery.isFetching} onClick={() => void documentsQuery.refetch()} type="button" variant="secondary">
              Refresh
            </Button>
            <Button as={Link} to={routes.workspaceUpload}>
              Upload
            </Button>
          </>
        }
      />
      {documentsQuery.isLoading ? <LoadingState label="Loading documents." /> : null}
      {documentsQuery.isError ? (
        <ErrorState message="LoreForge could not load your document list." title="Documents unavailable" />
      ) : null}
      {documentsQuery.data ? <DocumentList documents={documentsQuery.data.documents} /> : null}
    </section>
  );
}
