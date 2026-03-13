import WebApp from '@twa-dev/sdk'
import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import { useAuthStore } from '../store/authStore'

export function useTelegramAuth() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { setAuth } = useAuthStore()

  useEffect(() => {
    // Apply Telegram theme tokens to CSS variables
    const { bg_color, text_color, hint_color, button_color, button_text_color } =
      WebApp.themeParams
    const root = document.documentElement
    if (bg_color) root.style.setProperty('--tg-theme-bg-color', bg_color)
    if (text_color) root.style.setProperty('--tg-theme-text-color', text_color)
    if (hint_color) root.style.setProperty('--tg-theme-hint-color', hint_color)
    if (button_color) root.style.setProperty('--tg-theme-button-color', button_color)
    if (button_text_color) root.style.setProperty('--tg-theme-button-text-color', button_text_color)

    // Authenticate via Telegram initData
    const initData = WebApp.initData
    if (!initData) {
      setError('Приложение должно быть открыто через Telegram.')
      setLoading(false)
      return
    }

    apiClient
      .post('/api/v1/auth/telegram', { init_data: initData })
      .then((res) => {
        setAuth(res.data.access_token, res.data.user)
        WebApp.ready() // Signal Telegram that the app is ready
      })
      .catch(() => setError('Ошибка авторизации. Попробуйте снова.'))
      .finally(() => setLoading(false))
  }, [])

  return { loading, error }
}
