import { useEffect, useState, useCallback } from 'react'
import { getStats, StatsResponse } from '../api/stats'

const REFRESH_INTERVAL_MS = 60_000

const USER_STATUS_LABELS: Record<string, string> = {
  active: 'Активные',
  pending: 'Ожидают',
  denied: 'Отклонены',
  banned: 'Заблокированы',
}

const USER_STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  pending: 'bg-yellow-100 text-yellow-800',
  denied: 'bg-red-100 text-red-800',
  banned: 'bg-gray-200 text-gray-700',
}

function RatioBar({
  leftLabel,
  leftCount,
  leftColor,
  rightLabel,
  rightCount,
  rightColor,
}: {
  leftLabel: string
  leftCount: number
  leftColor: string
  rightLabel: string
  rightCount: number
  rightColor: string
}) {
  const total = leftCount + rightCount
  const leftPct = total === 0 ? 50 : Math.round((leftCount / total) * 100)
  const rightPct = 100 - leftPct

  return (
    <div>
      <div className="flex rounded-full overflow-hidden h-4 mb-2">
        <div className={`${leftColor} transition-all`} style={{ width: `${leftPct}%` }} />
        <div className={`${rightColor} transition-all`} style={{ width: `${rightPct}%` }} />
      </div>
      <div className="flex justify-between text-sm text-gray-600">
        <span>
          {leftLabel}: <span className="font-medium">{leftCount}</span>{' '}
          <span className="text-gray-400">({leftPct}%)</span>
        </span>
        <span>
          {rightLabel}: <span className="font-medium">{rightCount}</span>{' '}
          <span className="text-gray-400">({rightPct}%)</span>
        </span>
      </div>
    </div>
  )
}

function MetricCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl shadow p-5">
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">{title}</h2>
      {children}
    </div>
  )
}

export default function SystemPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const fetchStats = useCallback(() => {
    setIsLoading(true)
    setError(null)
    getStats()
      .then((data) => {
        setStats(data)
        setLastRefresh(new Date())
      })
      .catch(() => setError('Не удалось загрузить статистику.'))
      .finally(() => setIsLoading(false))
  }, [])

  useEffect(() => {
    fetchStats()
    const timer = setInterval(fetchStats, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [fetchStats])

  const modelLite = stats?.model_usage['lite'] ?? 0
  const modelAdvanced = stats?.model_usage['advanced'] ?? 0

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Статистика системы</h1>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-gray-400">
              Обновлено:{' '}
              {lastRefresh.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button
            onClick={fetchStats}
            disabled={isLoading}
            className="px-3 py-1.5 text-sm rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Загрузка…' : 'Обновить'}
          </button>
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {!stats && isLoading && (
        <p className="text-gray-400 text-sm">Загрузка…</p>
      )}

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Queries today */}
          <MetricCard title="Запросы сегодня">
            <p className="text-5xl font-bold text-gray-800">{stats.queries_today}</p>
          </MetricCard>

          {/* Avg retrieval score */}
          <MetricCard title="Avg Retrieval Score (7 дней)">
            <p className="text-5xl font-bold text-gray-800">
              {stats.avg_retrieval_score_7d !== null
                ? stats.avg_retrieval_score_7d.toFixed(2)
                : '—'}
            </p>
            <p className="text-xs text-gray-400 mt-1">Средний косинусный скор за 7 дней</p>
          </MetricCard>

          {/* Model usage */}
          <MetricCard title="Использование моделей">
            <RatioBar
              leftLabel="Lite"
              leftCount={modelLite}
              leftColor="bg-blue-400"
              rightLabel="Advanced"
              rightCount={modelAdvanced}
              rightColor="bg-purple-400"
            />
          </MetricCard>

          {/* Feedback ratio */}
          <MetricCard title="Обратная связь">
            <RatioBar
              leftLabel="👍"
              leftCount={stats.feedback_up}
              leftColor="bg-green-400"
              rightLabel="👎"
              rightCount={stats.feedback_down}
              rightColor="bg-red-400"
            />
          </MetricCard>

          {/* Users by status */}
          <MetricCard title="Пользователи по статусу">
            <div className="flex flex-wrap gap-2">
              {Object.entries(stats.users).map(([status, count]) => (
                <span
                  key={status}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${
                    USER_STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {USER_STATUS_LABELS[status] ?? status}
                  <span className="font-bold">{count}</span>
                </span>
              ))}
            </div>
          </MetricCard>
        </div>
      )}
    </div>
  )
}
