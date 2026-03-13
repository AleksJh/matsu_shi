import { useState, useEffect } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { createSession, listAvailableModels } from '../../api/sessions'

export function MachineModelSelector() {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState(false)

  const addSession = useSessionStore((s) => s.addSession)
  const setActiveSession = useSessionStore((s) => s.setActiveSession)

  useEffect(() => {
    listAvailableModels()
      .then(setModels)
      .catch(() => setFetchError(true))
  }, [])

  async function handleSelect(model: string) {
    setLoading(true)
    try {
      const session = await createSession(model)
      addSession(session)
      setActiveSession(String(session.id))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="px-4 py-3">
      <p
        className="mb-2 text-xs font-semibold uppercase tracking-wide"
        style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
      >
        Выберите модель техники
      </p>

      {fetchError || models.length === 0 ? (
        <p
          className="text-sm"
          style={{ color: 'var(--tg-theme-hint-color, #999999)' }}
        >
          Документы не загружены. Обратитесь к администратору.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {models.map((model) => (
            <button
              key={model}
              disabled={loading}
              onClick={() => handleSelect(model)}
              className="rounded-full px-3 py-1 text-sm font-medium transition-opacity disabled:opacity-50"
              style={{
                background: 'var(--tg-theme-button-color, #2481cc)',
                color: 'var(--tg-theme-button-text-color, #ffffff)',
              }}
            >
              {loading ? 'Создание сессии...' : model}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
