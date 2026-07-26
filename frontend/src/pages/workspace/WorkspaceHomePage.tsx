import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { EmptyState } from "../../components/feedback/EmptyState";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";

export function WorkspaceHomePage() {
  return (
    <section className="stack">
      <PageHeader
        title="Workspace"
        description="The MVP workflow is linear: upload PDFs, wait for READY, ask AskMe, then inspect the citations behind the answer."
        actions={
          <>
            <Button as={Link} to={routes.workspaceUpload}>
              Upload document
            </Button>
            <Button as={Link} to={routes.workspaceChat} variant="secondary">
              AskMe
            </Button>
          </>
        }
      />
      <div className="dashboard-grid">
        <Card className="metric">
          <span className="muted">Step 1</span>
          <span className="metric__value">Upload PDFs</span>
          <p className="muted">Accepted uploads are tracked through UPLOADED, INGESTING, and READY states.</p>
          <Badge tone="info">Ingestion tracked</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">Step 2</span>
          <span className="metric__value">AskMe</span>
          <p className="muted">Ask questions across all READY indexed documents owned by the authenticated user.</p>
          <Badge tone="success">READY docs only</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">Step 3</span>
          <span className="metric__value">Inspect citations</span>
          <p className="muted">Every answer includes source metadata so grounding is visible instead of implied.</p>
          <Badge tone="neutral">Evidence metadata</Badge>
        </Card>
      </div>
      <EmptyState
        title="Recommended demo path"
        message="Upload Documents -> wait until READY -> ask AskMe -> inspect citations -> open Engineering Operations."
      />
    </section>
  );
}