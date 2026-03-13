import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Message } from '../../types'
import { CitationBlock } from './CitationBlock'
import { ImageViewer } from './ImageViewer'
import { FeedbackButtons } from './FeedbackButtons'

// Configure marked once
marked.setOptions({ gfm: true, breaks: true })

interface MarkdownContentProps {
  content: string
}

function MarkdownContent({ content }: MarkdownContentProps) {
  const html = DOMPurify.sanitize(marked(content) as string)
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
            <MarkdownContent content={message.content} />
            {citations.length > 0 && <CitationBlock citations={citations} />}
            {firstVisual && <ImageViewer url={firstVisual} />}
            {message.query_id && <FeedbackButtons queryId={message.query_id} />}
            {message.response?.model_used === 'advanced' && (
              <span
                className="mt-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium"
                style={{
                  background: 'var(--tg-theme-hint-color, #999999)',
                  color: 'var(--tg-theme-button-text-color, #ffffff)',
                }}
              >
                Расширенный анализ
              </span>
            )}
          </>
        )}
      </div>
    </div>
  )
}
