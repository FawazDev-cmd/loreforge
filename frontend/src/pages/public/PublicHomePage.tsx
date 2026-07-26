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
        description="A private-document AskMe system: upload PDFs, wait for indexing, ask grounded questions, and inspect the citations behind every answer."
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
          <span className="muted">1. Build the collection</span>
          <span className="metric__value">Upload PDFs</span>
          <p className="muted">LoreForge accepts documents, tracks ingestion, and shows when they become READY for retrieval.</p>
          <Badge tone="info">Document workflow</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">2. Ask grounded questions</span>
          <span className="metric__value">AskMe answers</span>
          <p className="muted">Answers are generated only from indexed evidence and returned with citation metadata.</p>
          <Badge tone="success">Citation aware</Badge>
        </Card>
        <Card className="metric">
          <span className="muted">3. Inspect operations</span>
          <span className="metric__value">Engineering view</span>
          <p className="muted">Health, readiness, metrics, and offline evaluation posture are separated from the user workflow.</p>
          <Badge tone="neutral">Production minded</Badge>
        </Card>
      </div>
      <Card className="journey-card">
        <h2>Demo path</h2>
        <p>Sign in, upload a PDF, monitor ingestion, ask AskMe, inspect citations, then review Engineering Operations.</p>
      </Card>
    </section>
  );
}