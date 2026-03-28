WIKI: Как работает ingest pipeline (для понимания)
Что происходит когда ты запускаешь ingest.py
Pipeline состоит из 6 шагов, которые выполняются последовательно:

PDF файл
  │
  ▼
[1] parse (Docling)
    PDF → структурированный Markdown
    Распознаёт: текст, таблицы, позиции изображений
    Артефакт: cache/{sha256}/parse.json (~1.4 MB)
    Время: ~1-3 мин на 100 стр.
  │
  ▼
[2] visual (Gemini LLM_ADVANCED_MODEL + Vision)  ←── параллельно с [3]
    Каждая страница → WebP → загружается в Cloudflare R2
    Gemini смотрит на страницу и пишет одну строку описания
    Модель: LLM_ADVANCED_MODEL — здесь нужна multimodal (vision) способность.
    Артефакт: cache/{sha256}/visual.json (~316 KB)
    Время: зависит от количества страниц (долго!)
  │
[3] chunk (параллельно с [2])
    Markdown → список чанков по правилам PRD:
    - Разбивка по заголовкам (header-aware)
    - Таблицы изолированы в отдельные чанки
    - 10% overlap между чанками
    Артефакт: cache/{sha256}/chunks.json (~1.5 MB)
  │
  ▼
[4] enrich (Gemini LLM_LITE_MODEL)
    3 задачи:
    a) Rule 3: привязывает R2-URL изображений к text-чанкам где упоминаются Рис./Схема N
    b) Создаёт visual_caption чанки из visual.json (по одному на каждое изображение)
       → чанков становится больше: chunks.json N + visual_count = итого
    c) Gemini prepend: для каждого text/visual_caption пишет одно предложение-резюме
       и вставляет [Контекст: ...] в начало. Для table — [Таблица: ...].
       Цель: улучшить векторное представление чанка при embedding.
    Модель: LLM_LITE_MODEL (gemini-2.5-flash-lite) — быстрая, стабильная, vision не нужна.
    ⚠️ Не менять на LLM_ADVANCED_MODEL: preview-модели перегружены, дают 503 каждые ~5 чанков,
       скорость падает в 15x (30 сек/чанк вместо 2 сек/чанк).
    Retry: 20 попыток / 2s для Gemini 503
    Partial checkpoint: enriched_partial.json сохраняется каждые 10 чанков
    → при падении: --start-from enrich подхватит с места остановки
    Артефакт: cache/{sha256}/enriched.json (~2.5 MB)
    Время: ~20-40 мин на 900 чанков (зависит от LLM_LITE_MODEL latency)
  │
  ▼
[5] embed (OpenRouter)
    Каждый чанк → вектор 1024 числа через Qwen3-Embedding
    Артефакт: cache/{sha256}/embedded.json (~31 MB!)
    Время: ~5-15 мин зависит от числа чанков
  │
  ▼
[6] write (требует SSH-туннель + R2)
    embedded.json → INSERT в PostgreSQL на VPS
    visual.json → WebP уже загружены (на шаге 2)
    После записи: doc.status = "indexed"
Почему запуск локальный, а не на VPS
Шаги 1-5 делают дорогие вызовы внешних API:

Gemini Vision — платный API (ключ у тебя локально)
OpenRouter (embeddings) — платный API
Cloudflare R2 — облачное хранилище
У Docker-контейнера на VPS нет доступа к .env с твоего компьютера, и нет смысла перекидывать ключи. Поэтому: локально считаем → записываем результат в VPS через туннель.

Зачем SSH-туннель
PostgreSQL на VPS работает внутри Docker-сети и не открыт наружу (это правильно с точки зрения безопасности). SSH-туннель создаёт "трубу":

localhost:5432  →  (SSH шифрование)  →  VPS:22  →  postgres:5432
Команда ssh -L 5432:localhost:5432 matsu -N буквально означает:

-L 5432:localhost:5432 — пробросить локальный порт 5432 → на сервере matsu → к localhost:5432
-N — не открывать интерактивный shell (только туннель)
Терминал "зависает" — это нормально, туннель активен пока окно открыто
Зачем передавать DATABASE_URL явно
В корне проекта лежит .env с:

DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/matsu_shi
postgres — это имя Docker-сервиса внутри Docker-сети. С твоего компьютера этот адрес не работает.

Явная передача DATABASE_URL="...@localhost:5432/..." переопределяет значение из .env и направляет записи в туннель.

Checkpoint-система: как не потерять часы работы
Флаг --save-artifacts сохраняет результат каждого шага в cache/{sha256}/.
Шаги 2 (visual) и 4 (enrich) имеют internal partial checkpoint:
- visual_partial.json — сохраняется после каждой страницы
- enriched_partial.json — сохраняется каждые 10 чанков
При перезапуске с --start-from partial подхватывается автоматически, удаляется при успехе.

# Упало на embed? Продолжаем с embed:
DATABASE_URL="..." PYTHONPATH=... \
uv run python scripts/ingest.py \
  --path "./scripts/samples/file.pdf" \
  --machine-model "WB97S-5" \
  --start-from embed

# Упало на write? Продолжаем с write (самое быстрое):
DATABASE_URL="..." PYTHONPATH=... \
uv run python scripts/ingest.py \
  --path "./scripts/samples/file.pdf" \
  --machine-model "WB97S-5" \
  --start-from write
Кеш идентифицирует файл по SHA256-хэшу содержимого. Один и тот же PDF → всегда один и тот же кеш-каталог.

Флаги ingest.py — краткая шпаргалка
Флаг	Что делает
--path FILE	Путь к PDF файлу
--machine-model "MODEL"	Название модели машины (произвольная строка)
--category "CAT"	Категория документа (maintenance / operations / etc.)
--save-artifacts	Сохранять артефакты каждого шага в cache/
--dry-run	Парсинг и чанкинг без записи в БД и R2 (для проверки)
--start-from STEP	Продолжить с шага: chunk / enrich / embed / write
--stop-after STEP	Остановиться после шага: parse / chunk / enrich / embed
--rebuild-index	Удалить старые чанки документа перед повторной записью
Naming convention: machine_model и category
machine_model — это поле поиска в БД. По нему фильтруются чанки при RAG-запросе.

WB97S-5EO и WB97S-5 — одна и та же машина, разные суффиксы обозначают рынок/сборку
Используй "WB97S-5" для ВСЕХ документов этой модели, независимо от суффикса
category — информационное поле, сейчас не влияет на RAG-поиск:

"maintenance" → Service Manual (SM) — регламенты, ТО, ремонт
"operations" → Operations Manual (OM) — управление, безопасность, рабочие процедуры