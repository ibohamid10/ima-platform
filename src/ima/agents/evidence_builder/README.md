# Evidence Builder Agent

## Zweck

Der Evidence-Builder erzeugt strukturierte `evidence_items` aus Bio, Metriken und aktuellem Creator-Content. Jedes Item muss eine konkrete `source_uri` und eine `confidence` enthalten.

## Input/Output-Contract

Der Contract lebt in [contract.py](/Users/hamidibr/Desktop/test/ima-platform/src/ima/agents/evidence_builder/contract.py). Input ist ein verdichteter Creator-Kontext, Output ist eine Liste von Evidence-Items mit `claim_text`, `source_uri`, `source_type` und `confidence`.

## Modell-Wahl

Default ist `claude-sonnet-4-6` mit Fallback auf `gpt-5.4`, weil Evidence-Building strukturierte Reasoning-Arbeit ist. Das ist teurer als reine Klassifikation, aber deutlich naeher an spaeterer Match- und Outreach-Qualitaet.

## Bekannte Edge-Cases

- Sehr wenig Content: wenige Items und konservative Confidence
- Mehrdeutige Captions: nur vorsichtige Claims
- Viele Links oder Copy-lastige Beschreibungen: Claims nur aus nachweisbaren Fakten ableiten
- Wiederholter Content: Duplikate moeglich, deshalb Persistenz spaeter ueber stabile Keys deduplizieren

## Test-Befehl

```bash
pytest tests/agents/test_evidence_builder_golden_set.py
```

## Abhaengigkeiten

- Keine Tool-Use-Abhaengigkeiten im Contract selbst
- Nutzt die vorbereitete Creator-/Content-/Metrik-Sicht aus dem Evidence-Builder-Service
