import type { AskCitation } from "../query/api";

type CitationCardProps = {
  citation: AskCitation;
};

export function CitationCard({ citation }: CitationCardProps) {

  return (
    <article className="citation-card">
      <header className="citation-card__header">
        <div>
          <h3>{citation.citation_id}</h3>
          <p>{citation.filename}</p>
        </div>
      </header>
      <dl className="citation-card__meta">
        <div>
          <dt>Page</dt>
          <dd>{citation.page_number}</dd>
        </div>
        <div>
          <dt>Chunk ID</dt>
          <dd>{citation.chunk_id}</dd>
        </div>
      </dl>
    </article>
  );
}