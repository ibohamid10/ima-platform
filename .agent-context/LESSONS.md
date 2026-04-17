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

## 2026-04-16 - UUID-Vergleiche in Tests nie implizit als Strings behandeln
**Kategorie:** DB
**Symptom:** Der neue Creator-Ingest-Pfad lief gegen Postgres lokal, scheiterte aber in den SQLite-basierten Unit-Tests mit `AttributeError: 'str' object has no attribute 'hex'`.
**Root Cause:** Beim Content-Upsert wurde `creator_id` als String durchgereicht, obwohl die ORM-Spalte als UUID typisiert ist. Postgres war tolerant genug, SQLite nicht.
**Fix:** Die Ingest-Logik nutzt fuer UUID-vergleichende Queries jetzt durchgehend echte `UUID`-Objekte.
**Prevention-Rule:** Bei Cross-DB-Tests keine stillschweigende String-zu-UUID-Konvertierung erwarten; typisierte IDs im Python-Code immer im nativen Typ halten.

## 2026-04-16 - Temporal-Workflow-Sandbox darf keine ORM-lastigen Service-Module importieren
**Kategorie:** Deployment
**Symptom:** Der erste lokale Temporal-Worker startete nicht und brach schon bei der Workflow-Validierung mit `TypeError: __annotations__ must be set to a dict object` ab.
**Root Cause:** Das Workflow-Modul importierte `CreatorIngestInput` aus einem Service-Modul, das transitiv SQLAlchemy-Modelle nachlud. In der Temporal-Sandbox kollidierte dieser Importpfad mit SQLAlchemys Wrapper-Logik.
**Fix:** Workflow-Contracts wurden in `src/ima/creators/schemas.py` als sandbox-sichere Pydantic-Typen ausgegliedert. Workflows importieren nur noch diese Contracts und delegieren alle DB-Arbeit an Activities.
**Prevention-Rule:** Temporal-Workflow-Module duerfen nur deterministische, importarme Contracts und Konstanten sehen. ORM-, Provider- und Session-Code gehoert ausschliesslich in Activities oder Services ausserhalb der Sandbox.
