import { useState } from "react";

import type { AskCitation } from "../query/api";

type CitationCardProps = {
  citation: AskCitation;
};

export function CitationCard({ citation }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article className="citation-card">
      <header className="citation-card__header">
        <div>
          <h3>{citation.citation_id}</h3>
          <p>{citation.filename}</p>
        </div>
        <button aria-expanded={expanded} onClick={() => setExpanded((value) => !value)} type="button">
          {expanded ? "Hide evidence" : "Show evidence"}
        </button>
      </header>
      <dl className="citation-card__meta">
        <div>
          <dt>Filename</dt>
          <dd>{citation.filename}</dd>
        </div>
        <div>
          <dt>Page</dt>
          <dd>{citation.page_number}</dd>
        </div>
        <div>
          <dt>Chunk ID</dt>
          <dd>{citation.chunk_id}</dd>
        </div>
      </dl>
      {expanded ? (
        <div className="citation-card__evidence">
          <p>Evidence excerpts are not yet returned by the backend.</p>
        </div>
      ) : null}
    </article>
  );
}