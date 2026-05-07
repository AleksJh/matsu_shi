---
type: component
zone: backend
last_updated: 2026-05-07
source_files:
  - backend/app/bot/dispatcher.py
  - backend/app/bot/handlers/mechanic.py
  - backend/app/bot/handlers/admin.py
  - backend/app/services/user_service.py
related:
  - "[[overview]]"
  - "[[api]]"
  - "[[database]]"
---

# Telegram Bot

The Matsu Shi Telegram Bot (built with **aiogram**) serves as the primary entry point for mechanics and a management interface for administrators. It handles user registration, access control, and system notifications.

## User Registration Flow

New users must complete a 5-step registration process via a Finite State Machine (FSM):

1.  **`/start`**: Initiates the process. If the user is unknown, they are prompted for their **FIO** (Full Name).
2.  **Country Selection**: An inline keyboard provides a list of countries (e.g., Russia, Kazakhstan, etc.).
3.  **City**: Manual text input for the user's city.
4.  **Email**: Validated for basic format (`@` and `.` presence).
5.  **Phone**: Validated to ensure it contains at least 7 digits.

Upon completion, the user is saved with a `pending` status, and a notification is sent to the **Admin Telegram ID**.

## Admin Interface (Telegram)

Administrators can manage the system directly through the bot using commands and inline buttons.

### Command Reference
- **`/users`**: Displays a paginated list of users grouped by status (Pending, Active, Denied, Banned). Each entry includes inline buttons for status changes.
- **`/stats`**: Provides a real-time summary of:
  - User counts by status.
  - Total queries processed today.
  - Average retrieval score over the last 7 days.
- **`/notify <text>`**: Broadcasts a message to all users with `active` status.

### Callback Actions
- **`approve:<id>`**: Sets status to `active`, records the approval time, and notifies the mechanic with a "Open Matsu Shi" button.
- **`deny:<id>`**: Sets status to `denied` and notifies the mechanic.
- **`ban:<id>`**: Sets status to `banned` and revokes access to the [[api]].

## Connection Modes

The bot's connection mode is determined by the `ENVIRONMENT` variable in `.env`:

| Mode | Connection Method | Logic |
| :--- | :--- | :--- |
| **Development** | **Long Polling** | Started as an async task within the FastAPI lifespan. |
| **Production** | **Webhooks** | Configured via `bot.set_webhook` to point to `/webhook/telegram`. |

## Backend Integration

The bot does not directly query the database; instead, it uses the **Service Layer** (`app/services/`) to maintain a clean separation of concerns:
- **`UserService`**: Used for all user-related state changes and lookups.
- **`AsyncSessionLocal`**: Injected into handlers to provide database access.

> ⚠️ Known issue: If a user changes their Telegram username after registration, the bot's stored `username` will become stale until they run `/start` again.
