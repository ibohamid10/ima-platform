# Current State

Letztes Update: 2026-04-16

## Stand heute

- **Phase:** 1 (Woche 1 abgeschlossen)
- **Aktuelle Aufgabe:** Woche 2 ist gestartet. Neben Datenmodell, Snapshots und heuristischem Scoring gibt es jetzt einen ersten Creator-Ingest-Pfad, der Creator, Content und Snapshot in einem Schritt upsertet und direkt neu scoret.
- **Status:** `docker compose up -d`, `scripts/db_migrate.py`, `scripts/smoke_test.py`, `uv run pytest`, `ima run-agent classifier`, `ima creators ingest`, `ima creators record-snapshot` und `ima creators score` laufen lokal. `schema_migrations`, `creators`, `creator_content` und `creator_metric_snapshots` sind lokal verifiziert.
- **Blocker:** Keine

## Naechste Tasks

1. Den Creator-Ingest-Pfad in eine erste Temporal-Activity und einen ersten Workflow ueberfuehren
2. Evidence-Builder vorbereiten, inklusive Storage-Strategie fuer Rohdaten vor Umsetzung klaeren
3. Golden-Set-Pattern auf weitere LLM-basierte Agenten uebertragen
4. Growth-Tracker spaeter an echte Harvester-Quellen anschliessen statt nur an manuelle Fixtures

## Operativer Hinweis

Die Review-UI ist weiterhin noch nicht relevant. Sie beginnt erst in Woche 4. Bis dahin erfolgt die Interaktion mit der Pipeline ueber SQL-Tools, Temporal UI, Langfuse und CLI-Skripte.

## Update-Format fuer kuenftige Sessions

Agents sollen dieses Dokument am Ende jeder Session knapp, aber konkret aktualisieren:

- `Stand heute` nur ueberschreiben, nicht historisieren
- Erledigte Punkte aus `Naechste Tasks` entfernen oder umformulieren
- Neue Blocker explizit benennen
- Bei groesseren Meilensteinen den Phasenstand anpassen
- Wenn eine Entscheidung den Status veraendert, zuerst `DECISIONS.md` aktualisieren und danach den Status hier spiegeln

Wenn eine Session nur Analyse war, soll trotzdem klar dokumentiert werden, was jetzt der naechste konkrete Build-Schritt ist.
