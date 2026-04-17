# Current State

Letztes Update: 2026-04-17

## Stand heute

- **Phase:** 1 (Woche 2 aktiv)
- **Aktuelle Aufgabe:** Neben dem Creator-Ingest-Workflow gibt es jetzt einen fixture-basierten Harvester-/Enricher-Stub, der Creator-Quellen auf `CreatorIngestInput` normalisiert und dann direkt oder via Temporal in denselben Ingest-Pfad schickt.
- **Status:** `docker compose up -d`, `scripts/db_migrate.py`, `scripts/smoke_test.py`, `uv run pytest`, `ima run-agent classifier`, `ima creators ingest`, `ima creators record-snapshot`, `ima creators score`, `ima temporal run-creator-worker`, `ima temporal ingest-creator` und `ima creators import-source-batch` laufen lokal. `schema_migrations`, `creators`, `creator_content`, `creator_metric_snapshots`, der erste orchestrierte Creator-Flow und ein fixture-basierter Source-Import sind lokal verifiziert.
- **Blocker:** Keine

## Naechste Tasks

1. Evidence-Builder vorbereiten, inklusive Storage-Strategie fuer Rohdaten vor Umsetzung klaeren
2. Den fixture-basierten Source-Import durch einen echten YouTube-Data-v3-Harvester ersetzen, sobald API-Key und Quoten-Setup lokal hinterlegt sind
3. Golden-Set-Pattern auf weitere LLM-basierte Agenten uebertragen
4. Brand-Seite und Spend-Intent-Scaffold fuer Woche 3 vorbereiten

## Operativer Hinweis

Die Review-UI ist weiterhin noch nicht relevant. Sie beginnt erst in Woche 4. Bis dahin erfolgt die Interaktion mit der Pipeline ueber SQL-Tools, Temporal UI, Langfuse und CLI-Skripte. Fuer Workflow-Code gilt jetzt explizit: nur sandbox-sichere Contracts in Workflows, alle DB- und Netzwerkarbeit in Activities.

## Update-Format fuer kuenftige Sessions

Agents sollen dieses Dokument am Ende jeder Session knapp, aber konkret aktualisieren:

- `Stand heute` nur ueberschreiben, nicht historisieren
- Erledigte Punkte aus `Naechste Tasks` entfernen oder umformulieren
- Neue Blocker explizit benennen
- Bei groesseren Meilensteinen den Phasenstand anpassen
- Wenn eine Entscheidung den Status veraendert, zuerst `DECISIONS.md` aktualisieren und danach den Status hier spiegeln

Wenn eine Session nur Analyse war, soll trotzdem klar dokumentiert werden, was jetzt der naechste konkrete Build-Schritt ist.
