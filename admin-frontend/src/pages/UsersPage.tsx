import { useEffect, useState, useCallback } from 'react'
import { listUsers, updateUserStatus, UserItem } from '../api/users'


type StatusFilter = 'pending' | 'active' | 'denied' | 'banned' | undefined

const FILTERS: { label: string; value: StatusFilter }[] = [
  { label: 'Все', value: undefined },
  { label: 'Ожидают', value: 'pending' },
  { label: 'Активные', value: 'active' },
  { label: 'Отклонённые', value: 'denied' },
  { label: 'Заблокированные', value: 'banned' },
]

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  active: 'Активен',
  denied: 'Отклонён',
  banned: 'Заблокирован',
}

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  active: 'bg-green-100 text-green-800',
  denied: 'bg-red-100 text-red-800',
  banned: 'bg-gray-100 text-gray-800',
}

type Action = { label: string; targetStatus: string }

function getActions(status: string): Action[] {
  switch (status) {
    case 'pending':
      return [
        { label: 'Одобрить', targetStatus: 'active' },
        { label: 'Отклонить', targetStatus: 'denied' },
      ]
    case 'active':
      return [{ label: 'Заблокировать', targetStatus: 'banned' }]
    case 'denied':
      return [
        { label: 'Одобрить', targetStatus: 'active' },
        { label: 'Заблокировать', targetStatus: 'banned' },
      ]
    case 'banned':
      return [{ label: 'Одобрить', targetStatus: 'active' }]
    default:
      return []
  }
}

const ACTION_STYLE: Record<string, string> = {
  active: 'bg-green-500 hover:bg-green-600 text-white',
  denied: 'bg-red-500 hover:bg-red-600 text-white',
  banned: 'bg-gray-500 hover:bg-gray-600 text-white',
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

const LIMIT = 20

export default function UsersPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(undefined)
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<UserItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const fetchUsers = useCallback(async (filter: StatusFilter, p: number) => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await listUsers(filter, p, LIMIT)
      setItems(data)
    } catch {
      setError('Не удалось загрузить список пользователей.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUsers(statusFilter, page)
  }, [statusFilter, page, fetchUsers])

  function handleFilterChange(value: StatusFilter) {
    setStatusFilter(value)
    setPage(1)
  }

  async function handleAction(userId: number, targetStatus: string) {
    setActionLoading(userId)
    setError(null)
    try {
      await updateUserStatus(userId, targetStatus)
      await fetchUsers(statusFilter, page)
    } catch {
      setError('Не удалось выполнить действие. Попробуйте снова.')
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Пользователи</h1>

      {/* Filter bar */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={String(f.value)}
            onClick={() => handleFilterChange(f.value)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${
              statusFilter === f.value
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">Username</th>
              <th className="px-4 py-3 text-left">Имя</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3 text-left">Зарегистрирован</th>
              <th className="px-4 py-3 text-right">Запросов</th>
              <th className="px-4 py-3 text-left">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  Загрузка...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  Нет пользователей
                </td>
              </tr>
            ) : (
              items.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-700">
                    {user.username ? `@${user.username}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{user.first_name ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[user.status]}`}
                    >
                      {STATUS_LABELS[user.status] ?? user.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(user.created_at)}</td>
                  <td className="px-4 py-3 text-right text-gray-700">{user.query_count}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2 flex-wrap">
                      {getActions(user.status).map((action) => (
                        <button
                          key={action.targetStatus}
                          disabled={actionLoading === user.id}
                          onClick={() => handleAction(user.id, action.targetStatus)}
                          className={`px-3 py-1 rounded text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${ACTION_STYLE[action.targetStatus] ?? 'bg-blue-500 hover:bg-blue-600 text-white'}`}
                        >
                          {actionLoading === user.id ? '...' : action.label}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Error */}
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {/* Pagination */}
      <div className="flex items-center gap-4 mt-4 text-sm text-gray-600">
        <button
          disabled={page <= 1 || isLoading}
          onClick={() => setPage((p) => p - 1)}
          className="px-3 py-1.5 rounded border border-gray-300 hover:border-blue-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Назад
        </button>
        <span>Страница {page}</span>
        <button
          disabled={items.length < LIMIT || isLoading}
          onClick={() => setPage((p) => p + 1)}
          className="px-3 py-1.5 rounded border border-gray-300 hover:border-blue-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Вперёд
        </button>
      </div>
    </div>
  )
}
