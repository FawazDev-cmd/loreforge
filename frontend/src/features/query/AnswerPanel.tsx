import { CitationList } from "../citations/CitationList";
import type { AskResponse } from "./api";

type AnswerPanelProps = {
  response: AskResponse;
};

export function AnswerPanel({ response }: AnswerPanelProps) {
  return (
    <section className="answer-panel" aria-labelledby="grounded-answer-heading">
      <header>
        <p className="muted">Collection-wide answer</p>
        <h2 id="grounded-answer-heading">Grounded answer</h2>
      </header>
      <p className="answer-panel__text">{response.answer}</p>
      <p className="muted">Request ID: {response.request_id}</p>
      <CitationList citations={response.citations} />
    </section>
  );
}