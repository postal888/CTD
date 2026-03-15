# Деплой на 165.22.212.230

## Вариант 1: С локальной машины одной командой (PowerShell / Git Bash)

Подставь своего пользователя сервера (часто `root` или `ubuntu`):

**PowerShell (Windows):**
```powershell
cd e:\GIT\CTD
Get-Content deploy\deploy-remote.sh -Raw | ssh root@165.22.212.230 "bash -s"
```

**Git Bash / Linux / Mac:**
```bash
cd /path/to/CTD
ssh root@165.22.212.230 'bash -s' < deploy/deploy-remote.sh
```

Если подключаешься по ключу не из стандартного места:
```powershell
ssh -i C:\path\to\your_key root@165.22.212.230 "bash -s" < deploy/deploy-remote.sh
```

---

## Вариант 2: Вручную по шагам

### 1. Подключись по SSH
```bash
ssh root@165.22.212.230
# или: ssh ubuntu@165.22.212.230
```

### 2. Установи зависимости (если ещё не стоят)
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx poppler-utils libreoffice
```
Если `python3.11` нет в репозитории:
```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
sudo apt install -y nginx poppler-utils libreoffice
```

### 3. Клонируй репозиторий и запусти установку
```bash
sudo mkdir -p /var/www/crackthedeck
sudo chown $USER:$USER /var/www/crackthedeck
cd /var/www/crackthedeck
git clone https://github.com/postal888/CTD.git .
chmod +x deploy/server-setup.sh
./deploy/server-setup.sh 165.22.212.230
```

### 4. Задай API-ключ OpenAI и перезапусти бэкенд

**Вариант А — общий .env в папке проекта (CTD / crackthedeck)** — файл `/var/www/crackthedeck/.env` (рекомендуется):
```bash
sudo nano /var/www/crackthedeck/.env
```
Добавь строку (подставь свой ключ):
```
OPENAI_API_KEY=sk-proj-...
```
Сохрани (Ctrl+O, Enter, Ctrl+X). Этот файл переопределяет переменные из папки бэкенда.

**Вариант Б — только в папке бэкенда:**
```bash
nano /var/www/crackthedeck/crackthedeck-backend/crackthedeck-backend/.env
```
В файле пропиши `OPENAI_API_KEY=sk-...`, сохрани.

Затем в обоих случаях:
```bash
sudo systemctl restart crackthedeck-backend
sudo systemctl status crackthedeck-backend
```

### 5. Проверка
- В браузере: **http://165.22.212.230**
- Должен открыться лендинг, загрузка деки идёт через `/api`.

---

## Обновление (код с GitHub, .env не трогаем)

Подключись к серверу и выполни (существующие `.env` в корне и в бэкенде не трогаются):

```bash
ssh root@165.22.212.230
cd /var/www/crackthedeck
git fetch origin
git reset --hard origin/main
sudo systemctl restart crackthedeck-backend
```

Или одной командой с локальной машины (PowerShell):

```powershell
ssh root@165.22.212.230 "cd /var/www/crackthedeck && git fetch origin && git reset --hard origin/main && sudo systemctl restart crackthedeck-backend"
```

---

## HTTPS (сертификат, чтобы не было «небезопасно»)

Сертификат можно получить только для **домена**, не для IP. Нужно:

1. **Привязать домен к серверу:** в DNS у регистратора создать A-запись для своего домена (например `crackthedeck.com`) на IP `165.22.212.230`.
2. **Дождаться обновления DNS** (от нескольких минут до часа).
3. **На сервере** запустить скрипт (подставь свой домен и при желании email):

```bash
ssh root@165.22.212.230
cd /var/www/crackthedeck
chmod +x deploy/setup-https.sh
./deploy/setup-https.sh твой-домен.ru
# или с email (без интерактива): ./deploy/setup-https.sh твой-домен.ru you@email.com
```

Скрипт установит certbot, подставит домен в Nginx, получит сертификат Let's Encrypt и включит редирект HTTP → HTTPS. После этого открывай сайт по **https://твой-домен.ru**.

**Вручную (без скрипта):**
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo sed -i 's/server_name .*/server_name твой-домен.ru _;/' /etc/nginx/sites-available/crackthedeck
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d твой-домен.ru --redirect
```

Сертификат обновляется автоматически (certbot ставит таймер). Если домена нет, для IP бесплатный «зелёный» сертификат недоступен — браузер будет показывать «небезопасно» при доступе по IP.

---

## (Опционально) Find matching funds

См. раздел 10 в [DEPLOY.md](DEPLOY.md) — установка Docker и funds-rag на этом же сервере.
