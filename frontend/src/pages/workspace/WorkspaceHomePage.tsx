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
        description="A foundation shell for user-owned document ingestion and grounded question answering."
        actions={
          <Button as={Link} to={routes.workspaceUpload}>
            Upload document
          </Button>
        }
      />
      <div className="dashboard-grid">
        <Card className="metric">
          <span className="muted">Documents</span>
          <span className="metric__value">Pending API wiring</span>
          <Badge tone="neutral">Frontend Day 3</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">AskMe</span>
          <span className="metric__value">Ready shell</span>
          <Badge tone="info">Frontend Day 4</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">Authorization</span>
          <span className="metric__value">Backend-owned</span>
          <Badge tone="success">Server enforced</Badge>
        </Card>
      </div>
      <EmptyState
        title="No workspace data loaded"
        message="Live document lists and answer history are intentionally deferred until the authenticated data layer is connected."
      />
    </section>
  );
}
