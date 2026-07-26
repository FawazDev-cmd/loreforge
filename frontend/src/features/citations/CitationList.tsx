import type { AskCitation } from "../query/api";
import { CitationCard } from "./CitationCard";

type CitationListProps = {
  citations: AskCitation[];
};

export function CitationList({ citations }: CitationListProps) {
  return (
    <section className="stack" aria-label="Citations">
      <h2>Citations</h2>
      {citations.map((citation) => (
        <CitationCard citation={citation} key={citation.citation_id} />
      ))}
    </section>
  );
}

