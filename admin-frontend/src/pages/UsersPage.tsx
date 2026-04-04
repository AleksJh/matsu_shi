import { useEffect, useState, useCallback } from 'react'
import {
  listUsers,
  updateUserStatus,
  deleteUser,
  deleteUsersBulk,
  sendUserMessage,
  UserItem,
} from '../api/users'

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

// ---------------------------------------------------------------------------
// Confirm delete dialog
// ---------------------------------------------------------------------------

interface ConfirmDeleteDialogProps {
  count: number
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDeleteDialog({ count, onConfirm, onCancel }: ConfirmDeleteDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h2 className="text-lg font-semibold text-gray-800 mb-2">Подтвердите удаление</h2>
        <p className="text-sm text-gray-600 mb-6">
          Будет безвозвратно удалено{' '}
          <span className="font-semibold text-red-600">
            {count} {count === 1 ? 'пользователь' : 'пользователей'}
          </span>{' '}
          вместе со всей историей запросов и сессиями.
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded text-sm border border-gray-300 hover:border-gray-400 text-gray-700 transition-colors"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 rounded text-sm bg-red-600 hover:bg-red-700 text-white font-medium transition-colors"
          >
            Удалить
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Send message modal
// ---------------------------------------------------------------------------

interface SendMessageModalProps {
  user: UserItem
  onSend: (message: string) => Promise<void>
  onClose: () => void
}

function SendMessageModal({ user, onSend, onClose }: SendMessageModalProps) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSend() {
    const trimmed = text.trim()
    if (!trimmed) return
    setSending(true)
    setError(null)
    try {
      await onSend(trimmed)
      onClose()
    } catch {
      setError('Не удалось отправить сообщение. Попробуйте снова.')
    } finally {
      setSending(false)
    }
  }

  const displayName = user.first_name ?? user.username ?? `#${user.id}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Сообщение пользователю</h2>
        <p className="text-sm text-gray-500 mb-4">
          {displayName}{user.username ? ` (@${user.username})` : ''}
        </p>
        <textarea
          className="w-full border border-gray-300 rounded-lg p-3 text-sm resize-none focus:outline-none focus:border-blue-400 transition-colors"
          rows={5}
          placeholder="Введите текст сообщения..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={sending}
          autoFocus
        />
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        <div className="flex gap-3 justify-end mt-4">
          <button
            onClick={onClose}
            disabled={sending}
            className="px-4 py-2 rounded text-sm border border-gray-300 hover:border-gray-400 text-gray-700 transition-colors disabled:opacity-40"
          >
            Отмена
          </button>
          <button
            onClick={handleSend}
            disabled={sending || !text.trim()}
            className="px-4 py-2 rounded text-sm bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {sending ? 'Отправка...' : 'Отправить'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function UsersPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(undefined)
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<UserItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  // Selection state
  const [selected, setSelected] = useState<Set<number>>(new Set())

  // Delete confirm dialog
  const [confirmDelete, setConfirmDelete] = useState<{ ids: number[] } | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  // Message modal
  const [messageTarget, setMessageTarget] = useState<UserItem | null>(null)

  const fetchUsers = useCallback(async (filter: StatusFilter, p: number) => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await listUsers(filter, p, LIMIT)
      setItems(data)
      setSelected(new Set())
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

  // Selection helpers
  const allIds = items.map((u) => u.id)
  const allSelected = allIds.length > 0 && allIds.every((id) => selected.has(id))
  const someSelected = selected.size > 0

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(allIds))
    }
  }

  function toggleOne(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // Delete flow
  function requestDelete(ids: number[]) {
    setConfirmDelete({ ids })
  }

  async function confirmDeleteUsers() {
    if (!confirmDelete) return
    setDeleteLoading(true)
    setError(null)
    try {
      const { ids } = confirmDelete
      if (ids.length === 1) {
        await deleteUser(ids[0])
      } else {
        await deleteUsersBulk(ids)
      }
      setConfirmDelete(null)
      await fetchUsers(statusFilter, page)
    } catch {
      setError('Не удалось удалить пользователей. Попробуйте снова.')
      setConfirmDelete(null)
    } finally {
      setDeleteLoading(false)
    }
  }

  // Send message flow
  async function handleSendMessage(message: string) {
    if (!messageTarget) return
    await sendUserMessage(messageTarget.id, message)
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

      {/* Bulk actions bar */}
      {someSelected && (
        <div className="flex items-center gap-3 mb-3 px-4 py-2 bg-red-50 border border-red-200 rounded-lg">
          <span className="text-sm text-red-700 font-medium">
            Выбрано: {selected.size}
          </span>
          <button
            disabled={deleteLoading}
            onClick={() => requestDelete(Array.from(selected))}
            className="px-3 py-1 rounded text-xs font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Удалить выбранных
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-xs text-gray-500 hover:text-gray-700 transition-colors"
          >
            Снять выделение
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="cursor-pointer"
                  title="Выбрать всех"
                />
              </th>
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
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  Загрузка...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  Нет пользователей
                </td>
              </tr>
            ) : (
              items.map((user) => (
                <tr
                  key={user.id}
                  className={`hover:bg-gray-50 transition-colors ${selected.has(user.id) ? 'bg-red-50' : ''}`}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(user.id)}
                      onChange={() => toggleOne(user.id)}
                      className="cursor-pointer"
                    />
                  </td>
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
                    <div className="flex gap-2 flex-wrap items-center">
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
                      <button
                        onClick={() => setMessageTarget(user)}
                        title="Отправить сообщение в Telegram"
                        className="px-3 py-1 rounded text-xs font-medium bg-blue-500 hover:bg-blue-600 text-white transition-colors"
                      >
                        Написать
                      </button>
                      <button
                        onClick={() => requestDelete([user.id])}
                        title="Удалить пользователя"
                        className="px-3 py-1 rounded text-xs font-medium bg-red-100 hover:bg-red-200 text-red-700 transition-colors"
                      >
                        Удалить
                      </button>
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

      {/* Confirm delete dialog */}
      {confirmDelete && (
        <ConfirmDeleteDialog
          count={confirmDelete.ids.length}
          onConfirm={confirmDeleteUsers}
          onCancel={() => setConfirmDelete(null)}
        />
      )}

      {/* Send message modal */}
      {messageTarget && (
        <SendMessageModal
          user={messageTarget}
          onSend={handleSendMessage}
          onClose={() => setMessageTarget(null)}
        />
      )}
    </div>
  )
}
