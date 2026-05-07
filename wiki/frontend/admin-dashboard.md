---
type: component
zone: frontend
last_updated: 2026-05-07
source_files:
  - admin-frontend/src/App.tsx
  - admin-frontend/src/pages/UsersPage.tsx
  - admin-frontend/src/pages/LoginPage.tsx
  - admin-frontend/src/pages/QueriesPage.tsx
  - admin-frontend/src/pages/SystemPage.tsx
  - admin-frontend/src/components/PrivateRoute.tsx
  - admin-frontend/src/api/users.ts
related:
  - "[[overview]]"
  - "[[api]]"
  - "[[bot]]"
---

# Admin Dashboard

The Admin Dashboard is a standalone **React** application used by system operators to manage users, monitor RAG performance, and broadcast maintenance notifications. It is accessible at `/admin/`.

## Core Modules

### 1. User Management (`UsersPage`)
This is the most critical module for system security and access control.
- **Approval Queue**: Operators review pending registrations (FIO, phone, email) and approve or deny access.
- **Direct Interaction**: Admins can send direct Telegram messages to any registered mechanic via the bot's API.
- **Access Control**: Users can be "Banned" (revoking JWT validity) or "Deleted" (cascading removal of all their history).

### 2. Query Monitoring (`QueriesPage`)
Provides a real-time log of all mechanic interactions.
- **Performance Audit**: Tracks `retrieval_score` and `latency_ms` for every query.
- **Detail View**: Allows operators to see the exact context chunks provided to the LLM and the final generated response.
- **Feedback Loop**: Visualizes user ratings (👍/👎) to identify documents that may need better chunking or enrichment.

### 3. Knowledge Base Audit (`DocumentsPage`)
Lists all manuals currently indexed in the [[database]].
- Shows status (indexed/processing/error).
- Displays chunk counts and machine model mapping for each PDF.

### 4. System Statistics (`SystemPage`)
Provides aggregated metrics for system health:
- **Daily Volume**: Total queries processed in the last 24 hours.
- **RAG Quality**: Rolling 7-day average of the retrieval confidence score.
- **Model Breakdown**: Percentage of queries handled by the "Lite" model vs the "Advanced" model.
- **Global Broadcast**: A tool to send an immediate notification to all `active` mechanics (e.g., "New manual for PC300-8 added").

## Security

- **JWT Authentication**: The dashboard uses a separate `role=admin` token.
- **Private Routes**: React routes are protected by the `PrivateRoute` component and an `authStore` check; unauthenticated users are redirected to the `LoginPage`.
- **Axios Interceptors**: Automatically attach the admin JWT to the `Authorization` header for all requests to the [[api]].

## Deployment

The dashboard is built into a static bundle using **Vite** and served by **Nginx** in production. The Nginx configuration ensures that all paths starting with `/admin` are routed to the `index.html` of the dashboard to support client-side routing.

> ⚠️ Security Note: In production, the admin login should be protected by an IP whitelist at the Nginx level in addition to password authentication.
