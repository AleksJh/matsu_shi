import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import UsersPage from './pages/UsersPage'
import DocumentsPage from './pages/DocumentsPage'
import QueriesPage from './pages/QueriesPage'
import SystemPage from './pages/SystemPage'
import PrivateRoute from './components/PrivateRoute'
import { useAuthStore } from './store/authStore'

const NAV_LINKS = [
  { to: '/users', label: 'Пользователи' },
  { to: '/documents', label: 'Документы' },
  { to: '/queries', label: 'Запросы' },
  { to: '/stats', label: 'Статистика' },
]

function AppLayout() {
  const { clearAuth } = useAuthStore()
  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      <nav className="bg-white shadow-sm px-6 py-3 flex items-center gap-6">
        <span className="font-bold text-gray-800 mr-4">Matsu Shi Admin</span>
        {NAV_LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }: { isActive: boolean }) =>
              `text-sm font-medium transition-colors ${
                isActive ? 'text-blue-600' : 'text-gray-500 hover:text-gray-800'
              }`
            }
          >
            {link.label}
          </NavLink>
        ))}
        <button
          onClick={clearAuth}
          className="ml-auto bg-red-500 text-white rounded px-3 py-1.5 text-sm hover:bg-red-600 transition-colors"
        >
          Выйти
        </button>
      </nav>
      <main className="flex-1">
        <Routes>
          <Route path="/users" element={<UsersPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/queries" element={<QueriesPage />} />
          <Route path="/stats" element={<SystemPage />} />
          <Route path="/" element={<Navigate to="/users" replace />} />
          <Route path="*" element={<Navigate to="/users" replace />} />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter basename="/admin">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<PrivateRoute />}>
          <Route path="/*" element={<AppLayout />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
