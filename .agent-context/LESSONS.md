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

## 2026-04-16 - Langfuse lokal braucht Windows-sichere ClickHouse- und Init-Konfiguration
**Kategorie:** Deployment
**Symptom:** `docker compose up` startete Postgres, Redis, Temporal und Qdrant, aber Langfuse blieb in einer Restart-Schleife oder akzeptierte keine SDK-Keys.
**Root Cause:** ClickHouse-Migrationen scheiterten auf Windows-Bind-Mounts bei `rename`, Redis lief ohne zum Langfuse-Default passende Auth-Konfiguration, und Langfuse ignorierte `LANGFUSE_INIT_*`-Werte solange `LANGFUSE_INIT_ORG_ID` und `LANGFUSE_INIT_PROJECT_ID` fehlten.
**Fix:** ClickHouse fuer Langfuse auf Docker-Volumes statt NTFS-Bind-Mounts umstellen, Redis mit explizitem Passwort und `noeviction` starten, `REDIS_CONNECTION_STRING` setzen und sowohl `LANGFUSE_INIT_ORG_ID` als auch `LANGFUSE_INIT_PROJECT_ID` in der lokalen Dev-Konfiguration hinterlegen.
**Prevention-Rule:** Bei self-hosted Langfuse immer die offizielle Compose-Topologie als Referenz nehmen; auf Windows keine ClickHouse-Bind-Mounts fuer produktive Migrationstests verwenden und Init-IDs nie auslassen.
