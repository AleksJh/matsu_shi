import { useEffect, useState } from 'react'
import { listQueries, getQuery, QueryItem, QueryDetail, QueryFilters } from '../api/queries'

const LIMIT = 50

const MODEL_BADGE: Record<string, string> = {
  lite: 'bg-blue-100 text-blue-800',
  advanced: 'bg-purple-100 text-purple-800',
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return (
    d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' +
    d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  )
}

function truncate(text: string, max = 100): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}

function feedbackIcon(rating: number | null): string {
  if (rating === 1) return '👍'
  if (rating === -1) return '👎'
  return '—'
}

export default function QueriesPage() {
  const [items, setItems] = useState<QueryItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [filterUserId, setFilterUserId] = useState('')
  const [filterSince, setFilterSince] = useState('')
  const [filterModel, setFilterModel] = useState('')
  const [page, setPage] = useState(1)

  const [detail, setDetail] = useState<QueryDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    setError(null)
    const filters: QueryFilters = {}
    if (filterUserId) filters.user_id = Number(filterUserId)
    if (filterSince) filters.since = new Date(filterSince).toISOString()
    if (filterModel) filters.model_used = filterModel
    listQueries(filters, LIMIT, (page - 1) * LIMIT)
      .then(setItems)
      .catch(() => setError('Не удалось загрузить список запросов.'))
      .finally(() => setIsLoading(false))
  }, [filterUserId, filterSince, filterModel, page])

  function handleFilterChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  function openDetail(id: number) {
    setDetailLoading(true)
    setDetail(null)
    getQuery(id)
      .then(setDetail)
      .catch(() => {})
      .finally(() => setDetailLoading(false))
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Запросы</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          type="number"
          placeholder="User ID"
          value={filterUserId}
          onChange={handleFilterChange(setFilterUserId)}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <input
          type="date"
          value={filterSince}
          onChange={handleFilterChange(setFilterSince)}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <select
          value={filterModel}
          onChange={handleFilterChange(setFilterModel)}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        >
          <option value="">Все модели</option>
          <option value="lite">lite</option>
          <option value="advanced">advanced</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">User ID</th>
              <th className="px-4 py-3 text-left">Запрос</th>
              <th className="px-4 py-3 text-left">Модель</th>
              <th className="px-4 py-3 text-right">Score</th>
              <th className="px-4 py-3 text-left">Время</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  Загрузка...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  Нет запросов
                </td>
              </tr>
            ) : (
              items.map((q) => (
                <tr
                  key={q.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => openDetail(q.id)}
                >
                  <td className="px-4 py-3 text-gray-600">{q.user_id ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-800 max-w-xs">{truncate(q.query_text)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        MODEL_BADGE[q.model_used ?? ''] ?? 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {q.model_used ?? '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {q.retrieval_score !== null ? q.retrieval_score.toFixed(2) : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDateTime(q.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {/* Pagination */}
      <div className="flex items-center gap-3 mt-4">
        <button
          disabled={page === 1}
          onClick={() => setPage((p) => p - 1)}
          className="px-3 py-1.5 text-sm rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Назад
        </button>
        <span className="text-sm text-gray-600">Страница {page}</span>
        <button
          disabled={items.length < LIMIT}
          onClick={() => setPage((p) => p + 1)}
          className="px-3 py-1.5 text-sm rounded border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Вперёд
        </button>
      </div>

      {/* Detail Modal */}
      {(detailLoading || detail) && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => { setDetail(null); setDetailLoading(false) }}
        >
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading ? (
              <p className="text-center text-gray-400 py-8">Загрузка...</p>
            ) : detail ? (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold text-gray-800">Детали запроса #{detail.id}</h2>
                  <button
                    onClick={() => setDetail(null)}
                    className="text-gray-400 hover:text-gray-600 text-xl leading-none"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-4 text-sm">
                  <div>
                    <p className="text-xs text-gray-500 uppercase font-medium mb-1">Запрос</p>
                    <p className="text-gray-800 whitespace-pre-wrap bg-gray-50 rounded p-3">
                      {detail.query_text}
                    </p>
                  </div>

                  {detail.response_text && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium mb-1">Ответ</p>
                      <p className="text-gray-800 whitespace-pre-wrap bg-gray-50 rounded p-3">
                        {detail.response_text}
                      </p>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Модель</p>
                      <span
                        className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                          MODEL_BADGE[detail.model_used ?? ''] ?? 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {detail.model_used ?? '—'}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Класс запроса</p>
                      <p className="mt-1 text-gray-700">{detail.query_class ?? '—'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Retrieval score</p>
                      <p className="mt-1 text-gray-700">
                        {detail.retrieval_score !== null
                          ? detail.retrieval_score.toFixed(2)
                          : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Latency</p>
                      <p className="mt-1 text-gray-700">
                        {detail.latency_ms !== null ? `${detail.latency_ms} мс` : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Обратная связь</p>
                      <p className="mt-1 text-gray-700 text-lg">{feedbackIcon(detail.feedback_rating)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Нет ответа</p>
                      <p className="mt-1 text-gray-700">
                        {detail.no_answer === true ? 'Да' : detail.no_answer === false ? 'Нет' : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Время</p>
                      <p className="mt-1 text-gray-700">{formatDateTime(detail.created_at)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">User ID</p>
                      <p className="mt-1 text-gray-700">{detail.user_id ?? '—'}</p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex justify-end">
                  <button
                    onClick={() => setDetail(null)}
                    className="px-4 py-2 text-sm rounded bg-gray-100 hover:bg-gray-200 text-gray-700"
                  >
                    Закрыть
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
