import { PageHeader } from "../../components/ui/PageHeader";
import { QuestionForm } from "../../features/query/QuestionForm";

export function WorkspaceChatPage() {
  return (
    <section className="stack query-page">
      <div>
        <PageHeader
          title="AskMe"
          description="Ask across all READY indexed documents. LoreForge returns grounded answers with citation metadata instead of unsupported certainty."
        />
        <QuestionForm />
      </div>

    </section>
  );
}