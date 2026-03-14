.PHONY: up down build index logs health

# Запустить всё
up:
	docker compose up -d --build

# Остановить
down:
	docker compose down

# Пересобрать
build:
	docker compose build --no-cache

# Проиндексировать CSV в pgvector
index:
	docker compose exec rag python -m scripts.index_funds --csv data/funds.csv --batch-size 50

# Логи
logs:
	docker compose logs -f rag

# Проверить здоровье
health:
	curl -s http://localhost:8100/health | python3 -m json.tool

# Тестовый поиск
test-search:
	curl -s -X POST http://localhost:8100/api/rag/search \
		-H "Content-Type: application/json" \
		-d '{"query": "early stage VC in Southeast Asia fintech", "top_k": 5}' \
		| python3 -m json.tool
