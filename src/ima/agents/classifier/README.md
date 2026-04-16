# Classifier Agent

## Zweck

Der `classifier` klassifiziert ein Creator-Profil nach Hauptnische, Sub-Nischen, Sprache und grober Brand-Safety. Er dient in Woche 1 als Referenz-Implementation fuer alle spaeteren LLM-basierten Agenten.

## Input/Output-Contract

Der formale Contract lebt in [contract.py](/Users/hamidibr/Desktop/test/ima-platform/src/ima/agents/classifier/contract.py). `ClassifierInput` nimmt Profil-Snippets an, `ClassifierOutput` liefert strukturierte Klassifikation zurueck.

## Modell-Wahl

Default ist Claude Haiku 4.5 mit Fallback auf GPT-5.4-nano. Die Begruendung ist pragmatisch: Haiku ist fuer strukturierte Klassifikation schnell und guenstig genug, und `model_preference` erlaubt spaeteren Model-Swap ohne Code-Aenderung.

## Bekannte Edge-Cases

- Mehrsprachige Profile mit wechselnder Caption-Sprache
- Sehr kurze Bios ohne Kontext
- Emoji-only Captions oder Hashtags ohne semantischen Inhalt

## Test-Befehl

```bash
pytest tests/agents/test_classifier_golden_set.py
```

## Abhaengigkeiten

Keine externen Tools. Der Agent verarbeitet nur Input-Daten und ruft das LLM ueber `LLMProvider`.
