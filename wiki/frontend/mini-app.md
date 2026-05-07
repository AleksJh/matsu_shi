---
type: component
zone: frontend
last_updated: 2026-05-07
source_files:
  - frontend/src/App.tsx
  - frontend/src/hooks/useTelegramAuth.ts
  - frontend/src/hooks/useSSE.ts
  - frontend/src/store/sessionStore.ts
  - frontend/src/store/messageStore.ts
  - frontend/src/api/sessions.ts
related:
  - "[[overview]]"
  - "[[api]]"
  - "[[bot]]"
---

# Telegram Mini App

The Matsu Shi frontend is a high-performance **React** application designed to run inside the Telegram Mini App (TMA) environment. It provides a seamless, chat-like experience for machinery diagnostics.

## Architecture

The application is built with **Vite** and **TypeScript**, utilizing a modular architecture:

- **State Management**: **Zustand** is used for lightweight, persistent state (sessions, messages, auth).
- **Communication**: A mix of **Axios** for RESTful API calls and **Fetch + ReadableStream** for real-time SSE updates.
- **Styling**: Native integration with the Telegram theme via CSS variables.

## Key Features

### 1. Telegram Authentication (`useTelegramAuth`)
The app automatically authenticates users by extracting `initData` from the Telegram WebApp SDK.
- **Theme Sync**: Colors like `--tg-theme-bg-color` are mapped to the application's design system.
- **JWT Handling**: After validating `initData` with the backend, the JWT is stored in `authStore` and injected into all subsequent API requests.

### 2. Streaming Diagnostics (`useSSE`)
To minimize perceived latency, the diagnostic response is delivered via **Server-Sent Events (SSE)**.
- **Optimistic Updates**: User messages are added to the UI instantly.
- **Stream Processing**: The custom `useSSE` hook parses the binary stream from the backend and extracts the structured `QueryResponse`.
- **Title Auto-Refresh**: Since the backend generates chat titles in the background, the frontend polls the session list ~700ms after a response to refresh the sidebar.

### 3. Session Management (`sessionStore`)
- **Isolation**: Messages are grouped by `session_id`, allowing mechanics to maintain multiple diagnostic threads (e.g., one for a hydraulic issue, another for an engine code).
- **History Retrieval**: When switching sessions, the app fetches previous messages from `POST /api/v1/chat/sessions/{id}/history`.

## Design Tokens

The app adheres to Telegram's design guidelines by using the following variables:
- `var(--tg-theme-bg-color)`: Main background.
- `var(--tg-theme-text-color)`: Primary text.
- `var(--tg-theme-button-color)`: Action buttons.
- `var(--tg-theme-hint-color)`: Secondary text and metadata.

## Citation & Visual Rendering
When a diagnostic answer is received, the frontend renders:
- **Markdown**: Formatted technical steps (Reason → Steps → Verification).
- **Citations**: Clickable markers that reveal the document name, section, and page.
- **Diagrams**: High-resolution WebP images from Cloudflare R2, embedded directly in the relevant citation.

> ⚠️ Note: The app requires `WebApp.ready()` to be called after initialization to remove the loading splash screen provided by Telegram.
