import { useAuthStore } from '../../store/authStore'
import { useSessionStore } from '../../store/sessionStore'
import { SessionList } from './SessionList'

interface SidebarProps {
  onClose: () => void
}

export function Sidebar({ onClose }: SidebarProps) {
  const user = useAuthStore((s) => s.user)
  const setActiveSession = useSessionStore((s) => s.setActiveSession)

  return (
    <div
      className="flex h-full flex-col"
      style={{
        background: 'var(--tg-theme-bg-color, #ffffff)',
        color: 'var(--tg-theme-text-color, #000000)',
        borderRight: '1px solid var(--tg-theme-hint-color, #cccccc)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <span className="font-semibold truncate">
          {user?.first_name ?? 'Матсу Ши'}
        </span>
        {/* Close button — mobile only */}
        <button
          onClick={onClose}
          className="sm:hidden ml-2 text-xl leading-none"
          style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
          aria-label="Закрыть меню"
        >
          ×
        </button>
      </div>

      {/* New session button */}
      <div className="px-4 pb-3">
        <button
          onClick={() => setActiveSession(null)}
          className="w-full rounded-lg px-4 py-2 text-sm font-medium"
          style={{
            background: 'var(--ms-green)',
            color: '#ffffff',
          }}
        >
          Новая сессия
        </button>
      </div>

      {/* Session list */}
      <div className="px-4 pb-2">
        <p
          className="text-xs font-medium uppercase tracking-wide"
          style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
        >
          История диагностики
        </p>
      </div>
      <div className="flex-1 overflow-y-auto">
        <SessionList />
      </div>
    </div>
  )
}
