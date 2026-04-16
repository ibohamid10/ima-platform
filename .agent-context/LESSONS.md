# Lessons Learned

Dieses Dokument ist append-only. Es sammelt Fehler, Beinahe-Fehler und teure Umwege so, dass spaetere Sessions dieselben Probleme nicht wiederholen.

## Format

Jeder Eintrag nutzt dieses Schema:

```text
## YYYY-MM-DD - Kurzer Titel
**Kategorie:** Scraping | LLM | Email | DB | Testing | Deployment | Security | UI
**Symptom:** ...
**Root Cause:** ...
**Fix:** ...
**Prevention-Rule:** ...
```

## 2026-04-16 - Beispiel: Unbelegte Personalisierung im Outreach-Draft
**Kategorie:** LLM
**Symptom:** Ein Mail-Draft klang plausibel, enthielt aber eine konkrete Behauptung ueber eine Creator-Kampagne ohne belastbare Quelle.
**Root Cause:** Personalisierungslogik hat Textfragmente aus Research uebernommen, ohne fuer jede Aussage eine verbindliche `evidence_id` zu erzwingen.
**Fix:** Validator und Pre-Send-Check muessen jede faktische Behauptung auf `evidence_items` zurueckfuehren und Drafts ohne vollstaendige Evidence-Coverage blockieren.
**Prevention-Rule:** Keine Personalisierungs-Pipeline ohne harten Evidence-Gate. "Klingt plausibel" ist nie ausreichend.
