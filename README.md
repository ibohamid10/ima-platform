# IMA Platform - Lokales Fundament

Dieses Repo enthaelt das lokale Fundament fuer eine interne Influencer Marketing Agency als headless Pipeline fuer einen Solo-Owner. Neben dem Woche-1-Basisstack gibt es jetzt auch erste Creator-Ingest-, Growth-Tracking- und Temporal-Orchestrierungsbausteine. Der tiefere Produkt- und Architekturkontext lebt in [.agent-context/PROJECT.md](/Users/hamidibr/Desktop/test/ima-platform/.agent-context/PROJECT.md) und den weiteren Dateien unter `.agent-context/`.

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

## Creator-Tracking und Scoring

```bash
uv run ima creators record-snapshot --platform youtube --handle fitgrowthlocal --captured-at 2026-03-15T10:00:00+00:00 --follower-count 130000 --average-views-30d 12000
uv run ima creators score --platform youtube --handle fitgrowthlocal
uv run ima creators ingest --input-file tests/fixtures/creator_ingest_example.json
uv run ima creators import-source-batch --input-file tests/fixtures/creator_source_batch.json --direct
```

## Erste Temporal-Orchestrierung

```bash
uv run ima temporal run-creator-worker
uv run ima temporal ingest-creator --input-file tests/fixtures/creator_ingest_temporal_run.json --workflow-id creator-ingest-local-001
uv run ima creators import-source-batch --input-file tests/fixtures/creator_source_batch.json --via-temporal --workflow-prefix source-fixture
```

Der Workflow delegiert bewusst alle DB- und I/O-Arbeit an Activities. Die Workflow-Payloads leben in `src/ima/creators/schemas.py`, damit die Temporal-Sandbox keine ORM- oder Service-Module importieren muss.

Der fixture-basierte Harvester-/Enricher-Stub lebt unter `src/ima/harvesters/`. Er normalisiert Rohdaten zuerst auf `CreatorIngestInput` und nutzt danach denselben Ingest-Pfad wie manuelle Creator-Fixtures. Das ist die Bruecke fuer spaetere echte YouTube-Data-v3-Integrationen.

## Echter YouTube-Import

Vor dem ersten Live-Import `YOUTUBE_DATA_API_KEY` in `.env` setzen. Der Live-Pfad nutzt bewusst `channel_id` als stabile Identitaet und nicht eine fuzzy Handle-Suche.

```bash
uv run ima creators import-youtube-channel --channel-id UC_x5XG1OV2P6uZZ5FSM9Ttw --direct
uv run ima creators import-youtube-channel --channel-id UC_x5XG1OV2P6uZZ5FSM9Ttw --via-temporal
```

## Evidence Builder

Der Evidence-Builder schreibt Rohartefakte im Dev-Setup ueber eine objekt-storage-artige Abstraktion nach `data/evidence/` und erzeugt dazu persistente `evidence_items` in der Datenbank. `source_uri` nutzt bereits das kanonische Format `evidence://<bucket>/<key>`, damit der spaetere Wechsel auf R2 oder S3 keinen Builder-Refactor braucht. Neben JSON-Artefakten werden jetzt auch HTML-Snapshots fuer Profil- und Content-Seiten gespeichert, wenn eine URL verfuegbar ist.

```bash
uv run ima evidence build-creator --platform youtube --handle googledevelopers
```

## Tests

```bash
uv run pytest
```

## Wo der Kontext lebt

Vor jeder neuen Aufgabe erst `.agent-context/` lesen. `CLAUDE.md` beschreibt die Bootstrap-Reihenfolge, `CURRENT_STATE.md` zeigt den aktuellen Stand, und `DECISIONS.md` bzw. `LESSONS.md` halten getroffene Architekturentscheidungen und Learnings fest.

Wenn Default-Ports lokal bereits belegt sind, koennen die Host-Ports ueber `.env` ueberschrieben werden, zum Beispiel `POSTGRES_PORT=15432` oder `REDIS_PORT=16379`. In diesem Fall muessen `DATABASE_URL`, `REDIS_URL`, `TEMPORAL_ADDRESS`, `QDRANT_URL` und `LANGFUSE_HOST` auf die gleichen Host-Ports zeigen.

Langfuse nutzt in dieser Dev-Umgebung fuer ClickHouse Docker-Volumes statt Windows-Bind-Mounts, weil ClickHouse-Migrations auf NTFS-Bind-Mounts bei `rename` scheitern koennen. Die uebrigen Service-Daten bleiben unter `./data/` erhalten.
