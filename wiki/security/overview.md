---
type: architecture
zone: security
last_updated: 2026-05-07
source_files:
  - backend/app/core/security.py
  - backend/app/api/auth.py
  - backend/app/api/chat.py
related:
  - "[[overview]]"
  - "[[api]]"
  - "[[bot]]"
---

# Security & Compliance

Matsu Shi is designed with a "Security-First" approach, leveraging Telegram's native authentication and strict API-level controls to protect both the proprietary knowledge base and user diagnostic data.

## 1. Multi-Stage Authentication

Access to the system is divided into two distinct roles, each with its own verification flow:

### Mechanic Access (Telegram Mini App)
1.  **HMAC Validation**: When the Mini App opens, it sends `initData` to the backend. The backend validates this string using the Telegram Bot Token and the HMAC-SHA256 algorithm.
2.  **Status Check**: The backend verifies that the user exists in the [[database]] and has a status of `active`.
3.  **JWT Issuance**: A JSON Web Token (JWT) is issued for subsequent requests.
    - **Algorithm**: HS256.
    - **Lifetime**: 24 hours (`JWT_EXPIRE_MINUTES = 1440`).

### Operator Access (Admin Dashboard)
- **Credentials**: Standard username/password login.
- **Hashing**: Passwords are stored using the **Bcrypt** algorithm.
- **JWT Issuance**: A separate token with the `role: admin` claim is issued, providing access to management endpoints.

## 2. API Protection

### Rate Limiting
To protect against automated scraping and control LLM costs, the system enforces a strict rate limit:
- **Threshold**: 15 diagnostic queries per minute per user.
- **Mechanism**: Redis-based `INCR` counter with a 60-second sliding window.
- **Status Code**: Returns `429 Too Many Requests` when exceeded.

### Session Isolation
All diagnostic data is isolated at the database level.
- **Ownership Check**: Every API call for session history or new queries verifies that the `session_id` belongs to the authenticated `user_id`.
- **Query Masking**: Admin views for query logs show truncated data unless the specific query detail is requested for auditing.

## 3. Infrastructure Security

- **Network Isolation**: In production, the PostgreSQL and Redis containers are only accessible via the internal Docker bridge network.
- **SSH Tunneling**: Remote indexing (ingestion) and manual DB maintenance are only possible through an encrypted SSH tunnel (`localhost:5432` → `VPS:5432`).
- **SSL Termination**: Nginx enforces HTTPS (TLS 1.2+) for all traffic, including the Telegram webhook.

## 4. RAG Compliance & Grounding

A core "security" feature of the RAG pipeline is the **Hallucination Guard**:
- If the retrieval score for a query is below **0.30**, the system refuses to answer.
- This prevents the LLM from generating "best guess" repairs that could lead to equipment damage or safety hazards.

## 5. PII Management

The system collects minimal Personally Identifiable Information (PII) during the [[bot]] registration flow:
- Telegram ID, Username, First Name.
- Optional: Full Name, Email, Phone.
This data is used solely for the mechanic approval process and is not shared with third-party LLM providers (only the diagnostic query is sent to OpenRouter).

> ⚠️ Security Rule: The `SECRET_KEY` in the `.env` file must be a cryptographically strong string of at least 32 characters and must never be shared or committed to the repository.
