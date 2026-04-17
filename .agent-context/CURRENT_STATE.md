# Current State

Letztes Update: 2026-04-17

## Stand heute

- **Phase:** 1 (Woche 2 abgeschlossen, Woche 3 bereit)
- **Aktuelle Aufgabe:** Woche-2-Nachbesserung abgeschlossen und Readiness fuer Woche 3 herstellen.
- **Status:** Woche 2 ist jetzt formal auf Ziel-Spec nachgezogen. Alembic ist eingefuehrt, `scripts/db_migrate.py` nutzt `alembic upgrade head`, `creators` / `creator_content` / `evidence_items` sind auf das Zielschema erweitert, `niche_fit_score` und konfigurierbares Scoring sind implementiert, der Evidence-Builder folgt jetzt als echter Agent dem `AgentContract`-Pattern, der YouTube-Harvester unterstuetzt Channel-Imports plus Keyword-Discovery mit `search.list`, und `record_snapshot()` ist pro Creator/Tag idempotent. `docker compose up -d`, `uv run alembic upgrade head`, `uv run python scripts/smoke_test.py`, `uv run pytest` und `uv run ruff check` laufen lokal grün. Die Alembic-Revisionen wurden zusaetzlich auf einer frisch angelegten leeren Postgres-Testdatenbank verifiziert.
- **Blocker:** Keine formalen Woche-2-Blocker mehr. Offene Production-Fragen bleiben ausserhalb dieser Nachbesserung, blockieren Woche 3 aber nicht.

## Naechste Tasks

1. Brand-Datenmodell und erste `brands`-Migrationen fuer Woche 3 aufsetzen
2. Spend-Intent-Signale Phase 1 als erstes Brand-Scaffold implementieren
3. Brand-Harvester-/Enricher-Stubs analog zum Creator-Pfad anlegen
4. Danach Matching-Grundlage vorbereiten, damit Woche 4 `/matches` auf belastbaren Daten startet

## Operativer Hinweis

Die Review-UI ist weiterhin noch nicht relevant. Sie beginnt erst in Woche 4. Bis dahin erfolgt die Interaktion mit der Pipeline ueber SQL-Tools, Temporal UI, Langfuse und CLI-Skripte. Fuer Workflow-Code gilt weiterhin explizit: nur sandbox-sichere Contracts in Workflows, alle DB- und Netzwerkarbeit in Activities.

## Update-Format fuer kuenftige Sessions

Agents sollen dieses Dokument am Ende jeder Session knapp, aber konkret aktualisieren:

- `Stand heute` nur ueberschreiben, nicht historisieren
- Erledigte Punkte aus `Naechste Tasks` entfernen oder umformulieren
- Neue Blocker explizit benennen
- Bei groesseren Meilensteinen den Phasenstand anpassen
- Wenn eine Entscheidung den Status veraendert, zuerst `DECISIONS.md` aktualisieren und danach den Status hier spiegeln

Wenn eine Session nur Analyse war, soll trotzdem klar dokumentiert werden, was jetzt der naechste konkrete Build-Schritt ist.
