import type { Citation } from '../../types'

interface CitationBlockProps {
  citations: Citation[]
}

export function CitationBlock({ citations }: CitationBlockProps) {
  return (
    <div
      className="mt-3 text-xs"
      style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
    >
      <p className="mb-1 font-semibold">Источники:</p>
      {citations.map((c, i) => (
        <p key={i} className="truncate">
          {c.doc_name} | {c.section} | Стр. {c.page}
        </p>
      ))}
    </div>
  )
}
