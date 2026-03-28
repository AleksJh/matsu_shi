# Matsu Shi

AI-ассистент механиков Komatsu — Telegram Mini App + Telegram Bot.

## Быстрый старт (dev)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/your-org/matsu-shi.git
cd matsu-shi

# 2. Скопировать пример env и заполнить значения
cp .env.example .env
# Обязательно: BOT_TOKEN, ADMIN_TELEGRAM_ID, DATABASE_URL, REDIS_URL, SECRET_KEY, APP_BASE_URL

# 3. Поднять все сервисы (dev — подхватывает docker-compose.override.yml автоматически)
docker compose up --build

# 4. Применить миграции (первый запуск)
docker compose exec backend alembic upgrade head
```

В режиме **development** (`ENVIRONMENT=development` в `.env`) backend запускается с polling —
бот подключается к Telegram напрямую, без публичного URL.

## Деплой в production (VPS)

```bash
# 1. Скопировать .env.example → .env и заполнить все значения
cp .env.example .env
# Обязательно: BOT_TOKEN, SECRET_KEY, APP_BASE_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
# Установить: ENVIRONMENT=production

# 2. Получить SSL-сертификат через Let's Encrypt
certbot certonly --standalone -d yourdomain.com

# 3. Обновить домен в nginx.prod.conf
# Заменить yourdomain.com на ваш реальный домен в docker/nginx/nginx.prod.conf

# 4. Собрать и запустить все сервисы
docker compose -f docker-compose.prod.yml up -d --build

# ⚠️  Всегда поднимай ВСЕ сервисы через up -d, а не только один (напр. backend).
# Если пересобрать только backend, nginx останется в старой Docker-сети и начнёт
# отдавать 502 Bad Gateway, пока его не перезапустить вручную.

# Миграции Alembic применяются автоматически при старте backend контейнера

# 5. Зарегистрировать Telegram webhook
python backend/scripts/register_webhook.py
```

В режиме **production** бот переключается на webhook (`POST /webhook/telegram`).

Отличия production от dev:

| | Dev | Prod |
|---|---|---|
| Compose файл | `docker-compose.yml` | `docker-compose.prod.yml` |
| Backend | `--reload`, порт 8000 открыт | 2 workers, порт закрыт (nginx) |
| Frontend/Admin | dev-серверы (порты 5173/5174) | статические файлы через nginx |
| БД/Redis | порты открыты наружу | только внутренняя сеть |
| SSL | нет | Let's Encrypt (порты 80/443) |
| Миграции | `alembic upgrade head` вручную | автоматически при старте backend |

## Сервисы

| Сервис | URL |
|--------|-----|
| Backend (FastAPI) | http://localhost:8000 |
| Frontend (Mini App) | http://localhost:5173 |
| Admin Dashboard | http://localhost:5174 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| Nginx | http://localhost:80 |

## Docker: dev vs prod

| | Dev | Prod |
|---|---|---|
| Compose файл | `docker-compose.yml` | `docker-compose.prod.yml` |
| Backend Dockerfile | `Dockerfile` (с `--reload`) | `Dockerfile.prod` (2 workers) |
| Telegram | polling | webhook |
| Hot reload | да | нет |

## Dev Container (VS Code)

Альтернатива `docker compose up` — изолированное окружение с Python 3.13 + Node.js 20
прямо в VS Code:

```
F1 → Dev Containers: Reopen in Container
```

При первом запуске автоматически:
- Собирается образ (`python:3.13-slim` + Node.js 20)
- Поднимаются postgres и redis (в отдельных named volumes, не пересекаются с основным compose)
- Устанавливаются все зависимости (uv + npm)
- Применяются миграции

Затем в терминале контейнера (`/workspace`):

```bash
# Backend
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

# Тесты
cd backend && pytest
```

> Dev Container и `docker compose up` используют **разные** docker volumes —
> можно переключаться между ними без конфликтов.

## Lint и типы (внутри контейнера)

```bash
docker compose exec backend ruff check app/
docker compose exec backend mypy app/
```

## Структура

```
matsu-shi/
├── backend/                    # FastAPI + aiogram + Pydantic AI
│   ├── app/
│   │   ├── bot/                # Telegram bot (dispatcher, handlers)
│   │   ├── core/               # Config, logging
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── api/                # REST endpoints
│   │   ├── services/           # Business logic
│   │   ├── agent/              # Pydantic AI agent
│   │   └── rag/                # RAG pipeline
│   ├── alembic/                # DB migrations
│   ├── tests/
│   └── Dockerfile              # multi-stage: base (prod) / dev
├── frontend/                   # Telegram Mini App (React 18 + Vite)
├── admin-frontend/             # Admin Dashboard (React 18 + Vite)
├── docker/                     # Nginx config
├── .devcontainer/              # VS Code Dev Container config
├── docker-compose.yml          # Dev compose (source mounts, hot-reload)
├── docker-compose.prod.yml     # Production compose (built images, SSL, named volumes)
└── .env.example
```

## Инструмент для загрузки PDF (локально)

Ingest pipeline запускается **локально на машине разработчика** (не в Docker на VPS).
Шаги 1–5 (parse → embed) выполняются локально; шаг 6 (write) пишет напрямую в VPS PostgreSQL
через SSH-туннель и в Cloudflare R2 по HTTPS.

### Подготовка

```bash
# 1. Открыть SSH-туннель к VPS PostgreSQL (держать терминал открытым):
ssh -L 5432:localhost:5432 matsu -N
# Терминал "зависнет" без вывода — это нормально, туннель активен.

# 2. В новом терминале запустить ingest:
cd backend
```

### Основные команды

```bash
# Полный прогон с сохранением артефактов (рекомендуется при первом запуске):
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/matsu_shi" \
PYTHONPATH=/path/to/matsu_shi/backend \
python -m uv run python scripts/ingest.py \
  --path ./scripts/samples/manual.pdf \
  --machine-model "PC300-8" \
  --category "maintenance" \
  --save-artifacts

# Dry-run: парсинг и чанкинг без записи в БД и R2:
DATABASE_URL="..." PYTHONPATH=... \
python -m uv run python scripts/ingest.py \
  --path ./scripts/samples/manual.pdf \
  --machine-model "PC300-8" \
  --dry-run
```

> **Почему `DATABASE_URL` передаётся явно?** pydantic-settings может подхватить `.env` из
> родительского каталога с `DATABASE_URL=postgres:5432` (Docker-адрес). Явный override гарантирует
> что используется `localhost:5432` (SSH-туннель).
>
> **Почему `PYTHONPATH`?** `scripts/ingest.py` импортирует `app.*` — модули backend. Python
> должен знать где их искать.

### Контрольные точки (checkpoint) — Phase 8.7

Артефакты хранятся в `cache/{sha256}/` и позволяют возобновить pipeline с любого шага
без повторного запуска дорогих операций (Docling, Gemini Vision, enrichment, embedding).

```bash
# Остановиться после парсинга, проверить качество markdown:
DATABASE_URL="..." PYTHONPATH=... \
python -m uv run python scripts/ingest.py \
  --path doc.pdf --machine-model "PC300-8" --stop-after parse

# Инспектировать cache/{checksum}/parse.json ...

# Продолжить с шага chunk:
DATABASE_URL="..." PYTHONPATH=... \
python -m uv run python scripts/ingest.py \
  --path doc.pdf --machine-model "PC300-8" --start-from chunk

# Переиндексировать с новой логикой чанкинга (parse+visual уже кешированы):
DATABASE_URL="..." PYTHONPATH=... \
python -m uv run python scripts/ingest.py \
  --path doc.pdf --machine-model "PC300-8" --start-from chunk --rebuild-index
```

| Флаг | Описание |
|------|---------|
| `--stop-after {parse,chunk,enrich,embed}` | Сохранить артефакт и остановиться |
| `--start-from {chunk,enrich,embed,write}` | Загрузить артефакт и продолжить |
| `--save-artifacts` | Сохранять все артефакты при полном прогоне |
| `--artifact-dir DIR` | Директория кеша (default: `./cache`) |

### Примечания по парсингу

- OCR отключён (`do_ocr=False`) — сервисные мануалы Komatsu являются цифровыми PDF с текстовым
  слоем. OCR не нужен и при включении вызывает краш pypdfium2 на сложных страницах (`std::bad_alloc`).
- При первом запуске docling скачивает модели (~40MB) из modelscope.cn — нужен интернет.
