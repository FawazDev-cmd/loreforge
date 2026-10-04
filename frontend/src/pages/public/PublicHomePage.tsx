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
        description="Search your organization's knowledge. Get answers grounded in its documents and trace them back to their sources."
        actions={
          <>
            <Button as={Link} to={routes.workspace}>
              Open workspace
            </Button>
            <Button as={Link} to={routes.admin} variant="secondary">
              Engineering operations
            </Button>
          </>
        }
      />
      <div className="dashboard-grid">
        <Card className="metric">
          <span className="muted">1. Build the knowledge base</span>
          <span className="metric__value">Upload documents</span>
          <p className="muted">Upload internal documents and track them through the indexing workflow until they are ready for retrieval.</p>
          <Badge tone="info">Document workflow</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">2. Ask grounded questions</span>
          <span className="metric__value">Get document-based answers</span>
          <p className="muted">Ask questions across your document collection and get the answers based on retrieved evidence.</p>
          <Badge tone="success">Grounded answers</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">3. Trace the answer</span>
          <span className="metric__value">Inspect sources</span>
          <p className="muted">Review the documents and citations returned with each answer.</p>
          <Badge tone="neutral">Source traceability</Badge>
        </Card>
      </div>
      <Card className="journey-card">
        <h2>Explore the workspace</h2>
        <p>Sign in to explore the document collection, ask a question, inspect its sources, and review system operations.</p>
      </Card>
    </section>
  );
}