import { useMemo, useState } from "react";

import type { KnowledgeCitation } from "../api/types";

type CitationFooterProps = {
  answer: string;
  citations: KnowledgeCitation[];
};

export function parseCitationRefs(text: string): number[] {
  const matches = text.matchAll(/\[(\d+)\]/g);
  const indices = new Set<number>();
  for (const match of matches) {
    const n = Number.parseInt(match[1], 10);
    if (Number.isFinite(n)) {
      indices.add(n);
    }
  }
  return [...indices].sort((a, b) => a - b);
}

export function CitationFooter({ answer, citations }: CitationFooterProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const referenced = useMemo(() => parseCitationRefs(answer), [answer]);

  if (!citations.length) {
    return null;
  }

  const showAll = referenced.length === 0;
  const visible = showAll
    ? citations
    : citations.filter((c) => referenced.includes(c.index));

  if (!visible.length) {
    return null;
  }

  return (
    <footer className="citation-footer" aria-label="引用来源">
      <p className="citation-footer__title">引用来源</p>
      <ul className="citation-footer__list">
        {visible.map((citation) => (
          <li
            key={`${citation.doc_id}-${citation.chunk_index}`}
            className={`citation-footer__item${
              referenced.includes(citation.index) ? " citation-footer__item--active" : ""
            }`}
          >
            <button
              type="button"
              className="citation-footer__head"
              onClick={() =>
                setExpanded((prev) =>
                  prev === citation.index ? null : citation.index,
                )
              }
            >
              <span className="citation-footer__index">[{citation.index}]</span>
              <span className="citation-footer__filename">{citation.filename}</span>
            </button>
            {(expanded === citation.index || showAll) && (
              <p className="citation-footer__excerpt">{citation.excerpt}</p>
            )}
          </li>
        ))}
      </ul>
    </footer>
  );
}
