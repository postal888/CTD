# Деплой CrackTheDeck на сервер (VPS)

Один сервер: Nginx раздаёт фронт (`crackthedeck-deploy`) и проксирует `/api` на бэкенд (uvicorn :8000). Опционально на том же сервере — Docker с funds-rag (Find matching funds). Подходит для Ubuntu/Debian.

## Структура на сервере

После деплоя в `/var/www/crackthedeck/` должны быть:

- `crackthedeck-deploy/` — статика (index.html, style.css, app.js, статьи)
- `crackthedeck-backend/crackthedeck-backend/` — код бэкенда (main.py, .env, presentations, reports)
- `deploy/` — nginx конфиг, systemd unit, скрипты
- `venv/` — виртуальное окружение Python (создаётся при установке)
- при необходимости `Funds/` — данные для Find matching funds (funds_clean.jsonl), если поднимаешь funds-rag на этом же сервере

## 1. Сервер

- **ОС**: Ubuntu 22.04 (или 20.04 / Debian 11+)
- **Порты**: 80 (и при необходимости 443 для HTTPS)

## 2. Зависимости на сервере

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx poppler-utils libreoffice
```

- **poppler-utils** — конвертация PDF в картинки (pdftoppm)
- **libreoffice** — конвертация PPTX → PDF

Если будешь поднимать **Find matching funds** (funds-rag) на этом же сервере — установи Docker:

```bash
# Опционально: Docker для funds-rag
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# выйти и зайти в сессию или: newgrp docker
```

## 3. Код и виртуальное окружение

```bash
sudo mkdir -p /var/www/crackthedeck
sudo chown $USER:$USER /var/www/crackthedeck
cd /var/www/crackthedeck

# Клонировать репозиторий или залить папки: crackthedeck-deploy, crackthedeck-backend, deploy
# git clone https://github.com/YOUR_ORG/CTD.git .

# Удалить Windows poppler (на сервере используется системный)
rm -rf crackthedeck-backend/crackthedeck-backend/poppler-25.12.0 2>/dev/null || true

# Виртуальное окружение и зависимости бэкенда
python3.11 -m venv venv
source venv/bin/activate
pip install -r crackthedeck-backend/crackthedeck-backend/requirements.txt
deactivate
```

## 4. Переменные окружения бэкенда

```bash
cd /var/www/crackthedeck/crackthedeck-backend/crackthedeck-backend
cp .env.example .env
nano .env
```

Обязательно:

- `OPENAI_API_KEY=sk-...` — ключ OpenAI.

Опционально (для блока «Find matching funds»):

- `FUNDS_RAG_URL=http://127.0.0.1:8100` — если funds-rag запущен на этом же сервере (Docker). Если не задан, по умолчанию используется `http://localhost:8100`; без запущенного RAG кнопка «Find matching funds» будет возвращать ошибку или пустой список.

На Linux по умолчанию используются `libreoffice` и системный `pdftoppm`. При необходимости укажи `LIBREOFFICE_CMD` и `POPPLER_DIR`.

## 5. Nginx

Скопировать конфиг и подставить свой домен или IP:

```bash
sudo cp /var/www/crackthedeck/deploy/nginx-crackthedeck.conf /etc/nginx/sites-available/crackthedeck
sudo sed -i 's/YOUR_DOMAIN_OR_IP/ваш-домен.ru/' /etc/nginx/sites-available/crackthedeck
# или для доступа по IP: sudo sed -i 's/YOUR_DOMAIN_OR_IP/1.2.3.4/' ...
sudo ln -sf /etc/nginx/sites-available/crackthedeck /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx
```

Путь к статике в конфиге: `root /var/www/crackthedeck/crackthedeck-deploy`. Если положил проект в другой каталог — поправь `root` и пути в systemd.

## 6. Systemd (бэкенд)

- В юните должны совпадать пути: `WorkingDirectory`, `EnvironmentFile`, `ExecStart` (путь к `venv`).

```bash
sudo cp /var/www/crackthedeck/deploy/crackthedeck-backend.service /etc/systemd/system/
# При необходимости отредактировать пути
sudo nano /etc/systemd/system/crackthedeck-backend.service

sudo systemctl daemon-reload
sudo systemctl enable crackthedeck-backend
sudo systemctl start crackthedeck-backend
sudo systemctl status crackthedeck-backend
```

Проверка API напрямую:

```bash
curl http://127.0.0.1:8000/api/health
```

## 7. Права

- Nginx и uvicorn должны иметь доступ к файлам фронта и к каталогам бэкенда (загрузки, отчёты). Юнит запущен от `www-data`; если клонировал от своего пользователя:

```bash
sudo chown -R www-data:www-data /var/www/crackthedeck/crackthedeck-backend
sudo chown -R www-data:www-data /var/www/crackthedeck/crackthedeck-deploy
# venv можно оставить читаемым для www-data или запускать от пользователя с своим venv
```

Если venv в `/var/www/crackthedeck/venv` и принадлежит root, дать доступ на чтение/выполнение:

```bash
sudo chmod -R o+rX /var/www/crackthedeck/venv
```

## 8. HTTPS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d ваш-домен.ru
```

После этого обновлять сертификат не нужно — certbot настроит таймер.

## 9. Проверка

- В браузере: `https://ваш-домен.ru` — открывается лендинг.
- Загрузка питч-дека → выбор файла и отправка → ответ с ссылкой на PDF (запрос идёт на тот же хост по `/api/analyze`).
- Если настроен funds-rag: «Find matching funds» возвращает список фондов и стран.

## 10. (Опционально) Find matching funds — funds-rag на том же сервере

Если нужен блок «Find matching funds» с подбором инвесторов по профилю стартапа:

1. Установи Docker (см. п. 2).
2. Скопируй на сервер папку `funds-rag-service/funds-rag-service` и каталог `Funds` с файлом `funds_clean.jsonl` (или `investors_rag.jsonl` → скопировать в `funds_clean.jsonl`).
3. В `funds-rag-service/funds-rag-service` создай `.env` из `.env.example`, укажи `OPENAI_API_KEY`, `POSTGRES_PASSWORD`, при необходимости `FUNDS_HOST_PATH` (путь к папке Funds на сервере, например `/var/www/crackthedeck/Funds`).
4. Запусти сервис: `docker compose up -d`. Дождись healthcheck БД, затем выполни индексацию:
   ```bash
   docker compose exec rag python -m scripts.index_funds --jsonl /app/funds_data/funds_clean.jsonl
   ```
5. В бэкенде в `.env` задай `FUNDS_RAG_URL=http://127.0.0.1:8100` и перезапусти бэкенд: `sudo systemctl restart crackthedeck-backend`.

Подробнее: `funds-rag-service/funds-rag-service/README.md`.

## Краткий чеклист

1. Установить python3.11-venv, nginx, poppler-utils, libreoffice.
2. Положить в `/var/www/crackthedeck`: `crackthedeck-deploy`, `crackthedeck-backend`, `deploy`; удалить `poppler-25.12.0` с хоста; создать venv и установить зависимости бэкенда.
3. В бэкенде создать `.env` из `.env.example`, обязательно задать `OPENAI_API_KEY`; при использовании Find matching funds — `FUNDS_RAG_URL=http://127.0.0.1:8100`.
4. Подключить конфиг Nginx, заменить `YOUR_DOMAIN_OR_IP` на домен или IP, перезагрузить nginx.
5. Скопировать и включить systemd unit `crackthedeck-backend.service`, выдать права `www-data`, запустить сервис.
6. При необходимости настроить HTTPS через certbot.
7. (Опционально) Запустить funds-rag в Docker, проиндексировать фонды, перезапустить бэкенд.
