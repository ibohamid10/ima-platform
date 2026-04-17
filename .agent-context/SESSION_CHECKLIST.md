# Session Checklist

## Session-Ende-Ritual

Jede Agent-Session endet mit diesem kurzen Review:

- [ ] Ist `CURRENT_STATE.md` aktualisiert
- [ ] Ist bei Review-, Abnahme- oder Go/No-Go-Sessions das Ergebnis mit klaren PASS/WARN/FAIL-Blockern in `CURRENT_STATE.md` gespiegelt
- [ ] Hat die Session eine neue Entscheidung erzeugt, die in `DECISIONS.md` festgehalten werden muss
- [ ] Hat die Session einen Fehler oder teuren Umweg sichtbar gemacht, der in `LESSONS.md` gehoert
- [ ] Wurde eine offene Frage geklaert und deshalb aus `OPEN_QUESTIONS.md` entfernt
- [ ] Ist eine neue offene Frage entstanden und wurde sie in `OPEN_QUESTIONS.md` ergaenzt
- [ ] Referenziert die Commit-Message relevante Context-Files oder ist der Scope aus dem Diff klar genug

## Wochen-Review-Checkliste (15 Minuten)

- [ ] Stimmt `CURRENT_STATE.md` noch mit der Realitaet ueberein
- [ ] Sind `DECISIONS.md` und `ARCHITECTURE.md` konsistent
- [ ] Gibt es offene Fragen, die eigentlich schon entschieden wurden
- [ ] Gibt es Learnings aus der Woche, die nur in Chat-Verlaeufen existieren
- [ ] Ist der Bootstrap-Pfad fuer neue Sessions noch schlank genug
- [ ] Sind die Gate-Checks fuer `pytest`, Migrationen, Smoke-Test und Linting ausdruecklich geprueft statt nur angenommen

## Phasen-Abschluss-Review-Checkliste (1 Stunde)

- [ ] Wurden die Phasen-Ziele aus `PROJECT.md` tatsaechlich erreicht
- [ ] Welche Entscheidungen haben sich bewaehrt und welche brauchen Nachschaerfung
- [ ] Welche Architekturteile erzeugen unerwartete Komplexitaet
- [ ] Gibt es temporaere Legacy-Spalten oder Kompatibilitaetsfelder, die per Alembic bereinigt werden muessen
- [ ] Welche Fehler haben sich wiederholt und was fehlt als Prevention-Rule
- [ ] Welche Dokumente koennen gekuerzt, archiviert oder neu strukturiert werden
- [ ] Ist `CURRENT_STATE.md` sauber auf den Start der naechsten Phase ausgerichtet
