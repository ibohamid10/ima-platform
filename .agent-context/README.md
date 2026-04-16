# .agent-context System

`.agent-context/` ist das persistente Projekt-Memory fuer dieses Repo. Es ergaenzt Git-Historie und Code durch verdichteten Kontext: Was gebaut wird, warum es gebaut wird, wie das System gedacht ist, welche Entscheidungen bereits getroffen wurden, welche Fehler schon passiert sind und was als Naechstes ansteht.

## Ziel des Systems

Das Ziel ist, dass jede neue Agent-Session in wenigen Minuten arbeitsfaehig wird, ohne Annahmen neu zu erfinden oder alte Diskussionen wiederholen zu muessen. Das gilt fuer Coding-Agents wie Claude Code oder Codex genauso wie fuer den Projekt-Owner.

## Bootstrap-Pattern

Das System folgt einem einfachen Bootstrap-Pattern:

1. `PROJECT.md` liefert den Nordstern.
2. `ARCHITECTURE.md` beschreibt die Struktur-Wahrheit.
3. `CURRENT_STATE.md` sagt, wo das Projekt heute steht.
4. `CONVENTIONS.md` definiert, wie implementiert wird.
5. `DECISIONS.md` und `LESSONS.md` verhindern, dass bekannte Abzweigungen und Fehler vergessen werden.
6. `OPEN_QUESTIONS.md` macht Unsicherheit explizit statt implizit.

`CLAUDE.md` im Repo-Root ist der Bootstrap-Pointer fuer Agenten, die beim Start nur eine einzelne Datei laden.

## Erwartete Disziplin

Dieses System funktioniert nur, wenn jede Session den Kontext nicht nur konsumiert, sondern auch pflegt.

### Session-Ende-Ritual

Am Ende jeder Arbeits-Session wird `SESSION_CHECKLIST.md` durchgegangen. Mindestens `CURRENT_STATE.md` wird aktualisiert. Neue Entscheidungen wandern nach `DECISIONS.md`. Relevante Fehler und Learnings wandern nach `LESSONS.md`. Neue Unsicherheiten werden in `OPEN_QUESTIONS.md` sichtbar gemacht.

### Wochen-Review

Einmal pro Woche wird der Kontext in 15 Minuten auf Konsistenz geprueft:

- Ist `CURRENT_STATE.md` noch aktuell
- Sind offene Fragen noch relevant
- Haben sich Architekturannahmen geaendert
- Fehlen Entscheidungen oder Learnings aus den letzten Sessions

### Phasen-Abschluss-Review

Am Ende jeder Projektphase gibt es ein laengeres Review:

- Welche Ziele wurden erreicht
- Welche Teile der Architektur haben sich bewaehrt
- Welche Regeln brauchen Schaerfung
- Welche Dokumente koennen archiviert oder verdichtet werden

Abgeschlossene, nicht mehr bootstrap-relevante Details koennen in `.agent-context/archive/` verschoben werden, damit das aktive Memory schlank bleibt.

## Schreibprinzipien

- Deutsch fuer Prozess- und Erklaerungstexte
- Technische Begriffe, Code-Namen und Feldnamen in ihrer Originalform
- Kurz genug fuer regelmaessiges Lesen
- Praezise genug, dass ein neuer Agent sofort handlungsfaehig wird
- Keine impliziten Annahmen, wenn sie fuer Architektur oder Scope relevant sind

## Wer diese Dateien lesen sollte

- Coding-Agents vor jeder inhaltlichen Aufgabe
- Der Solo-Owner vor Priorisierungs- oder Architekturentscheidungen
- Jeder, der wissen muss, was Phase 1 bewusst nicht ist
