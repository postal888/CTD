# CrackTheDeck — деплой на сервер

В этой папке конфиги для развёртывания на VPS (Ubuntu/Debian).

| Файл | Назначение |
|------|------------|
| **DEPLOY.md** | Пошаговая инструкция по деплою (обязательно к прочтению) |
| **nginx-crackthedeck.conf** | Nginx: статика из `crackthedeck-deploy`, прокси `/api` на бэкенд :8000 |
| **crackthedeck-backend.service** | Systemd unit для uvicorn (бэкенд) |
| **server-setup.sh** | Скрипт первичной настройки на сервере: venv, nginx, systemd, права |

Перед деплоем убедись, что на сервер скопированы:

- `crackthedeck-deploy/` (весь фронт: index.html, style.css, app.js, статьи)
- `crackthedeck-backend/` (код бэкенда с `crackthedeck-backend/` внутри)
- `deploy/` (эта папка)

Опционально для «Find matching funds»: папка `Funds` с `funds_clean.jsonl` и проект `funds-rag-service` — см. раздел 10 в DEPLOY.md.

Быстрый старт на сервере (после копирования файлов в `/var/www/crackthedeck`):

```bash
cd /var/www/crackthedeck
chmod +x deploy/server-setup.sh
./deploy/server-setup.sh ваш-домен.ru
# затем: nano crackthedeck-backend/crackthedeck-backend/.env  → OPENAI_API_KEY=sk-...
# sudo systemctl restart crackthedeck-backend
```

Подробно: **DEPLOY.md**.
