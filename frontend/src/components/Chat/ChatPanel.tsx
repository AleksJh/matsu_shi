import { useRef, useEffect, useState } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { useChat } from '../../hooks/useChat'
import { useSSE } from '../../hooks/useSSE'
import { useThemeStore } from '../../store/themeStore'
import { MessageBubble } from './MessageBubble'
import { NewSessionPanel } from './NewSessionPanel'

function TypingIndicator() {
  return (
    <div className="flex justify-start px-4 py-2">
      <div
        className="flex gap-1 rounded-2xl rounded-tl-sm px-4 py-3"
        style={{ background: 'var(--tg-theme-secondary-bg-color, #f0f0f0)' }}
      >
        <span
          className="h-2 w-2 animate-bounce rounded-full [animation-delay:-0.3s]"
          style={{ background: 'var(--tg-theme-hint-color, #999999)' }}
        />
        <span
          className="h-2 w-2 animate-bounce rounded-full [animation-delay:-0.15s]"
          style={{ background: 'var(--tg-theme-hint-color, #999999)' }}
        />
        <span
          className="h-2 w-2 animate-bounce rounded-full"
          style={{ background: 'var(--tg-theme-hint-color, #999999)' }}
        />
      </div>
    </div>
  )
}

interface ChatPanelProps {
  onMenuClick: () => void
}

export function ChatPanel({ onMenuClick }: ChatPanelProps) {
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const sessions = useSessionStore((s) => s.sessions)
  const { messages, isLoading } = useChat()
  const { sendMessage } = useSSE()
  const bottomRef = useRef<HTMLDivElement>(null)
  const [inputText, setInputText] = useState('')

  const { theme, toggle: toggleTheme } = useThemeStore()
  const activeSession = activeSessionId ? sessions.find((s) => s.id === activeSessionId) : null
  const title = activeSession
    ? (activeSession.title ?? activeSession.machine_model ?? 'Матсу Ши')
    : 'Матсу Ши'

  async function handleSend() {
    if (!activeSessionId || isLoading || !inputText.trim()) return
    const text = inputText
    setInputText('')
    await sendMessage(activeSessionId, text)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div
      className="flex h-full flex-col"
      style={{
        background: 'var(--tg-theme-bg-color, #ffffff)',
        color: 'var(--tg-theme-text-color, #000000)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3"
        style={{ background: 'var(--ms-dark)' }}
      >
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuClick}
          className="text-xl leading-none sm:hidden"
          style={{ color: 'rgba(255,255,255,0.85)' }}
          aria-label="Открыть меню"
        >
          &#9776;
        </button>
        <div className="min-w-0 flex-1 flex flex-col">
          <span className="truncate font-semibold leading-tight" style={{ color: '#ffffff' }}>{title}</span>
          {activeSession?.machine_model && (
            <span
              className="truncate text-xs"
              style={{ color: 'rgba(255,255,255,0.55)' }}
            >
              {activeSession.machine_model}
            </span>
          )}
        </div>
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="ml-2 flex-shrink-0 text-xl leading-none rounded-full w-8 h-8 flex items-center justify-center transition-opacity hover:opacity-70"
          style={{ color: 'rgba(255,255,255,0.85)' }}
          aria-label={theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}
          title={theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {!activeSessionId ? (
          <NewSessionPanel />
        ) : messages.length === 0 && !isLoading ? (
          <div className="flex flex-1 items-center justify-center">
            <p style={{ color: 'var(--tg-theme-hint-color, #999999)' }}>
              Задайте первый вопрос
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto py-2">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isLoading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input Area (6.8) */}
      {activeSessionId && (
        <div
          className="flex items-end gap-2 px-3 py-2"
          style={{ borderTop: '1px solid var(--tg-theme-hint-color, #cccccc)' }}
        >
          <textarea
            className="flex-1 resize-none rounded-xl px-3 py-2 text-sm outline-none"
            style={{
              background: 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
              color: 'var(--tg-theme-text-color, #000000)',
              maxHeight: '120px',
            }}
            rows={1}
            placeholder="Введите вопрос…"
            value={inputText}
            disabled={isLoading}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !inputText.trim()}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-white disabled:opacity-40"
            style={{ background: 'var(--ms-primary)' }}
            aria-label="Отправить"
          >
            &#9658;
          </button>
        </div>
      )}
    </div>
  )
}
