# Текущая реализация

## 1. Текущая фаза и задача

**Фаза:** 9 — Pilot & Tuning
**Задача:** 9.2 — Onboard Test Mechanics
**Статус:** Не начато. Требуется пригласить 3–5 тестовых механиков и пройти полный flow.

---

## 2. Цель

Проверить на реальных пользователях полный путь: `/start` → статус `pending` →
уведомление админа → одобрение → запуск Mini App → выбор модели техники → запрос.
Убедиться, что бот и фронтенд работают без ошибок в production-среде с реальными
Telegram-аккаунтами.

---

## 3. Ссылки на PRD

- **PRD §2** — Auth Flow: pending → active, inline buttons Approve/Deny
- **PRD §3** — US-01 (запрос с ответом), US-02 (история), US-03 (feedback),
  US-06 (возобновить сессию), US-07 (admin approve/deny)
- **PRD §13** — Verification Plan (тест-кейсы, которые будут проверяться в 9.4)

---

## 4. Создаваемые файлы

Нет — задача операционная, без изменений кода.

---

## 5. Изменяемые файлы

Нет — задача операционная, без изменений кода.

---

## 6. Ключевые компоненты (для диагностики, если что-то сломается)

```
backend/app/bot/handlers/mechanic.py   — /start, статус pending/active
backend/app/bot/handlers/admin.py      — inline Approve/Deny/Ban callbacks
backend/app/services/user_service.py   — create_pending, update_status
backend/app/api/auth.py                — POST /api/v1/auth/telegram (initData HMAC)
frontend/src/                          — Mini App (initData → JWT → chat)
```

---

## 7. Implementation Notes

### Шаги онбординга
1. Убедиться, что бот запущен в webhook-режиме на VPS (`ENVIRONMENT=production`).
2. Пригласить 3–5 механиков — дать им username бота в Telegram.
3. Каждый механик отправляет `/start` → бот создаёт запись `users` с `status=pending`.
4. Администратор получает уведомление с именем и username механика + кнопки `✅ Approve` / `❌ Deny`.
5. Нажать `✅ Approve` → механик получает подтверждение + кнопку запуска Mini App.
6. Механик открывает Mini App → выбирает модель → отправляет запрос → проверяет ответ.
7. Проверить `/users` команду — все механики отображаются в правильных статусах.

### Возможные проблемы
- Если кнопка Mini App не открывается: проверить `APP_BASE_URL` в `.env`.
- Если initData HMAC отклоняется: проверить `BOT_TOKEN` совпадает на боте и сервере.
- Если бот не отвечает: проверить `docker compose logs backend` на VPS.

---

## 8. Точки интеграции

```
Telegram (мобильный клиент)
  └─► Bot: /start → users.status = pending
  └─► Admin notification → inline Approve callback → users.status = active
  └─► Mini App WebApp button → frontend (React)
        └─► POST /api/v1/auth/telegram (HMAC validation → JWT)
              └─► POST /api/v1/chat/sessions (machine_model)
                    └─► POST /api/v1/chat/query (SSE)
```

---

## 9. Done When

### Критерии готовности
- [ ] Минимум 3 реальных Telegram-аккаунта прошли `/start` → `pending`.
- [ ] Администратор успешно одобрил всех через inline-кнопки.
- [ ] Каждый механик открыл Mini App и выбрал модель техники.
- [ ] Каждый механик отправил хотя бы 1 запрос и получил ответ с цитатами.
- [ ] Команда `/users` показывает всех механиков в статусе `active`.
- [ ] В Langfuse видны трейсы для запросов механиков.

### Шаги верификации
1. Проверить `docker compose logs backend --tail=50` — нет ошибок при `/start`.
2. Проверить admin web dashboard → Users page — механики отображаются.
3. Проверить admin web dashboard → Queries page — запросы механиков видны.
4. Выполнить команду `/stats` в боте — статистика корректная.
