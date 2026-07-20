import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";

export function PublicHomePage() {
  return (
    <section className="stack">
      <PageHeader
        title="LoreForge"
        description="A grounded RAG product workspace for private document collections, citation-aware answers, and operator-visible system health."
        actions={
          <>
            <Button as={Link} to={routes.workspace}>
              Open workspace
            </Button>
            <Button as={Link} to={routes.admin} variant="secondary">
              Admin panel
            </Button>
          </>
        }
      />
      <div className="dashboard-grid">
        <Card>
          <h2>Workspace</h2>
          <p className="muted">Owned documents, upload flow, and AskMe routes are separated from operator tools.</p>
          <Badge tone="info">User surface</Badge>
        </Card>
        <Card>
          <h2>Admin</h2>
          <p className="muted">Health, readiness, metrics, and evaluation routes have their own navigation shell.</p>
          <Badge tone="warning">Operator surface</Badge>
        </Card>
        <Card>
          <h2>Backend Boundary</h2>
          <p className="muted">Authorization remains backend-enforced; the frontend only presents product flows.</p>
          <Badge tone="success">Clean contracts</Badge>
        </Card>
      </div>
    </section>
  );
}
