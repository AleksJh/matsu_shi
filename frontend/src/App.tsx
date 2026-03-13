import { useTelegramAuth } from './hooks/useTelegramAuth'
import { AppLayout } from './components/Layout/AppLayout'

function App() {
  const { loading, error } = useTelegramAuth()

  if (loading) return (
    <div className="flex h-screen items-center justify-center">
      <p className="text-[var(--tg-theme-hint-color)]">Загрузка...</p>
    </div>
  )

  if (error) return (
    <div className="flex h-screen items-center justify-center p-4">
      <p className="text-red-500 text-center">{error}</p>
    </div>
  )

  return <AppLayout />
}

export default App
