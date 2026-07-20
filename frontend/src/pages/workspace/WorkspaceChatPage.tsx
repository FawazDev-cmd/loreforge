import { EmptyState } from "../../components/feedback/EmptyState";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { PageHeader } from "../../components/ui/PageHeader";

export function WorkspaceChatPage() {
  return (
    <section className="split">
      <div>
        <PageHeader
          title="AskMe"
          description="Grounded question answering will call the authenticated `/ask` endpoint and display citations when evidence is available."
        />
        <Card>
          <Input disabled helpText="Question submission is connected in Frontend Day 4." label="Question" />
        </Card>
      </div>
      <EmptyState
        title="No answer generated"
        message="The frontend does not create sample answers or hard-code evidence during the foundation milestone."
      />
    </section>
  );
}
