# Classifier Golden Set

Dieses Golden Set ist die Referenz fuer Regressions-Checks beim `classifier`. Jeder Fall beschreibt verifizierte Input-Merkmale und minimale Erwartungen an Nische, Sprache und Brand-Safety.

## Wie neue Cases hinzugefuegt werden

- Nur kuratierte, nachvollziehbare Beispiele aufnehmen
- `input` moeglichst realistisch und knapp halten
- `expected.niche` und `expected.language` nur setzen, wenn sie stabil beurteilbar sind
- `expected.brand_safety_score_min` konservativ formulieren

## Warum das wichtig ist

Golden Sets dienen als Merge-Gate fuer LLM-basierte Agenten und als Regressions-Check fuer Model-Swaps. Wenn ein Modellwechsel hier schlechter wird, ist die Entscheidung noch nicht produktionsreif.
