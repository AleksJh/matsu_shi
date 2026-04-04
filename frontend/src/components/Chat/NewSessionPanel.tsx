import { useState, useEffect } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { createSession, listAvailableModels } from '../../api/sessions'

export function NewSessionPanel() {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState(false)
  const [creatingModel, setCreatingModel] = useState<string | null>(null)

  const addSession = useSessionStore((s) => s.addSession)
  const setActiveSession = useSessionStore((s) => s.setActiveSession)

  useEffect(() => {
    listAvailableModels()
      .then(setModels)
      .catch(() => setFetchError(true))
  }, [])

  async function handleSelect(model: string) {
    setLoading(true)
    setCreatingModel(model)
    try {
      const session = await createSession(model)
      addSession(session)
      setActiveSession(String(session.id))
    } finally {
      setLoading(false)
      setCreatingModel(null)
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-8">
      {/* Logo */}
      <img
        src="/logo.jpg"
        alt="Matsu Shi"
        className="mb-4 h-20 w-20 rounded-2xl object-cover shadow-lg"
      />

      <h2
        className="mb-1 text-lg font-semibold"
        style={{ color: 'var(--tg-theme-text-color, #000000)' }}
      >
        Матсу Ши
      </h2>
      <p
        className="mb-6 text-center text-sm"
        style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
      >
        Выберите модель техники для начала диагностики
      </p>

      {fetchError ? (
        <p className="text-sm" style={{ color: 'var(--tg-theme-hint-color, #999999)' }}>
          Документы не загружены. Обратитесь к администратору.
        </p>
      ) : models.length === 0 ? (
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-t-transparent"
          style={{ borderColor: 'var(--tg-theme-button-color, #2481cc)' }}
        />
      ) : (
        <div className="flex flex-wrap justify-center gap-3">
          {models.map((model) => (
            <button
              key={model}
              disabled={loading}
              onClick={() => handleSelect(model)}
              className="rounded-xl px-5 py-3 text-sm font-semibold shadow-sm transition-opacity disabled:opacity-50"
              style={{
                background: creatingModel === model
                  ? 'var(--ms-steel)'
                  : 'var(--ms-green)',
                color: '#ffffff',
                minWidth: '120px',
              }}
            >
              {creatingModel === model ? 'Создание...' : model}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
