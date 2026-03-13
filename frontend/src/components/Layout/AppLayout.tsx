import { useState } from 'react'
import { Sidebar } from '../Sidebar/Sidebar'
import { ChatPanel } from '../Chat/ChatPanel'

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Backdrop — mobile only, visible when drawer is open */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 sm:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={[
          'fixed inset-y-0 left-0 z-40 w-72',
          'transition-transform duration-300 ease-in-out',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
          'sm:static sm:translate-x-0 sm:flex-shrink-0',
        ].join(' ')}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main chat panel */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <ChatPanel onMenuClick={() => setSidebarOpen(true)} />
      </div>
    </div>
  )
}
