# Текущая фаза и задача

**Фаза:** 9 — Pilot & Tuning
**Задача:** 9.1 — Ingest Real Documents
**Статус:** 🔄 в процессе

---

## Цель

Запустить `ingest.py` на реальных PDF-мануалах Komatsu и убедиться, что:
- документы появляются в таблицах `documents` и `chunks` (видны в admin dashboard → Documents)
- WebP-изображения загружены в Cloudflare R2 bucket (`matsu-shi-images`)
- данные доступны для RAG-поиска через API

Это разблокирует задачи 9.2–9.5: онбординг механиков, валидацию порогов, верификационный план.

---

## PRD References

- **§4.1** — шаги pipeline: Docling → Gemini Vision → chunking → enrichment → embedding → remote write
- **§4.2** — 4 правила чанкинга (header-aware, table isolation, visual-link metadata, 10% overlap)
- **§4.3** — обязательные поля метаданных chunk (все поля ChunkData должны быть заполнены)
- **§9.3** — схемы таблиц `documents` и `chunks` (поля, типы, HNSW-индекс, machine_model индекс)
- **§10** — список всех 13 env vars (DATABASE_URL, R2_*, GEMINI_API_KEY, OPENROUTER_API_KEY, EMBED_MODEL, EMBED_DIM, LANGFUSE_*)
- **§13** — 18 тест-кейсов верификационного плана (выполнять в задаче 9.4)

---

## Files to Create

Нет. Phase 9 — операционная фаза. Весь код уже написан в фазах 0–8.7.

---

## Files to Modify

- `backend/scripts/ingest.py` — отключён OCR (`do_ocr=False`) для предотвращения краша pypdfium2
  на сложных страницах цифровых PDF. Добавлены импорты `PdfPipelineOptions`, `PdfFormatOption`, `InputFormat`.
- `docker-compose.prod.yml` — добавлен port mapping `127.0.0.1:5432:5432` для сервиса `postgres`
  (необходим для SSH-туннеля при локальном запуске ingest).

При необходимости также корректируется:
- `.env` на VPS (пороги `RETRIEVAL_SCORE_THRESHOLD`, `RETRIEVAL_NO_ANSWER_THRESHOLD` — задача 9.3)

---

## Key Imports & Dependencies

- `backend/scripts/ingest.py` — главный CLI для инджеста (все 6 шагов + checkpoint)
- `backend/app/rag/embedder.py` — `embed_text()` вызывается на шаге 5 (embed)
- `backend/app/core/config.py` — `settings` (DATABASE_URL, R2_BUCKET, GEMINI_API_KEY, OPENROUTER_API_KEY, EMBED_MODEL, EMBED_DIM)
- `backend/app/core/database.py` — `AsyncSessionLocal` (используется в step_write)
- `backend/app/models/document.py` — ORM-модель `Document` (upsert по checksum)
- `backend/app/models/chunk.py` — ORM-модель `Chunk` (batch insert с векторами)

---

## Implementation Notes

### Критические блокеры перед 9.1

Перед запуском убедиться, что:
1. VPS запущен: `docker compose -f docker-compose.prod.yml up -d`
2. Telegram webhook зарегистрирован: `python backend/scripts/register_webhook.py`
3. Admin user создан: `python backend/scripts/create_admin.py --username admin --password <pass>`
4. `.env` на VPS полностью заполнен (все 13 сервисов из PRD §10)

### Запуск ingest.py (локально, не в Docker)

Требования перед запуском:
1. SSH-туннель открыт: `ssh -L 5432:localhost:5432 matsu -N` (терминал должен "висеть")
2. CWD = `backend/`

```bash
cd backend

# Первый прогон — сохранить все артефакты для возможного возобновления:
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/matsu_shi" \
PYTHONPATH=/path/to/matsu_shi/backend \
python -m uv run python scripts/ingest.py \
  --path ./scripts/samples/<manual>.pdf \
  --machine-model "PC300-8" \
  --category "maintenance" \
  --save-artifacts

# Если нужно перечитать только chunking (parse+visual уже в cache):
DATABASE_URL="..." PYTHONPATH=... \
python -m uv run python scripts/ingest.py \
  --path ./scripts/samples/<manual>.pdf \
  --machine-model "PC300-8" \
  --start-from chunk \
  --rebuild-index

# Dry-run для проверки без записи в БД и R2:
DATABASE_URL="..." PYTHONPATH=... \
python -m uv run python scripts/ingest.py \
  --path ./scripts/samples/<manual>.pdf \
  --machine-model "PC300-8" \
  --dry-run
```

### Checkpoint-флаги (Phase 8.7)

| Флаг | Описание |
|------|---------|
| `--stop-after {parse,chunk,enrich,embed}` | Сохранить артефакт и остановиться |
| `--start-from {chunk,enrich,embed,write}` | Загрузить артефакт и продолжить |
| `--save-artifacts` | Сохранять все артефакты при полном прогоне |
| `--artifact-dir DIR` | Директория кеша (default: `./cache`) |

Артефакты: `cache/{sha256_checksum}/{parse,visual,chunks,enriched,embedded}.json`

### Проверка результатов

После успешного прогона:
```bash
# Проверить документ в БД:
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT display_name, chunk_count, status FROM documents ORDER BY indexed_at DESC LIMIT 5;"

# Проверить количество chunks:
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT COUNT(*) FROM chunks WHERE machine_model = 'PC300-8';"
```

- Открыть admin dashboard → Documents — убедиться, что документ виден с правильным `chunk_count` и статусом `indexed`
- Проверить WebP в R2 bucket: `{machine_model}/{doc_name}/page_{n}.webp`
- Spot-check 5–10 запросов в Langfuse: `retrieval_score`, `model_used`, наличие citations

---

## Integration Points

- **Зависит от:** Phase 8 ✅ (VPS + SSL + webhook + CI) и Phase 8.7 ✅ (ingest.py с checkpoint)
- **Использует:** весь стек фаз 0–8
- **Разблокирует:** Phase 9.2 (онбординг механиков), 9.3 (валидация порогов), 9.4 (верификационный план), 9.5 (мониторинг)

---

## Done When

**Задача 9.1 считается завершённой, когда:**
- [ ] Как минимум один реальный PDF-мануал Komatsu проиндексирован без ошибок
- [ ] Документ виден в admin dashboard → Documents с правильным `chunk_count` и `status = indexed`
- [ ] WebP-файлы присутствуют в R2 bucket для страниц с диаграммами
- [ ] 5–10 тестовых запросов возвращают chunks с `retrieval_score > 0.0` (данные searchable)
- [ ] Langfuse показывает traces для тестовых запросов с полями `retrieval_score`, `model_used`

**Phase 9 полностью завершена, когда:**
- [ ] Все 18 тест-кейсов PRD §13 задокументированы как PASS (задача 9.4)
- [ ] 50+ реальных запросов обработано без hallucinations или отсутствия citations
- [ ] 3–5 реальных механиков прошли полный onboarding flow (задача 9.2)
- [ ] Langfuse и Loguru мониторинг подтверждён (задача 9.5)
