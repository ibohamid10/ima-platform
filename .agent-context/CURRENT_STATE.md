# Current State

Letztes Update: 2026-04-18

## Stand heute

- **Phase:** 1 (Woche 2 abgeschlossen, Woche 3 bereit)
- **Aktuelle Aufgabe:** Woche 3 ist funktional aufgebaut; naechster Schwerpunkt kann auf Matching und der Woche-4-UI/API-Schicht liegen.
- **Status:** Der Woche-3-Unterbau steht. Die YAML-getriebene `NicheRegistry` laedt jetzt `productivity` und `tech` aus `config/niches/`; Creator-Discovery unterstuetzt `ima creators discover-youtube --niche <id>`, und `creator_niche_scores` speichert den per-Nische-Fit-Breakdown, waehrend `creators.niche_fit_score` als Best-Score-Shortcut bestehen bleibt. Die Brand-Seite ist als eigener Pfad aufgebaut: Revision `20260418_010` fuehrt `brands`, `brand_creator_matches`, `creator_niche_scores` und alle fuenf Suppression-Tabellen ein; `BrandSeeder`, `BrandEnricher`, `BrandSpendIntentScorer`, `HunterAdapter`-Stub, deterministische Brand-Evidence und die neuen CLI-Befehle `ima brands seed`, `ima brands enrich-websites`, `ima brands score-spend-intent` und `ima brands build-evidence` laufen lokal. `evidence_items` kann jetzt Creator- und Brand-Fakten aufnehmen. Die Review-UI-Entscheidung ist final auf Next.js 15 festgezogen, und der Meta-Ad-Library-Pfad faellt ohne Token kontrolliert auf einen Fallback zurueck, damit Spend-Intent nicht an einem einzelnen API-Zugang blockiert. `uv run alembic upgrade head`, `uv run ima brands seed --file config/seeds/productivity_brands.yaml`, `uv run ima brands enrich-websites --domain notion.so`, `uv run ima brands score-spend-intent --domain notion.so`, `uv run ima brands build-evidence --domain notion.so`, `uv run ima creators discover-youtube --niche productivity --max-results-per-keyword 1 --max-videos 1 --direct`, `uv run python scripts/smoke_test.py`, `uv run pytest` und `uv run ruff check .` laufen lokal gruen.
- **Blocker:** Keine formalen Woche-2-Blocker mehr.

## Naechste Tasks

1. Match-Scoring-Service auf `brands`, `creators` und `brand_creator_matches` aufsetzen
2. Woche-4-API-/UI-Schicht fuer `/matches` entlang der finalen Next.js-Entscheidung vorbereiten
3. Brand-Level Enrichment um robustere Hiring- und Branded-Content-Quellen erweitern
4. Golden Sets und Heuristiken schrittweise von Legacy-Fitness-Faellen auf die Woche-3-Nischen `productivity` und `tech` umziehen

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
