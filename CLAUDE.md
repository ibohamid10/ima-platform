# Projekt-Bootstrap fuer Agenten

Dieses Repo baut eine weitgehend automatisierte Influencer Marketing Agency als interne Pipeline fuer einen Solo-Owner. Es ist kein oeffentliches Produkt und keine Kundenseite; die einzige eigens gebaute UI ist eine minimale Review-UI fuer den Operator. Der Schwerpunkt liegt auf Discovery, Matching, evidenzbasiertem Outreach, Reply-Handling und klaren Human Gates.

## Bootstrap-Anweisung

Lies **vor jeder Aufgabe** folgende Dateien in dieser Reihenfolge:

1. `.agent-context/PROJECT.md`
2. `.agent-context/ARCHITECTURE.md`
3. `.agent-context/CURRENT_STATE.md`
4. `.agent-context/CONVENTIONS.md`
5. Die letzten 10 Eintraege in `.agent-context/DECISIONS.md`
6. Die letzten 5 Eintraege in `.agent-context/LESSONS.md`
7. `.agent-context/OPEN_QUESTIONS.md`

Danach:

- Bestaetige kurz, dass du den Kontext geladen hast
- Fasse in 3 Saetzen zusammen, wo das Projekt gerade steht
- Arbeite erst dann an der eigentlichen Aufgabe

Am Session-Ende: `.agent-context/SESSION_CHECKLIST.md` durchgehen.

## Session-Opener-Prompt-Template fuer Codex oder andere Agents

```text
Du arbeitest in einem Repo fuer eine interne Influencer-Marketing-Pipeline mit Operator-UI, nicht fuer ein oeffentliches Produkt.

Bitte fuehre vor der eigentlichen Aufgabe zuerst diesen Bootstrap aus:
1. Lies `.agent-context/PROJECT.md`
2. Lies `.agent-context/ARCHITECTURE.md`
3. Lies `.agent-context/CURRENT_STATE.md`
4. Lies `.agent-context/CONVENTIONS.md`
5. Lies die letzten 10 Eintraege in `.agent-context/DECISIONS.md`
6. Lies die letzten 5 Eintraege in `.agent-context/LESSONS.md`
7. Lies `.agent-context/OPEN_QUESTIONS.md`

Bestaetige danach in 3 Saetzen:
- was gebaut wird,
- in welcher Phase das Projekt steht,
- was die naechsten konkreten Schritte sind.

Arbeite erst danach an meiner eigentlichen Aufgabe und gehe am Session-Ende `.agent-context/SESSION_CHECKLIST.md` durch.
```
