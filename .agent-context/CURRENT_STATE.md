# Current State

Letztes Update: 2026-04-17

## Stand heute

- **Phase:** 1 (Woche 2 aktiv)
- **Aktuelle Aufgabe:** Der Evidence-Builder schreibt jetzt nicht nur JSON-Rohartefakte, sondern auch HTML-Snapshots fuer Profil- und Content-Seiten auf denselben kanonischen `evidence://bucket/key`-Pfad. Damit ist die Rohdatenbasis fuer spaetere Screenshots und staerkere Claim-Reproduktion vorbereitet.
- **Status:** `docker compose up -d`, `scripts/db_migrate.py`, `scripts/smoke_test.py`, `uv run pytest`, `ima run-agent classifier`, `ima creators ingest`, `ima creators record-snapshot`, `ima creators score`, `ima temporal run-creator-worker`, `ima temporal ingest-creator`, `ima creators import-source-batch`, `ima creators import-youtube-channel` und `ima evidence build-creator` laufen lokal. `schema_migrations`, `creators`, `creator_content`, `creator_metric_snapshots`, `evidence_items`, der erste orchestrierte Creator-Flow, der fixture-basierte Source-Import, der Live-YouTube-Import gegen einen echten Kanal, der Live-Evidence-Build gegen diesen Kanal und HTML-Snapshots fuer dessen Profil-/Content-Seiten sind lokal verifiziert.
- **Blocker:** Keine

## Naechste Tasks

1. Evidence-Builder um Screenshots und weitere Rohartefakte erweitern
2. Golden-Set-Pattern auf weitere LLM-basierte Agenten uebertragen
3. Retention-, Verschluesselungs- und Production-Provider-Policy fuer Evidence-Artefakte finalisieren
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
