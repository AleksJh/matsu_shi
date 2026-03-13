# Текущая фаза и задача

**Фаза:** 9 — Pilot & Tuning
**Задача:** 9.1 — Ingest Real Documents (первая задача фазы)
**Статус:** ⏳ не начата

---

## Цель

Запустить `ingest.py` на реальных PDF-мануалах Komatsu, убедиться, что документы появляются
в таблице `documents` и `chunks`, изображения — в Cloudflare R2, и что данные доступны
для поиска через API. Это разблокирует задачи 9.2–9.5 (онбординг механиков, валидация
порогов, верификационный план).

---

## PRD References

- **§4.1** — pipeline ingestion: Docling → Gemini visual → chunking → enrichment → embed → write
- **§4.2** — 4 правила чанкинга
- **§13** — 18 тест-кейсов верификационного плана (выполнять в задаче 9.4)
- **§8** — NFR: 0% hallucination, 100% citation, P95 < 8s

---

## Files to Create

Нет новых файлов — Phase 9 является операционной фазой (данные + ручная верификация).

---

## Files to Modify

Нет изменений кода. Все действия выполняются вручную или через существующие скрипты.

---

## Key Imports & Dependencies

- `backend/scripts/ingest.py` — главный CLI для инджеста
- `backend/scripts/create_admin.py` — создание admin_users записи (нужен для dashboard)
- `backend/scripts/register_webhook.py` — регистрация Telegram webhook на VPS
- `backend/app/rag/` — dense_retriever, sparse_retriever, retriever (используются при запросах)
- `backend/app/agent/` — classifier, router, responder (используются при запросах)

---

## Implementation Notes

### Task 9.1 — Ingest Real Documents

```bash
# Запускать локально (НЕ в Docker), с production .env
cd backend
python scripts/ingest.py --path ./scripts/samples/<manual>.pdf \
  --machine-model "PC300-8" \
  --category "hydraulics"
```

- Проверить появление строки в таблице `documents` (admin dashboard → Documents)
- Проверить `chunk_count` соответствует числу строк в таблице `chunks`
- Проверить WebP файлы в R2 bucket (`matsu-shi-images`)
- Spot-check 5–10 запросов в Langfuse: retrieval_score, model_used, citations

### Task 9.2 — Onboard Test Mechanics

1. Пригласить 3–5 механиков в Telegram
2. Провести через full flow: `/start` → pending → approve → Mini App
3. Убедиться, что кнопка Mini App ведёт на production URL
4. Проверить, что `WebAppInfo(url=settings.APP_BASE_URL)` корректен

### Task 9.3 — Threshold Validation

Проверить Langfuse после первых 50 запросов:
- Если retrieval_score кластеризуется иначе ожидаемого → скорректировать в `.env`:
  - `RETRIEVAL_SCORE_THRESHOLD` (default 0.65)
  - `RETRIEVAL_NO_ANSWER_THRESHOLD` (default 0.30)
- Убедиться: ни один ответ не возвращается без citations

### Task 9.4 — Run Verification Plan (PRD §13)

18 тест-кейсов из PRD §13:

| # | Тест | Что проверить |
|---|------|--------------|
| 1 | Auth flow | `/start` → approve → Mini App |
| 2 | Denied access | status denied → rejection |
| 3 | Machine model selector | selection locks for session |
| 4 | RAG accuracy | 10 error codes → correct doc+page |
| 5 | Hallucination | absent topic → "Информация не найдена" |
| 6 | Visual chunks | figure query → visual_url populated |
| 7 | Domain filter | PC300 query → no PC200 data |
| 8 | LLM routing | score < 0.65 → model_used = "advanced" |
| 9 | Step-by-Step | complex query → session resumable |
| 10 | Citation presence | all responses have [doc\|section\|page] |
| 11 | Rate limiting | 16th request → HTTP 429 |
| 12 | Admin ban | ban user → next query → HTTP 403 |
| 13 | Feedback | 👎 → visible in admin Queries |
| 14 | Ingestion CLI | new PDF → admin Documents page |
| 15 | Docker restart | down && up → data preserved |
| 16 | Telegram initData | tampered → HTTP 401 |
| 17 | Langfuse | trace visible after query |

### Task 9.5 — Monitoring Checklist

- [ ] Langfuse dashboard: все трейсы видны с retrieval_score
- [ ] `docker compose logs backend`: структурированные логи читаемы
- [ ] Admin `/stats` в Telegram: точные данные

---

## Integration Points

- **Зависит от:** Phase 8 ✅ (VPS + SSL + webhook + CI)
- **Использует:** все фазы 0–8 (полный стек)
- **Критические блокеры перед 9.1:**
  1. VPS запущен (`docker-compose.prod.yml up`)
  2. Telegram webhook зарегистрирован (`register_webhook.py`)
  3. Admin user создан (`create_admin.py`)
  4. `.env` на VPS заполнен (все 13 сервисов из PRD §10)

---

## Done When

Phase 9 считается завершённой когда:
- [ ] Все 18 тест-кейсов PRD §13 выполнены и задокументированы как PASS
- [ ] Минимум 50 реальных запросов обработано без hallucinations или отсутствия citations
- [ ] Langfuse dashboard показывает трейсы для всех запросов
- [ ] 3–5 реальных механиков прошли полный onboarding flow
