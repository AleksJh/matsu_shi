import { useEffect } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { useMessageStore } from '../../store/messageStore'
import { listSessions } from '../../api/sessions'
import { getSessionHistory } from '../../api/history'
import type { Session } from '../../types'

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'только что'
  if (min < 60) return `${min} мин. назад`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} ч. назад`
  const d = Math.floor(h / 24)
  if (d === 1) return 'вчера'
  return `${d} дн. назад`
}

function statusLabel(status: Session['status']): string {
  switch (status) {
    case 'active': return 'Активна'
    case 'paused': return 'Пауза'
    case 'completed': return 'Завершена'
  }
}

function statusColor(status: Session['status']): string {
  switch (status) {
    case 'active': return '#34C759'
    case 'paused': return '#FF9500'
    case 'completed': return 'var(--tg-theme-hint-color, #999999)'
  }
}

export function SessionList() {
  const sessions = useSessionStore((s) => s.sessions)
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const setSessions = useSessionStore((s) => s.setSessions)
  const setActiveSession = useSessionStore((s) => s.setActiveSession)
  const setMessages = useMessageStore((s) => s.setMessages)

  useEffect(() => {
    listSessions().then(setSessions).catch(() => {})
  }, [setSessions])

  async function handleSessionClick(id: string) {
    setActiveSession(id)
    try {
      const messages = await getSessionHistory(id)
      setMessages(id, messages)
    } catch {
      // История недоступна — не блокируем UI
    }
  }

  if (sessions.length === 0) {
    return (
      <div className="px-4 py-3">
        <p
          className="text-sm"
          style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
        >
          Нет диагностических сессий
        </p>
      </div>
    )
  }

  return (
    <ul>
      {sessions.map((session) => {
        const isActive = session.id === activeSessionId
        const title = (session.title ?? session.machine_model).slice(0, 100)
        return (
          <li
            key={session.id}
            onClick={() => handleSessionClick(session.id)}
            className="cursor-pointer px-4 py-3 transition-colors"
            style={{
              background: isActive
                ? 'var(--tg-theme-secondary-bg-color, #f0f0f0)'
                : 'transparent',
              borderLeft: isActive
                ? '3px solid var(--tg-theme-button-color, #2481cc)'
                : '3px solid transparent',
            }}
          >
            <p
              className="truncate text-sm font-medium"
              style={{ color: 'var(--tg-theme-text-color, #000000)' }}
            >
              {title}
            </p>
            <div className="mt-1 flex items-center gap-2">
              <span
                className="text-xs font-medium"
                style={{ color: statusColor(session.status) }}
              >
                {statusLabel(session.status)}
              </span>
              <span
                className="text-xs"
                style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
              >
                {relativeTime(session.updated_at)}
              </span>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
