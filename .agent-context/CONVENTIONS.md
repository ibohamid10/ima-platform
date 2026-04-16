# Konventionen

## Grundhaltung

Dieses Projekt bevorzugt einfache, austauschbare und beobachtbare Bausteine. Fachlogik soll nicht direkt an Vendor-APIs oder Framework-Patterns kleben. Alle strukturierten Daten werden explizit modelliert, validiert und versioniert.

## Python-Defaults

### Version und Package-Management

- Python `3.12+`
- Package-Manager: `uv`

`uv` ist der Default, weil es schnell, modern und fuer ein neues Repo einfacher als Poetry ist, ohne auf reproduzierbare Environments zu verzichten. Falls spaeter ein abweichender Build- oder Publish-Bedarf entsteht, ist das eine explizite Architekturentscheidung und gehoert nach `DECISIONS.md`.

### Schemas und Datenstrukturen

- Pydantic v2 fuer alle Input-, Output-, Config- und Tool-Schemas
- Niemals rohe `dict`-Literale fuer strukturierte Domainedaten weiterreichen
- Tool-Schemas immer als Pydantic-Modelle
- `AgentContract`-Inputs und -Outputs immer versioniert denken

### Async-Style

- `asyncio`-first
- Async Clients bevorzugen, wenn Bibliotheken es sauber unterstuetzen
- Sync-Code nur fuer klar lokale, CPU-leichte oder bibliotheksbedingte Pfade
- Temporal Activities und I/O-lastige Integrationen so designen, dass Blocking minimiert wird

### Fehlerbehandlung

- Explizite Exception-Klassen pro Domain, zum Beispiel fuer `llm`, `mail`, `scraping`, `evidence`, `matching`
- Keine stillen `except Exception`-Bloecke ohne Re-Raise oder Mapping
- Fehler so modellieren, dass Retries, Dead-Letter-Entscheidungen und Human Review voneinander trennbar bleiben
- Validation-Failures sind eigene Fehlerklasse, nicht generische Runtime-Fehler

### Logging

- `structlog` als Logging-Standard
- Produktion: JSON-Logs
- Entwicklung: lesbare strukturierte Logs
- Immer mit Kontextfeldern wie `workflow_id`, `activity_id`, `agent_name`, `provider`, `model`, `brand_id`, `creator_id`, `thread_id`
- Keine Prompts oder personenbezogenen Rohdaten ungefiltert in Logs kippen

### Tests

- `pytest` als Test-Runner
- `pytest-asyncio` fuer async Tests
- Fixture-Factories statt schwerer globaler Fixtures
- Golden Sets fuer Agent-Evals separat und reproduzierbar pflegen
- Jeder LLM-basierte Agent muss mindestens einen Golden-Set-Test haben, der gegen verifizierte Input/Output-Paare laeuft. Ohne Golden Set kein Merge.
- Contract-Tests fuer Provider-Adapter
- Workflow-nahe Tests fuer kritische Gates wie Suppression und Evidence-Coverage

## Architektur-Regeln im Code

- Nie direkte LLM-Vendor-Calls, immer ueber `LLMProvider`
- Nie direkte Mail-Vendor-Calls, immer ueber `MailProvider`
- Keine Agent-SDKs oder Multi-Agent-Frameworks einschleusen
- `agent_runs` ist Pflichtpfad, kein optionales Logging
- Jede faktische Behauptung, die spaeter in Mailtext landet, muss auf `evidence_items` rueckfuehrbar sein

## Prompt- und Agent-Patterns

- System-Prompts als Templates, nicht inline zusammengeklebter String-Spaghetti
- Few-Shots nur dort, wo sie messbar helfen, besonders beim Copywriter
- Output immer strikt gegen Pydantic-Schema validieren
- Retries nur kontrolliert und mit Grund, nicht blind

## Naming-Konventionen

- Python: `snake_case` fuer Module, Funktionen, Variablen und Dateinamen
- Klassen: `PascalCase`
- Agent-Namen als Klassennamen und Contract-Namen, zum Beispiel `ClassifierAgent`
- Tabellen- und Feldnamen im Storage: `snake_case`
- Keine uneinheitlichen Synonyme im Code, wenn das Glossar einen bevorzugten Begriff vorgibt

## Inline-Decision-Anchors

Wenn Code auf eine bewusste Projektentscheidung zurueckgeht, wird ein knapper Anchor gesetzt:

```python
# DECISION: DECISIONS.md#2026-04-16--keine-agent-sdks
```

Die Anchors sind sparsam zu verwenden, aber hilfreich an Stellen, an denen jemand sonst spaeter "warum so?" fragt.

## Frontend-Konventionen fuer die Review-UI

Diese Regeln gelten ab Woche 4, wenn die Review-UI beginnt:

- TypeScript strict mode
- Server Components first
- Client Components nur dort, wo Interaktivitaet wirklich noetig ist
- `shadcn/ui` als primaere Komponentenquelle
- Keine CSS-in-JS-Loesungen
- Kein Redux, kein Zustand als globaler Default
- Server-State ueber native Server Components oder gezielt ueber React Query
- Forms und Actions moeglichst nah am Server halten
- Fokus auf funktionale Operator-Flows statt Design-Polish

## Dokumentations-Regeln

- Architekturentscheidungen in `DECISIONS.md`, nicht in zufaelligen PR-Kommentaren vergraben
- Fehler mit Prevention-Rule in `LESSONS.md`
- Offene Unsicherheit sichtbar in `OPEN_QUESTIONS.md`
- `CURRENT_STATE.md` am Ende jeder Session aktualisieren
