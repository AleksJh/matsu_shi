import { useState, useCallback } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Message, Citation } from '../../types'
import { CitationBlock } from './CitationBlock'
import { ImageViewer } from './ImageViewer'
import { FeedbackButtons } from './FeedbackButtons'
import { InlineCitation } from './InlineCitation'

// Configure marked once
marked.setOptions({ gfm: true, breaks: true })

/**
 * Replace [N] markers in the answer string with <span> tags that survive
 * DOMPurify sanitization and can be targeted via event delegation.
 */
function injectCitationSpans(answer: string, citations: Citation[]): string {
  return answer.replace(/\[(\d+)\]/g, (_match, numStr) => {
    const idx = parseInt(numStr, 10)
    if (idx >= 1 && idx <= citations.length) {
      return `<span class="citation-marker" data-idx="${idx}" style="display:inline;cursor:pointer;color:var(--tg-theme-link-color,#2481cc);font-size:0.75em;vertical-align:super;font-weight:600;">[${idx}]</span>`
    }
    return ''  // Strip out-of-range markers
  })
}

interface MarkdownContentProps {
  content: string
}

function MarkdownContent({ content }: MarkdownContentProps) {
  // Allow span and data-idx through DOMPurify so citation markers survive
  const html = DOMPurify.sanitize(marked(content) as string, {
    ADD_TAGS: ['span'],
    ADD_ATTR: ['data-idx', 'style'],
  })
  return (
    <div
      className="prose prose-sm max-w-none"
      style={{ color: 'inherit' }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const citations = message.response?.citations ?? []
  const firstVisual = citations.find((c) => c.visual_url)?.visual_url ?? null

  // Track which citation index is active for the popover (1-based, or null)
  const [activeCitationIdx, setActiveCitationIdx] = useState<number | null>(null)

  // Event delegation handler on the markdown container
  const handleContainerClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const el = (e.target as HTMLElement).closest<HTMLElement>('[data-idx]')
      if (el?.dataset.idx) {
        const idx = parseInt(el.dataset.idx, 10)
        setActiveCitationIdx((prev) => (prev === idx ? null : idx))
      }
    },
    [],
  )

  // Pre-process content: inject citation spans before passing to MarkdownContent
  const processedContent =
    !isUser && citations.length > 0
      ? injectCitationSpans(message.content, citations)
      : message.content

  return (
    <div className={`flex px-4 py-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] px-4 py-3 text-sm ${
          isUser ? 'rounded-2xl rounded-tr-sm' : 'rounded-2xl rounded-tl-sm'
        }`}
        style={{
          background: isUser
            ? 'var(--tg-theme-button-color, #2481cc)'
            : 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
          color: isUser
            ? 'var(--tg-theme-button-text-color, #ffffff)'
            : 'var(--tg-theme-text-color, #000000)',
        }}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <>
            {/* Wrap markdown in a div that handles citation click via delegation */}
            <div style={{ position: 'relative' }} onClick={handleContainerClick}>
              <MarkdownContent content={processedContent} />
              {/* Render active citation popover anchored to the container */}
              {activeCitationIdx !== null && citations[activeCitationIdx - 1] && (
                <InlineCitation
                  index={activeCitationIdx}
                  citation={citations[activeCitationIdx - 1]}
                  onClose={() => setActiveCitationIdx(null)}
                />
              )}
            </div>
            {citations.length > 0 && <CitationBlock citations={citations} />}
            {firstVisual && <ImageViewer url={firstVisual} />}
            {message.query_id && <FeedbackButtons queryId={message.query_id} />}
            {message.response?.model_used === 'advanced' && (
              <span
                className="mt-2 inline-flex cursor-help items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                style={{
                  background: 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
                  color: 'var(--tg-theme-hint-color, #888888)',
                  border: '1px solid var(--tg-theme-hint-color, #cccccc)',
                }}
                title="Для этого сложного запроса была использована расширенная языковая модель с глубоким контекстным анализом"
              >
                🔬 Расширенный анализ
              </span>
            )}
          </>
        )}
      </div>
    </div>
  )
}
