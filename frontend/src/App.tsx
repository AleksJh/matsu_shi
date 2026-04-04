import { useEffect } from 'react'
import { useTelegramAuth } from './hooks/useTelegramAuth'
import { AppLayout } from './components/Layout/AppLayout'
import { useThemeStore } from './store/themeStore'

function App() {
  const { loading, error } = useTelegramAuth()
  const theme = useThemeStore((s) => s.theme)

  useEffect(() => {
    document.body.setAttribute('data-theme', theme)
  }, [theme])

  if (loading) return (
    <div className="flex h-screen items-center justify-center">
      <p className="text-[var(--tg-theme-hint-color)]">Загрузка...</p>
    </div>
  )

  if (error) return (
    <div className="flex h-screen items-center justify-center p-4">
      <div className="text-center max-w-xs">
        <p className="text-red-500 mb-3">{error}</p>
        {error.includes('Telegram') && (
          <p className="text-sm text-gray-500">
            Откройте приложение через кнопку «🔧 Открыть Matsu Shi» в чате с ботом.
          </p>
        )}
      </div>
    </div>
  )

  return <AppLayout />
}

export default App
