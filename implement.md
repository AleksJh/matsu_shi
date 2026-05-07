# Phase 9.3 — Threshold Validation

## 1. Текущая фаза и задача

- **Phase:** 9 — Pilot & Tuning
- **Sub-task ID:** 9.3
- **Title:** Threshold Validation

---

## 2. Цель

Проанализировать трассировки в Langfuse для первых 50+ запросов от тестовых механиков, оценить распределение `retrieval_score`, и при необходимости скорректировать пороговые значения в `.env` без изменения кода.

**Почему это важно:**
- `RETRIEVAL_SCORE_THRESHOLD=0.65` определяет, когда используется lite vs advanced модель
- `RETRIEVAL_NO_ANSWER_THRESHOLD=0.30` определяет, когда возвращается "not found"
- Неправильные пороги приводят к: перерасходу API-бюджета или недостаточно качественным ответам

---

## 3. PRD References

- **§5.3** — Retrieval Score Thresholds: таблица с условиями и действиями
- **§6.2** — Model Routing Logic: `if max_retrieval_score < 0.65 or query_class == "complex"`
- **§8** — Non-functional requirements: P95 latency targets

---

## 4. Файлы для создания

**Нет** — это аналитическая задача, код не требуется.

---

## 5. Файлы для модификации

| Файл | Изменения |
|------|-----------|
| `.env` | Опционально: `RETRIEVAL_SCORE_THRESHOLD`, `RETRIEVAL_NO_ANSWER_THRESHOLD` |

---

## 6. Ключевые импорты и зависимости

| Файл | Назначение |
|------|------------|
| `backend/app/core/config.py` | Чтение `RETRIEVAL_SCORE_THRESHOLD=0.65`, `RETRIEVAL_NO_ANSWER_THRESHOLD=0.30` |
| `backend/app/rag/retriever.py` | Вычисляет `max_score` из dense retrieval; применяет пороги |
| `backend/app/core/tracing.py` | Langfuse client для анализа трассировок |

**Dependency chain:**
```
Query → retrieve() → dense_retrieve() → max_score
                             ↓
                    RETRIEVAL_NO_ANSWER_THRESHOLD (0.30) → no_answer=True
                             ↓
                    RETRIEVAL_SCORE_THRESHOLD (0.65) → recommended_model
```

---

## 7. Заметки по реализации

**Пороги определены в `backend/app/core/config.py`:**
```python
RETRIEVAL_SCORE_THRESHOLD: float = 0.65
RETRIEVAL_NO_ANSWER_THRESHOLD: float = 0.30
```

**Логика в `retriever.py` (§5.3):**
```python
# retriever.py:136 — early exit
if max_score < settings.RETRIEVAL_NO_ANSWER_THRESHOLD:
    return RetrievalResult(no_answer=True, ...)

# retriever.py:171-175 — model routing
recommended = (
    settings.LLM_ADVANCED_MODEL
    if max_score < settings.RETRIEVAL_SCORE_THRESHOLD
    else settings.LLM_LITE_MODEL
)
```

**Правила корректировки (§5.3):**

| Проблема | Решение |
|----------|---------|
| Слишком много "Информация не найдена" | Уменьшить `RETRIEVAL_NO_ANSWER_THRESHOLD` (напр. 0.25) |
| "not found" содержит hallucination | Увеличить `RETRIEVAL_NO_ANSWER_THRESHOLD` (напр. 0.35) |
| Слишком много advanced-моделей | Увеличить `RETRIEVAL_SCORE_THRESHOLD` (напр. 0.70) |
| Lite-ответы низкого качества | Уменьшить `RETRIEVAL_SCORE_THRESHOLD` (напр. 0.60) |

**Анализ в Langfuse:**
- Каждая трассировка содержит: `retrieval_score`, `model_used`, `query_class`, `no_answer`
- Группировка по `model_used`: должно быть ~70% lite, ~30% advanced для типичной механики
- Проверить: ни один ответ с `no_answer=True` не содержит hallucination

---

## 8. Integration Points

- **Phase 9.2** — результаты онбординга механиков генерируют данные для анализа
- **Phase 9.4** — выводы из threshold validation влияют на результаты verification plan
- **Phase 9.5** — мониторинг Langfuse подтверждает корректность порогов

---

## 9. Критерий завершения

**Done When:**

1. **Минимум 50 запросов накоплено в `queries` таблице:**
   ```bash
   docker compose exec backend python -c "
   from app.core.database import AsyncSessionLocal
   from sqlalchemy import select, func
   from app.models.query import Query
   import asyncio
   
   async def count():
       async with AsyncSessionLocal() as s:
           r = await s.execute(select(func.count(Query.id)))
           print(f'Total queries: {r.scalar()}')
   asyncio.run(count())
   "
   ```

2. **Анализ распределения в Langfuse:**
   - Открыть Langfuse dashboard
   - Фильтровать по last 7 days
   - Проверить: `retrieval_score` гистограмма
   - Проверить: доля lite vs advanced моделей

3. **Подтверждение: нет hallucination при no_answer:**
   - Каждый ответ с `no_answer=True` содержит строго: "Информация не найдена. Попробуйте добавить конкретику в запрос."
   - Нет сгенерированного текста в этих ответах

4. **Опционально: корректировка порогов в `.env`:**
   ```bash
   # Если нужно изменить пороги:
   # RETRIEVAL_SCORE_THRESHOLD=0.65  ← по умолчанию
   # RETRIEVAL_NO_ANSWER_THRESHOLD=0.30  ← по умолчанию
   ```

**Verification steps:**
```bash
# 1. Проверить количество запросов
docker compose exec postgres psql -U postgres -d matsu_shi \
  -c "SELECT COUNT(*) FROM queries;"

# 2. Проверить распределение retrieval_score
docker compose exec postgres psql -U postgres -d matsu_shi \
  -c "SELECT 
        COUNT(*) as total,
        AVG(retrieval_score) as avg_score,
        MIN(retrieval_score) as min_score,
        MAX(retrieval_score) as max_score,
        SUM(CASE WHEN no_answer THEN 1 ELSE 0 END) as no_answer_count
      FROM queries;"

# 3. Проверить модель-использование
docker compose exec postgres psql -U postgres -d matsu_shi \
  -c "SELECT model_used, COUNT(*) FROM queries GROUP BY model_used;"

# 4. Langfuse dashboard:
#    -打开 Langfuse → проект → Traces
#    - Фильтр: last 7 days
#    - Группировка по query_class
```

---

## 10. Следующие шаги

После завершения Phase 9.3 → перейти к **Phase 9.4 (Run Verification Plan)**:
- Выполнить все тесты из PRD §13 вручную
- Задокументировать pass/fail для каждого теста
- Исправить любые failures до завершения пилота
