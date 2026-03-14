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
```bash
nano /var/www/crackthedeck/crackthedeck-backend/crackthedeck-backend/.env
```
В файле пропиши (подставь свой ключ):
```
OPENAI_API_KEY=sk-...
```
Сохрани (Ctrl+O, Enter, Ctrl+X), затем:
```bash
sudo systemctl restart crackthedeck-backend
sudo systemctl status crackthedeck-backend
```

### 5. Проверка
- В браузере: **http://165.22.212.230**
- Должен открыться лендинг, загрузка деки идёт через `/api`.

---

## Обновление (код с GitHub, .env не трогаем)

Подключись к серверу и выполни (существующий `.env` с OPENAI_API_KEY сохранится):

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

## (Опционально) HTTPS и Find matching funds

- **HTTPS**: `sudo apt install certbot python3-certbot-nginx` и `sudo certbot --nginx -d твой-домен.ru` (если на этот IP привязан домен).
- **Find matching funds**: см. раздел 10 в [DEPLOY.md](DEPLOY.md) — установка Docker и funds-rag на этом же сервере.
