# Evidence Builder Golden Set

Dieses Golden Set prueft, ob der Evidence-Builder aus verdichtetem Creator-Kontext belastbare Evidence-Items mit `source_uri` und `confidence` erzeugt.

## Wie neue Cases hinzugefuegt werden

- Nur verifizierbare Claims aufnehmen
- `source_uri` muessen zu den im Input vorhandenen Quellen passen
- Mehrdeutige Faelle bewusst mit niedrigerer `min_confidence` modellieren
- Die erwartete Item-Anzahl konservativ halten, damit das Golden Set stabil bleibt

## Warum das wichtig ist

Der Evidence-Builder ist ein Merge-Gate fuer spaetere Matching- und Outreach-Schritte. Wenn ein Modell hier schlechter wird, sinkt die spaetere Evidence-Coverage-Qualitaet direkt mit.
