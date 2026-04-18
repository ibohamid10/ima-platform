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

## 2026-04-17 - Live-YouTube-Import liefert fuer grosse Kanaele frueh hohe Fraud-Risk-Scores
**Kategorie:** DB
**Symptom:** Der erste echte YouTube-Import gegen einen grossen Testkanal lief technisch sauber, wurde aber im heuristischen Scoring sofort als unqualifiziert mit hohem `fraud_risk_score` eingestuft.
**Root Cause:** Die aktuelle Fraud-Heuristik interpretiert ein niedriges View-zu-Subscriber-Verhaeltnis sehr streng. Bei sehr grossen, etablierten Kanaelen oder allgemein-populistischen Content-Profilen ist diese Regel fuer Phase 1 zu grob.
**Fix:** Noch kein Code-Fix in diesem Schritt. Das Ergebnis wurde als reales Kalibrierungssignal dokumentiert; Fraud- und Qualification-Heuristiken muessen vor breiterem Live-Harvesting mit echten Kanaelen nachgeschaerft werden.
**Prevention-Rule:** Neue Harvest-Quellen immer mindestens einmal gegen echte Live-Daten pruefen, bevor heuristische Scores als belastbar angenommen werden.

## 2026-04-17 - Windows-CLI braucht fuer Live-Evidence-Output ASCII-sichere JSON-Ausgabe
**Kategorie:** Testing
**Symptom:** `ima evidence build-creator` lief fachlich durch, scheiterte am Ende aber auf Windows mit `UnicodeEncodeError`, sobald echte Creator-Texte Sonderzeichen wie Pfeile enthielten.
**Root Cause:** Das lokale Terminal schrieb ueber eine `cp1252`-Konsole, waehrend der JSON-Output ungefilterte Unicode-Zeichen aus Live-YouTube-Captions enthielt.
**Fix:** Der CLI-Output fuer den Evidence-Builder wird jetzt ASCII-sicher serialisiert (`ensure_ascii=True`), waehrend die eigentlichen Artefakte unveraendert im Storage liegen.
**Prevention-Rule:** Neue CLI-Pfade immer mindestens einmal mit echten Live-Daten statt nur mit ASCII-lastigen Fixtures pruefen.

## 2026-04-17 - Hintergrund-Worker blockieren auf Windows spaetere `uv sync`- und Playwright-Installationen
**Kategorie:** Deployment
**Symptom:** Nach der Einfuehrung der Screenshot-Strecke scheiterten `uv sync --dev` und `uv run playwright install chromium`, obwohl die Konfiguration fachlich korrekt war.
**Root Cause:** Alte lokal gestartete Temporal-Worker liefen noch im Hintergrund und hielten `.venv\\Scripts\\ima.exe` geoeffnet. Dadurch konnte `uv` das Entry-Point-Binary nicht sauber aktualisieren.
**Fix:** Vor Dependency-Aenderungen oder Browser-Installationen wurden die hängenden `ima`, `python`- und `uv`-Prozesse explizit beendet. Danach liefen `uv sync --dev` und die Chromium-Installation sauber durch.
**Prevention-Rule:** Auf Windows vor jeder groesseren Environment-Aenderung zuerst pruefen, ob Hintergrund-Worker oder lang laufende CLI-Prozesse noch auf die lokale `.venv` zeigen.

## 2026-04-17 - Alembic-Revisions duerfen mit asyncpg keine Multi-Statement-SQL-Bloecke schicken
**Kategorie:** DB
**Symptom:** `alembic upgrade head` scheiterte gegen Postgres trotz syntaktisch korrekter SQL-Dateien mit `cannot insert multiple commands into a prepared statement`.
**Root Cause:** Mehrere Alembic-Revisionen haben mehrere SQL-Kommandos in einem einzigen `op.execute("""...; ...;""")` kombiniert. `asyncpg` akzeptiert das in vorbereiteten Statements nicht.
**Fix:** Jede Alembic-Revision fuehrt jetzt einzelne `CREATE`, `ALTER`, `UPDATE` und `CREATE INDEX`-Statements getrennt aus.
**Prevention-Rule:** In Alembic-Revisionen fuer Postgres/asyncpg nie mehrere SQL-Kommandos in einem `op.execute()`-Block kombinieren. Pro Statement genau ein `op.execute()` oder eine Alembic-Operation verwenden.

## 2026-04-17 - Migrationen im Smoke-Test nie direkt im laufenden Event-Loop ausfuehren
**Kategorie:** Testing
**Symptom:** Der aktualisierte Woche-2-Smoke-Test brach bei der Migration mit `asyncio.run() cannot be called from a running event loop` ab.
**Root Cause:** `scripts/smoke_test.py` lief selbst unter `asyncio.run(...)`, waehrend Alembics `env.py` online wiederum `asyncio.run(...)` fuer die Async-Engine nutzt.
**Fix:** Der Smoke-Test startet `scripts/db_migrate.py` jetzt via `await asyncio.to_thread(...)`, damit Alembic in einem separaten Thread ausserhalb des laufenden Event-Loops ausgefuehrt wird.
**Prevention-Rule:** Tools, die intern selbst `asyncio.run()` verwenden, nie direkt aus einem bereits laufenden Async-Loop heraus aufrufen; stattdessen in einen Thread oder Subprozess auslagern.

## 2026-04-17 - Fixed-point Score-Spalten duerfen in Migrationen nicht still auf Float driften
**Kategorie:** DB
**Symptom:** Ein frisch migriertes Postgres-Schema hatte fuer mehrere Score- und Confidence-Spalten `DOUBLE PRECISION`, waehrend ORM, Services und SQLite-Testschema dieselben Felder als `NUMERIC(...)/Decimal` behandelten. Zusaetzlich scheiterte die Rueckkonvertierung auf `NUMERIC(6,4)`, sobald Altwerte noch im alten `0..100`-Massstab vorlagen.
**Root Cause:** Eine Spec-Alignment-Revision hat die Typentscheidung fuer Fixed-Point-Spalten nicht an der ORM-Metadatenquelle ausgerichtet und den historischen Skalenwechsel von Prozentwerten zu `0..1`-Scores nicht explizit normalisiert.
**Fix:** Die betroffenen Alembic-Revisionen nutzen jetzt wieder `NUMERIC(6,4)` bzw. `NUMERIC(8,4)`, eine Reparatur-Revision normalisiert Altwerte > 1 auf den kanonischen `0..1`-Pfad, und der Smoke-Test vergleicht die kritischen Postgres-Spalten direkt mit den ORM-Metadaten.
**Prevention-Rule:** Bei scoring- oder threshold-relevanten Dezimalwerten nie implizit auf Float-Typen ausweichen; jede Typaenderung an persistierten Score-Spalten braucht einen Drift-Check gegen ORM-Metadaten und einen expliziten Plan fuer Altwerte im alten Zahlenmassstab.

## 2026-04-17 - Golden-Set-Fakes duerfen nie direkt aus dem Expected-Block antworten
**Kategorie:** Testing
**Symptom:** Die Golden-Set-Tests fuer Classifier und Evidence-Builder konnten per Konstruktion nicht fehlschlagen, weil die Fake-Provider ihre Antwort direkt aus denselben YAML-`expected`-Feldern synthetisiert haben, gegen die spaeter asserted wurde.
**Root Cause:** Plumbing-Fakes und Agent-Eval wurden in derselben Testschicht vermischt. Dadurch testete der Default-Pfad nur Executor-Verdrahtung, nicht Prompt, Contract oder agentisches Verhalten.
**Fix:** Die Executor-Plumbing bleibt in `tests/agents/test_executor.py` mit generischen Fakes. Die Golden-Set-Tests nutzen jetzt eigene input-basierte Heuristik-Provider, die `expected` nicht kennen, und asserten zusaetzlich auf Prompt-Snippets sowie das beabsichtigte Default-Modell.
**Prevention-Rule:** Golden-Set- oder Eval-Fakes duerfen niemals aus den erwarteten Zielwerten lesen. Wenn ein Test `expected`-Fixtures hat, muss die Testantwort ausschliesslich aus dem Input oder aus externen Live-Providern abgeleitet werden.

## 2026-04-18 - agent_runs muessen auch Preflight-Abbrueche vor dem Provider-Call auditieren
**Kategorie:** DB
**Symptom:** Budget-Exceeded und fehlende kompatible Provider brachen im `AgentExecutor` ab, ohne einen `agent_runs`-Eintrag zu schreiben, obwohl genau diese operativen Fehlerpfade fuer Budget- und Observability-Dashboards wichtig sind.
**Root Cause:** Budget-Check und Provider-Selektion liefen vor dem Session-Block, in dem der `AgentRun` angelegt wurde. Dadurch existierte fuer diese Fehler kein persistierter Audit-Trail.
**Fix:** `AgentExecutor.run()` legt den `AgentRun` jetzt vor den Preflight-Checks an, fuehrt Budget-Check und Provider-Selektion im selben Session-Kontext aus und markiert den Run bei fruehen Abbruechen mit `budget_exceeded` bzw. `provider_unavailable`. Eine Alembic-Revision erweitert die Postgres-Constraint entsprechend.
**Prevention-Rule:** Alles, was fachlich als Agent-Lauf gilt, muss zuerst den Audit-Record anlegen und erst danach vorzeitig scheitern duerfen. Preflight-Checks fuer Budget, Provider, Policy oder Guardrails gehoeren hinter den `agent_runs`-Pfad, nicht davor.

## 2026-04-18 - Budget-Hard-Gates brauchen Reservationen statt nur Summen bereits committeter Kosten
**Kategorie:** DB
**Symptom:** Der erste Budget-Fix schrieb zwar Audit-Eintraege fuer `budget_exceeded`, liess aber weiterhin zu, dass zwei parallele Agent-Runs dieselbe freie Budgetluecke sehen und beide gleichzeitig loslaufen.
**Root Cause:** Der Budget-Check summierte nur bereits committete `cost_usd`. Laufende Runs ohne persistierte Reservation waren fuer konkurrierende Sessions unsichtbar, bis sie ihren Provider-Call abgeschlossen hatten.
**Fix:** `agent_runs` hat jetzt `reserved_cost_usd`. Der `AgentExecutor` reserviert vor dem ersten Provider-Call pessimistisch Budget, zaehlt `cost_usd + reserved_cost_usd` im Hard-Gate zusammen, nutzt in Postgres ein transaktionales Advisory Lock fuer die Reservation und setzt die Reservation bei Erfolg oder Fehler wieder auf null.
**Prevention-Rule:** Budget-Caps fuer parallele Worker nie nur gegen bereits angefallene Kosten pruefen. Fuer jedes konkurrierende Budget-Gate braucht es eine persistierte Reservation oder ein explizites Locking-Schema in derselben DB-Transaktion.

## 2026-04-18 - HTTP-Fallbacks nie am Exception-String erkennen
**Kategorie:** Testing
**Symptom:** Der OpenAI-Adapter entschied den Fallback von Responses API auf Chat Completions darueber, ob im Exception-Text zufaellig `"400"` oder `"404"` vorkam.
**Root Cause:** Transportfehler wurden nur als formatierter String weitergereicht. Der Fallback hatte deshalb keine stabile, strukturierte Fehlerursache und konnte bei veraendertem Fehlertext oder falschen 400er-Ursachen still kippen.
**Fix:** `LLMProviderUnavailableError` traegt jetzt optional `status_code`. Die OpenAI-Fallback-Logik matched explizit auf `exc.status_code in {400, 404}`, und Tests decken jetzt sowohl den legitimen Fallback als auch den Nicht-Fallback bei 500ern ab.
**Prevention-Rule:** Feature-Fallbacks niemals ueber Stringsuche in Fehlermeldungen steuern. HTTP-nahe Fehler muessen strukturierte Metadaten wie `status_code` tragen, damit Aufrufer eindeutig und testbar entscheiden koennen.

## 2026-04-18 - Compose-Dateien duerfen keine lokalen Dev-Secrets als eingebaute Defaults ausliefern
**Kategorie:** Security
**Symptom:** `docker-compose.yml` enthielt lauffaehige Default-Credentials fuer ClickHouse, MinIO und Langfuse-S3 sowie einen kryptografisch wertlosen Nullschluessel fuer `LANGFUSE_ENCRYPTION_KEY`.
**Root Cause:** Die lokale Dev-Topologie hat Komfort-Defaults direkt in Compose konserviert, statt Secrets explizit aus `.env` zu beziehen und unsichere Beispielwerte nur fuer `IMA_ENV=local` zuzulassen.
**Fix:** Compose liest die betroffenen Secrets jetzt ausschliesslich ueber verpflichtende `${VAR:?...}`-Interpolation aus `.env`, `.env.example` dokumentiert die benoetigten lokalen Werte, und ein vorgeschalteter `langfuse-config-guard` blockiert jeden Nicht-`local`-Start mit dem dokumentierten Dev-Default fuer `LANGFUSE_ENCRYPTION_KEY`.
**Prevention-Rule:** In Compose-Dateien niemals einsatzfaehige Secrets oder kryptografische Default-Schluessel einkompilieren. Lokale Beispielwerte gehoeren nur in `.env.example`, und unsichere Dev-Defaults brauchen einen expliziten Environment-Guard fuer Nicht-Local-Setups.

## 2026-04-18 - Schema-Fehlertelemetrie darf Retry-Zahlen nie hartkodieren
**Kategorie:** Testing
**Symptom:** Der `schema_failed`-Pfad im `AgentExecutor` schrieb immer `validation_attempts = 2`, auch wenn die tatsaechliche Retry-Policy spaeter veraendert wuerde.
**Root Cause:** Der Fehlerpfad nutzte eine implizite Annahme ueber die aktuelle Retry-Strategie statt die echte Versuchszahl aus `_attempt_completion()` zu uebernehmen.
**Fix:** `_attempt_completion()` hebt finale Schema-Fehler jetzt als `LLMSchemaValidationAttemptsError` mit `attempts`-Attribut hoch. Der Executor persistiert diesen Wert direkt im `agent_runs`-Record, und ein Regressionstest deckt explizit den Fall mit simulierten drei Versuchen ab.
**Prevention-Rule:** Telemetrie-Zaehler fuer Retries, Fallbacks oder Policies nie als literale Konstanten in Fehlerpfade schreiben. Wenn ein Codepfad die reale Versuchszahl kennt, muss sie strukturiert im Exception- oder Result-Objekt weitergereicht werden.

## 2026-04-18 - Brand Spend Intent darf nie an einem einzelnen externen API-Zugang haengen
**Kategorie:** Deployment
**Symptom:** Der Woche-3-Brand-Pfad braucht `branded_content_score`, aber in lokalen und fruehen Staging-Setups fehlt oft `META_ACCESS_TOKEN`, waehrend API-Zugaenge, Reviews oder Limits ausserhalb des Kern-Repos liegen.
**Root Cause:** Spend-Intent war fachlich als Dreisignal-Score gedacht, aber technisch drohte ein einzelner externer Meta-Zugang das gesamte Signalset zu blockieren.
**Fix:** Der Meta-Ad-Library-Service ist best-effort und faellt ohne Token oder bei HTTP-Fehlern kontrolliert auf einen Such-basierten Fallback zurueck. Website- und Hiring-Signale bleiben davon unabhaengig, sodass `spend_intent_score` auch ohne Meta-Zugang berechenbar bleibt.
**Prevention-Rule:** Operativ wichtige Scores nie an genau eine optionale Drittanbieter-Integration ketten. Wenn ein externes Signal fehlt, braucht es einen klaren Fallback oder eine degradierte, aber weiter lauffaehige Berechnung.
