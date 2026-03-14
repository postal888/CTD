# CrackTheDeck — Funds RAG Service v2

Standalone микросервис для матчинга фондов с стартапами.  
Сервер делает только лёгкую работу (SQL), вся генерация — на стороне OpenAI.

## Архитектура

```
Питч-дек (PDF/PPTX)
       │
       ▼
┌──────────────────────┐
│  crackthedeck        │  ← парсит PDF, получает текст
│  (основной бэкенд)   │
└──────┬───────────────┘
       │ POST /api/rag/extract   (текст питча)
       ▼
┌──────────────────────┐
│  RAG Service         │
│  1. GPT-4o извлекает │  ← OpenAI API (не нагружает сервер)
│     параметры        │
│  2. pgvector ищет    │  ← SQL запрос (миллисекунды)
│     фонды            │
│  3. GPT-4o генерирует│  ← OpenAI API (не нагружает сервер)
│     рекомендации     │
└──────────────────────┘
       │
       ▼
  JSON с ранжированными
  фондами + объяснениями
```

**Нагрузка на сервер:** только pgvector SQL-запрос (~5ms).  
**Всё остальное:** OpenAI API.

## Быстрый старт

### 1. Скопировать на сервер

```bash
scp -r funds-rag-service root@YOUR_SERVER_IP:/var/www/funds-rag
```

### 2. Настроить .env

```bash
cd /var/www/funds-rag
cp .env.example .env
nano .env   # вписать OPENAI_API_KEY и пароль PostgreSQL
```

### 3. Запустить

```bash
docker compose up -d --build
```

### 4. Проиндексировать фонды (JSONL)

Используется почищенный файл `E:\GIT\CTD\Funds\funds_clean.jsonl` (подмонтирован в контейнер как `/app/funds_data`):

```bash
docker compose exec rag python -m scripts.index_funds --jsonl /app/funds_data/funds_clean.jsonl
```

Либо задай в `.env` переменную `FUNDS_JSONL_PATH` и запусти без аргумента:

```bash
docker compose exec rag python -m scripts.index_funds
```

Поддержка Excel (.xls): `--xls /app/funds_data/funds_clean.xls`. CSV (legacy): `--csv путь/к/file.csv`.

### 5. Проверить

```bash
curl http://localhost:8100/health
```

## API Endpoints

### POST /api/rag/match  ← ОСНОВНОЙ

Полный пайплайн матчинга: параметры стартапа → поиск фондов → GPT-4o рекомендации.

**Request:**
```json
{
  "startup": {
    "company_name": "FinBot",
    "industry": "fintech",
    "sub_industry": "personal finance",
    "stage": "seed",
    "business_model": "B2C SaaS",
    "geography": "Brazil, Latin America",
    "target_raise": "$1.5M",
    "description": "AI-powered personal finance assistant for emerging markets"
  },
  "top_k": 10,
  "language": "en"
}
```

**Response:**
```json
{
  "startup": { ... },
  "total_candidates": 10,
  "recommendations": [
    {
      "investor_name": "Valor Capital Group",
      "country": "Brazil; United States",
      "overview": "Cross-border VC focused on Brazil and LatAm",
      "website": "https://valorcapitalgroup.com",
      "linkedin": "...",
      "similarity": 0.8723,
      "reasoning": "Strong fit: Valor focuses on Brazil/LatAm fintech at seed-Series A, with a portfolio of B2C financial products."
    }
  ],
  "summary": "Top matches include LatAm-focused VCs with fintech expertise. Valor Capital and Kaszek are strongest fits given your geography and stage."
}
```

### POST /api/rag/extract

Извлекает параметры стартапа из текста питч-дека. Используй после парсинга PDF.

```json
{
  "pitch_text": "FinBot is an AI-powered personal finance app... raising $1.5M seed round..."
}
```

### POST /api/rag/search

Прямой семантический поиск (без GPT-4o рекомендаций).

### GET /api/rag/funds?q=fintech&country=Japan&limit=20

Текстовый поиск с пагинацией.

### GET /api/rag/stats

Статистика по базе.

## Интеграция с crackthedeck

```python
import httpx

RAG_URL = "http://127.0.0.1:8100"


async def match_funds_for_pitch(pitch_text: str, language: str = "en"):
    """
    Полный пайплайн: текст питча → параметры → фонды → рекомендации.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        # Шаг 1: извлечь параметры стартапа из питча
        extract_resp = await client.post(
            f"{RAG_URL}/api/rag/extract",
            json={"pitch_text": pitch_text},
        )
        extract_resp.raise_for_status()
        startup = extract_resp.json()["startup"]

        # Шаг 2: найти фонды и получить рекомендации
        match_resp = await client.post(
            f"{RAG_URL}/api/rag/match",
            json={
                "startup": startup,
                "top_k": 10,
                "language": language,
            },
        )
        match_resp.raise_for_status()
        return match_resp.json()
```

Или одним вызовом, если параметры уже извлечены при анализе питча:

```python
async def match_funds(startup_profile: dict, top_k: int = 10):
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{RAG_URL}/api/rag/match",
            json={"startup": startup_profile, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json()
```

## Стоимость за запрос

| Этап | Где выполняется | Стоимость |
|------|-----------------|-----------|
| Извлечение параметров (extract) | OpenAI GPT-4o | ~$0.01 |
| Эмбеддинг запроса | OpenAI Embeddings | ~$0.00002 |
| pgvector поиск | Локальный сервер | $0 |
| Генерация рекомендаций (match) | OpenAI GPT-4o | ~$0.02 |
| **Итого за запрос** | | **~$0.03** |

## Обновление данных

```bash
# Заменить CSV и переиндексировать
docker compose exec rag python -m scripts.index_funds --csv data/funds.csv
```
