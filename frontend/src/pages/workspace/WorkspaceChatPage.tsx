import { EmptyState } from "../../components/feedback/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";
import { QuestionForm } from "../../features/query/QuestionForm";

export function WorkspaceChatPage() {
  return (
    <section className="split">
      <div>
        <PageHeader
          title="AskMe"
          description="Ask across all READY indexed documents. LoreForge returns grounded answers with citation metadata instead of unsupported certainty."
        />
        <QuestionForm />
      </div>
      <EmptyState
        title="Grounding is visible"
        message="AskMe answers must include citations. Evidence excerpts are not exposed by the backend yet, so the UI shows source metadata honestly."
      />
    </section>
  );
}