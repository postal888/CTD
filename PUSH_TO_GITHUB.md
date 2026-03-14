# Как отправить проект на GitHub

1. **Создай репозиторий на GitHub** (если ещё нет): https://github.com/new  
   - Имя: например `CTD`  
   - Без README, .gitignore и лицензии (у нас уже есть коммит).

2. **Укажи URL своего репозитория** (замени `YOUR_GITHUB_USERNAME` на свой логин):
   ```bash
   cd e:\GIT\CTD
   git remote set-url origin https://github.com/YOUR_GITHUB_USERNAME/CTD.git
   ```
   Либо если репозиторий под организацией:
   ```bash
   git remote set-url origin https://github.com/ORG_NAME/CTD.git
   ```

3. **Отправь код на GitHub**:
   ```bash
   git push -u origin main
   ```
   При запросе авторизации используй свой GitHub логин и пароль (или Personal Access Token вместо пароля).

4. **(По желанию)** Настроить имя и email для коммитов:
   ```bash
   git config user.name "Твоё Имя"
   git config user.email "твой@email.com"
   ```
   Затем можно переписать последний коммит с правильным автором:
   ```bash
   git commit --amend --reset-author --no-edit
   git push -u origin main
   ```
