import { useEffect, useState } from 'react'
import { listDocuments, DocumentItem } from '../api/documents'

const STATUS_BADGE: Record<string, string> = {
  indexed: 'bg-green-100 text-green-800',
  processing: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
}

const STATUS_LABELS: Record<string, string> = {
  indexed: 'Проиндексирован',
  processing: 'Обрабатывается',
  error: 'Ошибка',
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

export default function DocumentsPage() {
  const [items, setItems] = useState<DocumentItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setIsLoading(true)
    setError(null)
    listDocuments()
      .then(setItems)
      .catch(() => setError('Не удалось загрузить список документов.'))
      .finally(() => setIsLoading(false))
  }, [])

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Документы</h1>

      <div className="bg-white rounded-xl shadow overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">Название</th>
              <th className="px-4 py-3 text-left">Модель</th>
              <th className="px-4 py-3 text-left">Категория</th>
              <th className="px-4 py-3 text-right">Страниц</th>
              <th className="px-4 py-3 text-right">Чанков</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3 text-left">Проиндексирован</th>
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
                  Нет документов
                </td>
              </tr>
            ) : (
              items.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-800 font-medium">{doc.display_name}</td>
                  <td className="px-4 py-3 text-gray-600">{doc.machine_model}</td>
                  <td className="px-4 py-3 text-gray-500">{doc.category ?? '—'}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{doc.page_count ?? '—'}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{doc.chunk_count ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        STATUS_BADGE[doc.status ?? ''] ?? 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {STATUS_LABELS[doc.status ?? ''] ?? doc.status ?? '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(doc.indexed_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </div>
  )
}
