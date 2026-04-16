# Current State

Letztes Update: 2026-04-16

## Stand heute

- **Phase:** 0 (Setup)
- **Aktuelle Aufgabe:** Repo-Fundament aufbauen, dann Woche 1 starten
- **Status:** `.agent-context/` wurde gerade als persistentes Projekt-Memory aufgesetzt. Als Naechstes folgen Docker Compose, `LLMProvider`, `MailProvider`, `AgentContract` und `AgentExecutor`.
- **Blocker:** Keine

## Naechste Tasks

1. Docker Compose mit Temporal, Postgres, Redis und Qdrant aufsetzen
2. `LLMProvider`-Interface plus Anthropic-Adapter plus OpenAI-Adapter implementieren
3. `MailProvider`-Interface plus ersten Adapter fuer Instantly oder Smartlead implementieren
4. `AgentContract` als Basisklasse fuer versionierte Rollen-Definitionen erstellen
5. `AgentExecutor` mit Retry, Validation, Langfuse-Hook und Logging in `agent_runs` bauen
6. Einen Beispiel-Agenten als Referenz-Implementation erstellen, bevorzugt `Classifier`

## Operativer Hinweis

Die Review-UI ist in diesem Stadium noch nicht relevant. Sie beginnt erst in Woche 4. Bis dahin erfolgt die Interaktion mit der Pipeline ueber SQL-Tools, Temporal UI und CLI-Skripte.

## Update-Format fuer kuenftige Sessions

Agents sollen dieses Dokument am Ende jeder Session knapp, aber konkret aktualisieren:

- `Stand heute` nur ueberschreiben, nicht historisieren
- Erledigte Punkte aus `Naechste Tasks` entfernen oder umformulieren
- Neue Blocker explizit benennen
- Bei groesseren Meilensteinen den Phasenstand anpassen
- Wenn eine Entscheidung den Status veraendert, zuerst `DECISIONS.md` aktualisieren und danach den Status hier spiegeln

Wenn eine Session nur Analyse war, soll trotzdem klar dokumentiert werden, was jetzt der naechste konkrete Build-Schritt ist.
