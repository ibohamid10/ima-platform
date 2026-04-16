# IMA Platform - Woche 1 Fundament

Dieses Repo enthaelt das technische Fundament fuer eine interne Influencer Marketing Agency als headless Pipeline fuer einen Solo-Owner. Der tiefere Produkt- und Architekturkontext lebt in [.agent-context/PROJECT.md](/Users/hamidibr/Desktop/test/ima-platform/.agent-context/PROJECT.md) und den weiteren Dateien unter `.agent-context/`.

## Setup

```bash
uv sync --dev
cp .env.example .env
docker compose up -d
uv run python scripts/db_migrate.py
uv run python scripts/smoke_test.py
```

## Erste CLI-Benutzung

```bash
uv run ima run-agent classifier --input-file tests/golden_sets/classifier/example_input.json
```

## Tests

```bash
uv run pytest
```

## Wo der Kontext lebt

Vor jeder neuen Aufgabe erst `.agent-context/` lesen. `CLAUDE.md` beschreibt die Bootstrap-Reihenfolge, `CURRENT_STATE.md` zeigt den aktuellen Stand, und `DECISIONS.md` bzw. `LESSONS.md` halten getroffene Architekturentscheidungen und Learnings fest.

Wenn Default-Ports lokal bereits belegt sind, koennen die Host-Ports ueber `.env` ueberschrieben werden, zum Beispiel `POSTGRES_PORT=15432` oder `REDIS_PORT=16379`. In diesem Fall muessen `DATABASE_URL`, `REDIS_URL`, `TEMPORAL_ADDRESS`, `QDRANT_URL` und `LANGFUSE_HOST` auf die gleichen Host-Ports zeigen.

Langfuse nutzt in dieser Dev-Umgebung fuer ClickHouse Docker-Volumes statt Windows-Bind-Mounts, weil ClickHouse-Migrations auf NTFS-Bind-Mounts bei `rename` scheitern koennen. Die uebrigen Service-Daten bleiben unter `./data/` erhalten.
