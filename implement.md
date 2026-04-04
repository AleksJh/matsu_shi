# Infrastructure Audit & Hardening — Matsu-Shi

## Роль и контекст

Ты — ИИ-ассистент разработчика, который проводит **полный аудит инфраструктуры** production-приложения Matsu-Shi.
У тебя есть SSH-доступ к серверу через алиас `ssh matsu` и полный доступ к репозиторию в текущей рабочей директории.

**Важно:** не предпринимай никаких изменений, не обсудив их с пользователем. Это задача в режиме human-in-the-loop.
Сначала исследуй → составь картину → покажи проблемы → предложи план → получи подтверждение → действуй.

---

## Контекст приложения

**Matsu-Shi** — Telegram-бот и веб-приложение для промышленных механиков. Стек:

- **Backend**: Python / FastAPI / SQLAlchemy async / Alembic / aiogram (Telegram bot)
- **Frontend**: React SPA (Vite + TypeScript + Tailwind) — интерфейс механика (Mini App)
- **Admin**: React SPA (Vite + TypeScript + Tailwind) — панель администратора
- **База данных**: PostgreSQL с расширением pgvector
- **Кэш / очереди**: Redis
- **Реверс-прокси**: Nginx (TLS termination, routing)
- **Деплой**: Docker Compose на одном VPS (Ubuntu), домен `matsushi.xyz`
- **TLS**: Let's Encrypt (certbot)

Репозиторий: `~/matsu_shi` на сервере.

---

## Что уже известно (симптомы, которые привели к этому аудиту)

1. **Расхождение compose vs реальность**: `docker-compose.yml` описывал `admin` как `image: node:20-alpine` с `npm run dev`, тогда как реально на сервере работал контейнер, собранный вручную через `admin-frontend/Dockerfile` (multi-stage build → nginx:alpine). При `docker compose build admin` compose говорил `No services to build`.

2. **Backend запускается с `--reload`** в продакшне (dev-флаг).

3. **Frontend** в compose — такой же паттерн `node:20-alpine` dev-сервер. Неизвестно: есть ли у него свой Dockerfile или он должен работать как dev-сервер.

4. **Исторически что-то ломалось при деплоях** — предположительно из-за того, что compose не описывал реальное состояние.

---

## Цель задачи

Привести всю инфраструктуру к единому, воспроизводимому, production-ready состоянию, где:

- `docker compose up --build -d` на чистом сервере поднимает всё без ручных шагов
- Все сервисы описаны в compose так же, как они реально работают
- Нет dev-артефактов в продакшне (`--reload`, `npm run dev`, exposed dev-порты)
- Секреты — только через `.env` / env vars, никакого хардкода
- Nginx корректно проксирует все сервисы и не требует ручных правок после пересборки

---

## Шаги исследования (выполняй последовательно, обсуждая с пользователем)

### Шаг 1 — Инвентаризация: что реально запущено

Выполни на сервере и покажи полную картину:

```bash
# Все запущенные контейнеры с образами и портами
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"

# Откуда собран каждый образ (Dockerfile или pull)
docker inspect $(docker ps -q) --format '{{.Name}}: image={{.Config.Image}} cmd={{.Config.Cmd}}'

# Точки монтирования (volumes / bind mounts)
docker inspect $(docker ps -q) --format '{{.Name}}: {{json .Mounts}}'
```

### Шаг 2 — Инвентаризация: файлы в репозитории

Проверь наличие Dockerfile в каждом сервисе:

```bash
ls ~/matsu_shi/backend/Dockerfile
ls ~/matsu_shi/frontend/Dockerfile   # есть или нет?
ls ~/matsu_shi/admin-frontend/Dockerfile
cat ~/matsu_shi/docker-compose.yml
```

### Шаг 3 — Frontend: dev или prod?

Это ключевой вопрос. Выясни:

```bash
# Есть ли production build у frontend?
cat ~/matsu_shi/frontend/package.json   # есть ли скрипт "build"?
cat ~/matsu_shi/frontend/vite.config.*  # base path настроен?

# Что сейчас запущено в контейнере frontend
docker inspect matsu_shi-frontend-1 --format '{{json .Config}}'
docker exec matsu_shi-frontend-1 ls /usr/share/nginx/html 2>/dev/null || echo "no nginx html"
```

### Шаг 4 — Nginx: routing и upstream-конфиги

```bash
cat ~/matsu_shi/docker/nginx/nginx.conf
# Проверь: правильно ли указаны порты upstream для каждого сервиса
# admin: порт 80 (nginx в контейнере) или 5174?
# frontend: порт 80 или 5173?
```

### Шаг 5 — Backend: production-ready?

```bash
cat ~/matsu_shi/backend/Dockerfile
# Проверь: есть ли отдельный target для prod без --reload?
grep -r "reload" ~/matsu_shi/docker-compose.yml
grep -r "reload" ~/matsu_shi/backend/Dockerfile
```

### Шаг 6 — Redis и Postgres: персистентность и безопасность

```bash
# Postgres: есть ли password в .env (не захардкожен)?
grep POSTGRES_PASSWORD ~/matsu_shi/.env | head -1 | sed 's/=.*/=***/'

# Redis: есть ли requirepass?
docker exec matsu_shi-redis-1 redis-cli config get requirepass
```

### Шаг 7 — TLS и certbot: автообновление

```bash
# Есть ли cron или systemd timer для certbot renew?
crontab -l 2>/dev/null
systemctl list-timers | grep certbot
ls /etc/letsencrypt/renewal/
```

### Шаг 8 — Порты, открытые наружу

```bash
# Какие порты слушают снаружи (не только nginx)?
ss -tlnp | grep -v '127.0.0.1'
# Идеально: только 80, 443 (и 22 для SSH)
# Плохо: 8000, 5173, 5174 открыты напрямую
```

---

## После исследования: составь отчёт

Оформи находки в виде таблицы:

| Сервис | Текущее состояние | Соответствие best practice | Что нужно исправить |
|--------|-------------------|---------------------------|---------------------|
| backend | ... | ✅ / ⚠️ / ❌ | ... |
| frontend | ... | | |
| admin | ... | | |
| nginx | ... | | |
| postgres | ... | | |
| redis | ... | | |
| TLS/certbot | ... | | |
| Открытые порты | ... | | |

Затем предложи **план изменений** (файлы, которые нужно создать/изменить) и жди подтверждения от пользователя перед тем как что-либо менять.

---

## Критерии завершения

- [ ] `docker compose up --build -d` на сервере поднимает всё без ошибок и ручных шагов
- [ ] Ни один dev-сервер (`npm run dev`, `--reload`) не работает в продакшне
- [ ] Наружу открыты только порты 80, 443, 22
- [ ] Nginx корректно проксирует `/` → frontend, `/admin/` → admin, `/api/` → backend
- [ ] TLS-сертификат обновляется автоматически
- [ ] Все образы описаны в `docker-compose.yml` через `build:` или официальные `image:` без ручных `docker build`
- [ ] `.env` содержит все секреты, ни один секрет не захардкожен в коде или compose

---

## Соглашения проекта

- Все сообщения пользователям (механикам) — на **русском**
- Код, комментарии, переменные, названия файлов — на **английском**
- Никакого raw SQL — только SQLAlchemy ORM (кроме Alembic-миграций)
- Никаких секретов в коде — только env vars через pydantic-settings
