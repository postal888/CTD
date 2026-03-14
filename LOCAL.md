# Запуск CrackTheDeck локально (все сервисы)

## Что нужно

- **Python 3.10+** (для бэкенда CTD и скриптов)
- **Docker Desktop** (для funds-rag-service: Postgres + pgvector + RAG API)
- **OpenAI API key** (для анализа дек и для RAG)
- На Windows: **Poppler** и **LibreOffice** (как в основном README бэкенда)

## 1. Funds RAG (матчинг фондов)

```powershell
cd e:\GIT\CTD\funds-rag-service\funds-rag-service
copy .env.example .env
# Открой .env и задай OPENAI_API_KEY=sk-... и POSTGRES_PASSWORD=надёжный_пароль

docker compose up -d --build
# Дождись запуска (10–30 сек). Файл фондов подмонтирован из E:\GIT\CTD\Funds (Funds_no-China_no-India_ext.csv).
# Один раз проиндексируй (в контейнере путь /app/funds_data/...):
docker compose exec rag python -m scripts.index_funds --csv /app/funds_data/Funds_no-China_no-India_ext.csv
```

Проверка: в браузере или `curl http://localhost:8100/health` — в ответе должно быть `"funds_indexed": 3000+`.

## 2. Бэкенд CrackTheDeck

```powershell
cd e:\GIT\CTD\crackthedeck-backend\crackthedeck-backend
copy .env.example .env
# Задай OPENAI_API_KEY=sk-... (и при необходимости FUNDS_RAG_URL=http://localhost:8100)

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Или из корня: `.\crackthedeck-backend\crackthedeck-backend\run_backend.ps1`.

## 3. Фронт

```powershell
cd e:\GIT\CTD\crackthedeck-deploy
python -m http.server 5500
```

## 4. Всё одной командой (после настройки .env)

Из корня `e:\GIT\CTD`:

```powershell
.\start-local.ps1
```

Скрипт поднимает RAG (Docker), затем бэкенд и фронт. При первом запуске RAG обязательно выполни индексацию (шаг 1 выше).

## Итог

| Сервис        | URL                      |
|---------------|--------------------------|
| Сайт          | http://localhost:5500    |
| API CTD       | http://localhost:8000    |
| Funds RAG API | http://localhost:8100    |

- **Upload Deck** — анализ питч-дека (бэкенд CTD).
- **Find matching funds** — матчинг фондов (CTD вызывает RAG на 8100).
