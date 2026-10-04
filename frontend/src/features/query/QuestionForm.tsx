import { type FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { EmptyState } from "../../components/feedback/EmptyState";
import { ErrorState } from "../../components/feedback/ErrorState";
import { LoadingState } from "../../components/feedback/LoadingState";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { useDocumentsQuery } from "../documents/hooks";
import { AnswerPanel } from "./AnswerPanel";
import { useAskQuestion } from "./hooks";

const suggestedQuestions = [
  "What is the company's policy for reporting a security incident?",
  "What should an employee do if a company device is lost or stolen?",
  "How should a security incident be escalated?",
];

export function QuestionForm() {
  const documentsQuery = useDocumentsQuery();
  const askQuestion = useAskQuestion();
  const [question, setQuestion] = useState("");
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  const documents = useMemo(() => documentsQuery.data?.documents ?? [], [documentsQuery.data]);
  const readyDocuments = useMemo(
    () => documents.filter((document) => document.status === "READY"),
    [documents],
  );
  const activeDocuments = useMemo(
    () => documents.filter((document) => document.status === "UPLOADED" || document.status === "INGESTING"),
    [documents],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      setValidationMessage("Enter a question.");
      return;
    }

    setValidationMessage(null);
    await askQuestion.mutateAsync(question).catch(() => undefined);
  }

  if (documentsQuery.isLoading) {
    return <LoadingState label="Loading documents for AskMe." />;
  }

  if (documentsQuery.isError) {
    return <ErrorState message="LoreForge could not load documents for querying." title="Documents unavailable" />;
  }

  if (documents.length === 0) {
    return (
      <EmptyState
        title="No uploaded documents"
        message="Upload a PDF before asking AskMe. Once ingestion finishes, READY documents become available for retrieval."
        action={
          <Button as={Link} to={routes.workspaceUpload}>
            Upload document
          </Button>
        }
      />
    );
  }

  if (readyDocuments.length === 0) {
    return (
      <EmptyState
        title="No READY documents"
        message={
          activeDocuments.length > 0
            ? "Indexing is still running. AskMe becomes available after at least one uploaded document reaches READY."
            : "None of your documents are READY for retrieval yet. Check the document list for current ingestion status."
        }
        action={
          <Button as={Link} to={routes.workspaceDocuments} variant="secondary">
            View documents
          </Button>
        }
      />
    );
  }

  return (
    <div className="stack">
      <Card className="query-context">
        <h2>Collection-wide retrieval</h2>
        <p>
          AskMe searches across all {readyDocuments.length} READY indexed {readyDocuments.length === 1 ? "document" : "documents"} owned by
          your authenticated account. Documents still marked UPLOADED or INGESTING are not available for retrieval yet.
        </p>
        <p className="muted">READY now: {formatReadyDocumentNames(readyDocuments.map((document) => document.filename))}</p>
        <Link to={routes.workspaceDocuments}>View document statuses</Link>
      </Card>
      <Card>
        <form className="form-grid query-form" onSubmit={handleSubmit}>
          <label className="field" htmlFor="question">
            <span className="field__label">Question</span>
            <textarea
              className="input query-textarea"
              id="question"
              onChange={(event) => setQuestion(event.currentTarget.value)}
              placeholder="Ask a grounded question across your READY documents."
              rows={3}
              value={question}
            />
          </label>
          <Button disabled={askQuestion.isPending} type="submit">
            {askQuestion.isPending ? "Asking" : "AskMe"}
          </Button>
          <div className="query-suggestions">
            <span className="query-suggestions__label">Try a question</span>
            <div className="query-suggestions__list">
              {suggestedQuestions.map((suggestion) => (
                <button
                  className="query-suggestion"
                  key={suggestion}
                  onClick={() => setQuestion(suggestion)}
                  type="button"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>

        </form>
      </Card>
      {validationMessage ? <ErrorState message={validationMessage} title="Question not ready" /> : null}
      {askQuestion.isPending ? <LoadingState label="Retrieving evidence and generating an answer." /> : null}
      {askQuestion.isInsufficientEvidence ? (
        <ErrorState message={askQuestion.errorMessage ?? "Evidence was insufficient."} title="Insufficient evidence" />
      ) : null}
      {askQuestion.errorMessage && !askQuestion.isInsufficientEvidence ? (
        <ErrorState message={askQuestion.errorMessage} title="AskMe failed" />
      ) : null}
      {askQuestion.data ? <AnswerPanel response={askQuestion.data} /> : null}
    </div>
  );
}

function formatReadyDocumentNames(filenames: string[]): string {
  const visible = filenames.slice(0, 3).join(", ");
  const remaining = filenames.length - 3;

  if (remaining > 0) {
    return `${visible}, and ${remaining} more`;
  }

  return visible;
}