# Phase 9 — Pilot & Tuning

## 1. Текущая фаза и задача

**Фаза:** Phase 9 — Pilot & Tuning  
**Активные подзадачи:** 9.2 (Onboard) → 9.3 (Threshold Validation) → 9.4 (Verification) → 9.5 (Monitoring)

**Что уже сделано в Phase 9:**
- ✅ 9.1 — реальные документы загружены через `ingest.py`
- ✅ 9.6 — Gemini 503 retry реализован в `classifier.py`, `responder.py`, `embedder.py`
- ✅ Дополнительно (вне roadmap): регистрационная анкета FSM, user в auth response, кнопка при апруве

**Текущие продакшен-данные:**
- 4 активных пользователя: Alex (36 запросов), Andranik (0), Armen (6), Тигран (0)
- Средний retrieval score: **0.578** (ниже порога 0.65 → большинство через advanced model)
- No-answer: **28.5%** (12 из 42 запросов)

---

## 2. Цель

Провести пилот с реальными механиками, собрать данные о качестве ответов, настроить
пороги retrieval, пройти все тест-кейсы из PRD §13, убедиться что мониторинг работает.

---

## 3. Ссылки на PRD

- **PRD §13** — полный Verification Plan (16 тест-кейсов)
- **PRD §5.3** — пороги retrieval: `RETRIEVAL_SCORE_THRESHOLD=0.65`, `RETRIEVAL_NO_ANSWER_THRESHOLD=0.30`
- **PRD §8** — Non-Functional Requirements (latency, hallucination, citation)

---

## 4. Файлы для создания

Нет (Phase 9 — операциональная, не кодовая).

---

## 5. Файлы для изменения (при необходимости)

| Файл | Условие |
|------|---------|
| `.env` (на ВПС) | Если нужно изменить `RETRIEVAL_SCORE_THRESHOLD` или `RETRIEVAL_NO_ANSWER_THRESHOLD` |

---

## 6. Ключевые зависимости

```
backend/app/rag/retriever.py       — логика порогов (score < 0.30 → no_answer, < 0.65 → advanced)
backend/app/agent/router.py        — модельный роутинг по score и query_class
backend/app/core/config.py         — Settings: RETRIEVAL_SCORE_THRESHOLD, RETRIEVAL_NO_ANSWER_THRESHOLD
```

---

## 7. Implementation Notes

### 9.2 — Онбординг механиков

Теперь есть регистрационная анкета (FSM). Новый пользователь:
1. `/start` → заполняет ФИО, страну, город, email, телефон
2. Ты одобряешь → он получает кнопку Mini App прямо в сообщении об апруве
3. Тест: проверь что Andranik теперь может зарегистрироваться через новый флоу

Существующие пользователи не затронуты — у них нет `full_name` и т.д., это нормально.

### 9.3 — Валидация порогов

Текущая проблема: avg score = **0.578**, no-answer = **28.5%**

Это может означать:
- Запросы на темы не из загруженных документов → нормально
- Документов мало или не те модели техники → нужно больше мануалов
- Пороги слишком жёсткие → попробовать снизить `RETRIEVAL_NO_ANSWER_THRESHOLD` с 0.30 до 0.25

Как смотреть: Langfuse dashboard → фильтр по `no_answer=true` → читаем query_text.

### 9.4 — Verification Plan (PRD §13)

Пройти 16 тест-кейсов вручную:

| # | Тест | Как проверить |
|---|------|--------------|
| 1 | Auth flow | Новый пользователь → /start → анкета → апрув → Mini App |
| 2 | Denied access | status=denied → /start → отказ, нет Mini App |
| 3 | Machine model selector | Новая сессия → выбор модели → лок |
| 4 | RAG accuracy | 10 известных кодов ошибок → правильные цитаты |
| 5 | Hallucination | Запрос вне мануалов → "Информация не найдена..." |
| 6 | Visual chunks | Запрос о схеме → `visual_url` → изображение в Mini App |
| 7 | Domain filter | PC300 запрос → только PC300 чанки |
| 8 | LLM routing | Score < 0.65 → `model_used = "advanced"` в БД |
| 9 | Step-by-Step | Сложный запрос → сессия сохраняется → возобновляется |
| 10 | Citation presence | Все ответы содержат `[doc | section | page]` |
| 11 | Rate limiting | 16 запросов за 60с → 16-й возвращает HTTP 429 |
| 12 | Admin ban | Бан active пользователя → следующий запрос HTTP 403 |
| 13 | Feedback | 👎 → отображается в Queries в admin dashboard |
| 14 | Ingestion CLI | `ingest.py` на новый PDF → документ в admin Documents |
| 15 | Docker restart | `docker compose down && up` → все данные сохранены |
| 16 | Telegram initData | Изменённый initData → HTTP 401 |

### 9.5 — Monitoring Checklist

- [ ] Langfuse dashboard: трейсы видны после каждого запроса
- [ ] `docker compose logs backend` — структурированные логи читаемы
- [ ] `/stats` в боте возвращает корректные числа
- [ ] Admin dashboard `/admin/` → System page → графики обновляются

---

## 8. Интеграционные точки

```
Telegram Bot (mechanic.py FSM)
  └─► users table (full_name, country, city, email, phone)
  └─► Admin notification (полные данные анкеты)

admin.py cb_approve
  └─► Bot API: send ReplyKeyboardMarkup с WebAppInfo (прямая кнопка)

auth.py /auth/telegram
  └─► TokenResponse: { access_token, user: UserOut }
  └─► authStore.user (теперь не null)

retriever.py score thresholds
  └─► config.py RETRIEVAL_SCORE_THRESHOLD (0.65)
  └─► config.py RETRIEVAL_NO_ANSWER_THRESHOLD (0.30)
```

---

## 9. Done When

Phase 9 завершена когда:
- [ ] Не менее 3 реальных механиков активно используют систему
- [ ] Все 16 тест-кейсов PRD §13 пройдены (pass/fail задокументированы)
- [ ] Пройдено ≥50 реальных запросов без галлюцинаций и без пропущенных цитат
- [ ] Langfuse показывает трейсы для всех запросов
- [ ] No-answer rate понятен (либо принят, либо устранён настройкой порогов)

**Следующий шаг:** Пригласить Andranik заново зарегистрироваться через новый FSM флоу
и убедиться что он может отправить первый запрос.
