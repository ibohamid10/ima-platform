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

## 2026-04-16 - Async ORM im Growth-Scoring nicht auf Lazy-Relations verlassen
**Kategorie:** DB
**Symptom:** Die neuen Creator-Scoring-Tests schlugen mit `MissingGreenlet` fehl, obwohl die Daten im selben Async-Session-Kontext bereits geschrieben waren.
**Root Cause:** `session.get()` lieferte im Async-Kontext das bereits bekannte `Creator`-Objekt zurueck, ohne die Relationen frisch zu laden. Der Zugriff auf `creator.metric_snapshots` und `creator.content_items` loeste danach unerwartetes Lazy-Loading aus.
**Fix:** Growth-Scoring laedt Snapshots und Content jetzt explizit per `select(...)` statt sich auf ORM-Lazy-Relations zu verlassen.
**Prevention-Rule:** In Async-SQLAlchemy fuer Service-Logik keine impliziten Relation-Loads einplanen; benoetigte Daten immer explizit in derselben Methode holen.

## 2026-04-16 - CLI-Zeitstempel fuer historische Snapshots selbst als ISO-8601 parsen
**Kategorie:** Testing
**Symptom:** `ima creators record-snapshot --captured-at 2026-03-15T10:00:00+00:00` wurde von der CLI abgelehnt, obwohl der Wert fachlich korrekt war.
**Root Cause:** Typer akzeptierte fuer `datetime`-Optionen im Default-Parsing nur ein eingeschraenktes Formatset ohne Offset-Variante.
**Fix:** `--captured-at` wird jetzt als String entgegengenommen und bewusst via `datetime.fromisoformat()` in UTC-normalisierte Werte geparst.
**Prevention-Rule:** Fuer operator-facing CLI-Eingaben mit Zeitbezug kein implizites Framework-Parsing voraussetzen; akzeptierte Formate explizit kontrollieren und testen.
