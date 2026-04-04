import { useEffect, useRef, useState } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { useMessageStore } from '../../store/messageStore'
import { listSessions, deleteSession, renameSession } from '../../api/sessions'
import { getSessionHistory } from '../../api/history'
import type { Session } from '../../types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  if (isNaN(diff) || diff < 0) return ''
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'только что'
  if (min < 60) return `${min} мин. назад`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} ч. назад`
  const d = Math.floor(h / 24)
  if (d === 1) return 'вчера'
  return `${d} дн. назад`
}

function dateBucket(iso: string | null | undefined): string {
  if (!iso) return 'Ранее'
  const diff = Date.now() - new Date(iso).getTime()
  if (isNaN(diff)) return 'Ранее'
  const d = Math.floor(diff / 86400000)
  if (d < 1) return 'Сегодня'
  if (d < 2) return 'Вчера'
  if (d < 7) return 'Эта неделя'
  return 'Ранее'
}

function statusColor(status: Session['status']): string {
  switch (status) {
    case 'active': return '#34C759'
    case 'paused': return '#FF9500'
    case 'completed': return 'var(--tg-theme-hint-color, #999999)'
  }
}

// ---------------------------------------------------------------------------
// Session item with actions
// ---------------------------------------------------------------------------

interface SessionItemProps {
  session: Session
  isActive: boolean
  onSelect: (id: string) => void
}

function SessionItem({ session, isActive, onSelect }: SessionItemProps) {
  const removeSession = useSessionStore((s) => s.removeSession)
  const updateSessionTitle = useSessionStore((s) => s.updateSessionTitle)
  const setActiveSession = useSessionStore((s) => s.setActiveSession)

  const [menuOpen, setMenuOpen] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const displayTitle = (session.title ?? session.machine_model).slice(0, 80)

  function handleMenuToggle(e: React.MouseEvent) {
    e.stopPropagation()
    setMenuOpen((v) => !v)
  }

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation()
    setMenuOpen(false)
    const confirmed = window.confirm(`Удалить сессию "${displayTitle}"?\nВсе сообщения будут удалены.`)
    if (!confirmed) return
    try {
      await deleteSession(session.id)
      removeSession(session.id)
    } catch {
      // Silent fail — session remains visible
    }
  }

  function handleRenameStart(e: React.MouseEvent) {
    e.stopPropagation()
    setMenuOpen(false)
    setRenameValue(session.title ?? session.machine_model)
    setRenaming(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  async function handleRenameCommit() {
    const trimmed = renameValue.trim()
    if (trimmed && trimmed !== (session.title ?? session.machine_model)) {
      try {
        await renameSession(session.id, trimmed)
        updateSessionTitle(session.id, trimmed)
      } catch {
        // Revert on error
      }
    }
    setRenaming(false)
  }

  function handleRenameKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') handleRenameCommit()
    if (e.key === 'Escape') setRenaming(false)
  }

  // Close menu when clicking outside
  useEffect(() => {
    if (!menuOpen) return
    function close() { setMenuOpen(false) }
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [menuOpen])

  return (
    <li
      className="relative cursor-pointer px-4 py-2.5 transition-colors"
      style={{
        background: isActive
          ? 'var(--tg-theme-secondary-bg-color, #f0f0f0)'
          : 'transparent',
        borderLeft: isActive
          ? '3px solid var(--tg-theme-button-color, #2481cc)'
          : '3px solid transparent',
      }}
      onClick={() => !renaming && onSelect(session.id)}
    >
      {/* Title row */}
      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          {renaming ? (
            <input
              ref={inputRef}
              className="w-full rounded px-1 text-sm outline-none"
              style={{
                background: 'var(--tg-theme-bg-color, #ffffff)',
                color: 'var(--tg-theme-text-color, #000000)',
                border: '1px solid var(--tg-theme-button-color, #2481cc)',
              }}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={handleRenameCommit}
              onKeyDown={handleRenameKeyDown}
              maxLength={100}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <p
              className="truncate text-sm font-medium leading-snug"
              style={{ color: 'var(--tg-theme-text-color, #000000)' }}
            >
              {displayTitle}
            </p>
          )}
        </div>
        {/* ⋮ menu button */}
        {!renaming && (
          <button
            className="ml-1 flex-shrink-0 rounded px-1 text-base leading-none opacity-50 hover:opacity-100"
            style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
            onClick={handleMenuToggle}
            aria-label="Действия"
          >
            ⋮
          </button>
        )}
      </div>

      {/* Meta row: model tag + status + time */}
      {!renaming && (
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span
            className="rounded px-1.5 py-0.5 text-xs font-medium"
            style={{
              background: 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
              color: 'var(--tg-theme-hint-color, #888888)',
              border: '1px solid var(--tg-theme-hint-color, #cccccc)',
            }}
          >
            {session.machine_model}
          </span>
          <span
            className="text-xs font-medium"
            style={{ color: statusColor(session.status) }}
          >
            {session.status === 'active' ? '●' : session.status === 'paused' ? '⏸' : '✓'}
          </span>
          {relativeTime(session.updated_at) && (
            <span
              className="text-xs"
              style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
            >
              {relativeTime(session.updated_at)}
            </span>
          )}
        </div>
      )}

      {/* Inline action menu */}
      {menuOpen && (
        <div
          className="absolute right-2 top-8 z-10 flex flex-col overflow-hidden rounded-lg shadow-lg"
          style={{
            background: 'var(--tg-theme-bg-color, #ffffff)',
            border: '1px solid var(--tg-theme-hint-color, #cccccc)',
            minWidth: '140px',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="flex items-center gap-2 px-3 py-2 text-left text-sm hover:opacity-80"
            style={{ color: 'var(--tg-theme-text-color, #000000)' }}
            onClick={handleRenameStart}
          >
            ✏️ Переименовать
          </button>
          <button
            className="flex items-center gap-2 px-3 py-2 text-left text-sm hover:opacity-80"
            style={{ color: '#FF3B30' }}
            onClick={handleDelete}
          >
            🗑️ Удалить
          </button>
        </div>
      )}
    </li>
  )
}

// ---------------------------------------------------------------------------
// Accordion group for "by model" view
// ---------------------------------------------------------------------------

interface ModelGroupProps {
  model: string
  sessions: Session[]
  defaultOpen: boolean
  activeSessionId: string | null
  onSelect: (id: string) => void
}

function ModelGroup({ model, sessions, defaultOpen, activeSessionId, onSelect }: ModelGroupProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div>
      <button
        className="flex w-full items-center justify-between px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide"
        style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
        onClick={() => setOpen((v) => !v)}
      >
        <span>{model} ({sessions.length})</span>
        <span className="text-xs">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <ul>
          {sessions.map((s) => (
            <SessionItem
              key={s.id}
              session={s}
              isActive={s.id === activeSessionId}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type ViewMode = 'date' | 'model'

export function SessionList() {
  const sessions = useSessionStore((s) => s.sessions)
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const setSessions = useSessionStore((s) => s.setSessions)
  const setActiveSession = useSessionStore((s) => s.setActiveSession)
  const setMessages = useMessageStore((s) => s.setMessages)
  const [viewMode, setViewMode] = useState<ViewMode>('date')

  useEffect(() => {
    listSessions().then(setSessions).catch(() => {})
  }, [setSessions])

  async function handleSessionClick(id: string) {
    setActiveSession(id)
    try {
      const messages = await getSessionHistory(id)
      setMessages(id, messages)
    } catch {
      // History unavailable — don't block UI
    }
  }

  if (sessions.length === 0) {
    return (
      <div className="px-4 py-3">
        <p className="text-sm" style={{ color: 'var(--tg-theme-hint-color, #999999)' }}>
          Нет диагностических сессий
        </p>
      </div>
    )
  }

  return (
    <div>
      {/* View mode tabs */}
      <div className="flex gap-1 px-4 pb-2">
        {(['date', 'model'] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
            style={{
              background: viewMode === mode
                ? 'var(--tg-theme-button-color, #2481cc)'
                : 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
              color: viewMode === mode
                ? 'var(--tg-theme-button-text-color, #ffffff)'
                : 'var(--tg-theme-hint-color, #888888)',
            }}
          >
            {mode === 'date' ? 'По дате' : 'По модели'}
          </button>
        ))}
      </div>

      {viewMode === 'date' ? (
        <DateView sessions={sessions} activeSessionId={activeSessionId} onSelect={handleSessionClick} />
      ) : (
        <ModelView sessions={sessions} activeSessionId={activeSessionId} onSelect={handleSessionClick} />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Date view: grouped by time bucket
// ---------------------------------------------------------------------------

function DateView({ sessions, activeSessionId, onSelect }: {
  sessions: Session[]
  activeSessionId: string | null
  onSelect: (id: string) => void
}) {
  const bucketOrder = ['Сегодня', 'Вчера', 'Эта неделя', 'Ранее']
  const grouped: Record<string, Session[]> = {}
  for (const s of sessions) {
    const bucket = dateBucket(s.updated_at)
    if (!grouped[bucket]) grouped[bucket] = []
    grouped[bucket].push(s)
  }

  return (
    <div>
      {bucketOrder.filter((b) => grouped[b]?.length).map((bucket) => (
        <div key={bucket}>
          <div
            className="px-4 py-1 text-xs font-semibold uppercase tracking-wide"
            style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
          >
            {bucket}
          </div>
          <ul>
            {grouped[bucket].map((s) => (
              <SessionItem
                key={s.id}
                session={s}
                isActive={s.id === activeSessionId}
                onSelect={onSelect}
              />
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Model view: accordion groups
// ---------------------------------------------------------------------------

function ModelView({ sessions, activeSessionId, onSelect }: {
  sessions: Session[]
  activeSessionId: string | null
  onSelect: (id: string) => void
}) {
  // Group sessions by machine_model, preserving insertion order
  const modelMap = new Map<string, Session[]>()
  for (const s of sessions) {
    const key = s.machine_model ?? 'Без модели'
    if (!modelMap.has(key)) modelMap.set(key, [])
    modelMap.get(key)!.push(s)
  }
  const models = Array.from(modelMap.entries())

  return (
    <div>
      {models.map(([model, slist], idx) => (
        <ModelGroup
          key={model}
          model={model}
          sessions={slist}
          defaultOpen={idx === 0}
          activeSessionId={activeSessionId}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
