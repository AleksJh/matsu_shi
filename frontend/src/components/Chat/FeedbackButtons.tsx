import { useState } from 'react'
import { submitFeedback } from '../../api/feedback'
import axios from 'axios'

interface FeedbackButtonsProps {
  queryId: string
}

export function FeedbackButtons({ queryId }: FeedbackButtonsProps) {
  const [voted, setVoted] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleVote(rating: 1 | -1) {
    if (voted || submitting) return
    setSubmitting(true)
    try {
      await submitFeedback(queryId, rating)
      setVoted(true)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        // Already voted — treat silently as success
        setVoted(true)
      } else {
        console.error('Feedback error:', err)
      }
    } finally {
      setSubmitting(false)
    }
  }

  const disabled = voted || submitting

  return (
    <div className="mt-2 flex gap-3">
      <button
        onClick={() => handleVote(1)}
        disabled={disabled}
        aria-label="Полезно"
        className="text-base leading-none transition-opacity"
        style={{
          opacity: disabled ? 0.4 : 1,
          cursor: disabled ? 'default' : 'pointer',
        }}
      >
        👍
      </button>
      <button
        onClick={() => handleVote(-1)}
        disabled={disabled}
        aria-label="Бесполезно"
        className="text-base leading-none transition-opacity"
        style={{
          opacity: disabled ? 0.4 : 1,
          cursor: disabled ? 'default' : 'pointer',
        }}
      >
        👎
      </button>
    </div>
  )
}
