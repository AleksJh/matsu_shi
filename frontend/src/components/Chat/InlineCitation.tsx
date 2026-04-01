import { useEffect, useRef } from 'react'
import type { Citation } from '../../types'

interface InlineCitationProps {
  index: number     // 1-based citation number
  citation: Citation
  onClose: () => void
}

export function InlineCitation({ index, citation, onClose }: InlineCitationProps) {
  const ref = useRef<HTMLDivElement>(null)

  // Close popover when clicking outside
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        // Also ignore clicks on citation-marker spans (those toggle, not close)
        const target = e.target as HTMLElement
        if (!target.closest('[data-idx]')) {
          onClose()
        }
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [onClose])

  return (
    <div
      ref={ref}
      role="tooltip"
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        zIndex: 100,
        background: 'var(--tg-theme-bg-color, #ffffff)',
        border: '1px solid var(--tg-theme-hint-color, #cccccc)',
        borderRadius: '8px',
        padding: '8px 12px',
        minWidth: '200px',
        maxWidth: '280px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
        fontSize: '0.82rem',
        lineHeight: 1.4,
        color: 'var(--tg-theme-text-color, #000000)',
        whiteSpace: 'normal',
        textAlign: 'left',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
        <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>
          [{index}] {citation.doc_name}
        </span>
        <button
          onClick={onClose}
          aria-label="Закрыть"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '0 0 0 8px',
            fontSize: '1rem',
            lineHeight: 1,
            color: 'var(--tg-theme-hint-color, #999999)',
          }}
        >
          ×
        </button>
      </div>
      <span style={{ display: 'block', color: 'var(--tg-theme-hint-color, #666666)', fontSize: '0.8rem' }}>
        {citation.section}
      </span>
      {citation.page > 0 && (
        <span style={{ display: 'block', color: 'var(--tg-theme-hint-color, #666666)', fontSize: '0.8rem' }}>
          Стр. {citation.page}
        </span>
      )}
    </div>
  )
}
