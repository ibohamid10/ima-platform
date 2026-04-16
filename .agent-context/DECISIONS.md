# Entscheidungen

Dieses Dokument ist append-only. Neue Entscheidungen werden unten angefuegt. Bestehende Eintraege werden nicht rueckwirkend ueberschrieben, sondern bei Bedarf durch neue Entscheidungen praezisiert.

## 2026-04-16 - Keine Agent-SDKs
**Kontext:** Das Projekt braucht agentische Rollen und Orchestrierung, aber bereits mit Temporal als Workflow-Layer. Mehrere moegliche Agent-SDKs oder Multi-Agent-Frameworks stehen am Markt zur Verfuegung.
**Entscheidung:** In Phase 1 werden keine Agent-SDKs und keine Multi-Agent-Frameworks wie Anthropic Agent SDK, LangGraph, CrewAI oder Autogen eingesetzt.
**Begruendung:** Temporal ist bereits der Orchestrierungs-Layer. Zusaetzliche Agent-Orchestrierung wuerde Double-Orchestration erzeugen, das Debugging erschweren und die Model-Swap-Regel untergraben.
**Verworfene Alternativen:** Anthropic Agent SDK, LangGraph, CrewAI, Autogen

## 2026-04-16 - Temporal als Workflow-Engine
**Kontext:** Das System braucht robuste Orchestrierung fuer lange laufende, retry-faehige Hintergrundprozesse mit Human Gates und nachvollziehbarem Zustand.
**Entscheidung:** Temporal ist die Workflow-Engine fuer Phase 1 und der angestrebte produktive Orchestrierungs-Layer, nicht nur ein Uebergangswerkzeug.
**Begruendung:** Temporal passt zu langlebigen Workflows, Activity-Retries, observierbarem Zustand und klarer Trennung von Orchestrierung und Fachlogik.
**Verworfene Alternativen:** n8n als Endzustand, lose Cron-Skripte, ad-hoc Queue-Orchestrierung

## 2026-04-16 - Eigene duenne Abstraktion
**Kontext:** Das System braucht austauschbare LLM- und Mail-Integrationen und klar definierte Agent-Rollen ohne schweres Framework.
**Entscheidung:** Die Kernlogik wird ueber vier eigene duenne Abstraktionen gebaut: `LLMProvider`, `MailProvider`, `AgentContract` und `AgentExecutor`.
**Begruendung:** Eine schlanke eigene Schicht von etwa 500 bis 700 LOC ist leichter zu debuggen, besser auf das Projekt zugeschnitten und vermeidet Vendor- oder Framework-Lock-in.
**Verworfene Alternativen:** Framework-zentrierter Ansatz, direkte Vendor-API-Aufrufe im Fachcode

## 2026-04-16 - Opus fuer Copywriter nur als Hypothese
**Kontext:** Der Copywriter profitiert moeglicherweise von einem staerkeren Modell, aber die Mehrkosten muessen sich in Ergebnissen zeigen.
**Entscheidung:** Claude Opus 4.6 ist fuer den Copywriter nur der initiale A/B-Kandidat. Ein Vergleich gegen GPT-5.4 nach mindestens 200 echten Sends ist Pflicht, bevor ein finales Modell festgelegt wird.
**Begruendung:** Modellwahl soll eval-driven erfolgen statt vendor- oder prestigegetrieben.
**Verworfene Alternativen:** Opus dauerhaft per Bauchgefuehl festschreiben, Modellwahl ohne echte Send-Daten treffen

## 2026-04-16 - Discovery API-first
**Kontext:** Discovery kann ueber offizielle APIs, oeffentliche Signale oder fragiles Scraping erfolgen.
**Entscheidung:** Discovery folgt einer Hierarchie: zuerst APIs, dann offizielle oeffentliche Signale, Scraping nur als Gap-Filler.
**Begruendung:** API-first ist stabiler, rechtlich und operativ sauberer und reduziert Wartungsaufwand. Scraping bleibt nur dort, wo echte Datenluecken bestehen.
**Verworfene Alternativen:** Scraping-first, gleichgewichtige Behandlung aller Quellen

## 2026-04-16 - TikTok als Plattformrisiko behandeln
**Kontext:** TikTok kann wertvolle Daten liefern, ist aber plattform- und zugriffsseitig riskanter als andere Quellen.
**Entscheidung:** TikTok wird als plattformrisiko-behaftete Saeule behandelt. Die Architektur muss ohne TikTok voll funktionsfaehig bleiben.
**Begruendung:** Das Projekt darf nicht von einer einzelnen fragilen Quelle abhaengen.
**Verworfene Alternativen:** TikTok als Pflichtpfeiler der Discovery-Architektur, TikTok-zentrierte Datenmodelle

## 2026-04-16 - DMARC-Eskalation datenbasiert
**Kontext:** Die Sending-Infrastruktur muss Reputation schuetzen und DMARC sinnvoll schaerfen.
**Entscheidung:** DMARC startet mit `p=quarantine` und wird erst datenbasiert auf `p=reject` erhoeht.
**Begruendung:** Reputation und Zustellbarkeit muessen ueber echte Reports, SPF- und DKIM-Pass-Raten, Bounce- und Spam-Raten abgesichert werden statt ueber starre Zeitplaene.
**Verworfene Alternativen:** Zeitbasierte DMARC-Eskalation, sofortiges `p=reject`

## 2026-04-16 - Open Rate ist keine Kern-KPI
**Kontext:** Viele Outreach-Systeme optimieren auf Open Rates, nutzen dafuer aber Tracking-Pixel.
**Entscheidung:** Open Rate ist keine Kern-KPI dieses Systems.
**Begruendung:** Das System verzichtet bewusst auf Tracking-Pixel. Kernmetriken sollen robust und operational aussagekraeftig sein.
**Verworfene Alternativen:** Open Rate als zentrale Steuerungsmetrik, Pixel-basiertes Default-Tracking

## 2026-04-16 - Human-Approval fuer alle Outbound-Mails in Phase 1
**Kontext:** Outbound erzeugt direkten Aussenkontakt und damit Risiko bei Copy, Promise, Timing und Reputation.
**Entscheidung:** Alle Outbound-Mails in Phase 1 brauchen Human-Approval vor dem Versand.
**Begruendung:** Phase 1 ist lern- und kalibrierungsgetrieben. Der Operator bleibt bei jedem Outbound der letzte Gatekeeper.
**Verworfene Alternativen:** Auto-Sending fuer Erstmails, teilautomatische Freigabe ohne echte Policy-Matrix

## 2026-04-16 - Evidence-Coverage 100 Prozent als Hard Gate
**Kontext:** Personalisierte Outreach-Mails verlieren schnell Glaubwuerdigkeit, wenn faktische Behauptungen unbelegt sind.
**Entscheidung:** Jede faktische Behauptung in einer Mail braucht eine `evidence_id`. Ohne vollstaendige Evidence-Coverage kein Send.
**Begruendung:** Das ist der wirksamste Schutz gegen Halluzinationen, schlechte Personalisierung und vermeidbare Vertrauensbrueche.
**Verworfene Alternativen:** Teilweise Evidence-Coverage, Stichproben-Pruefung statt Hard Gate

## 2026-04-16 - Keine oeffentliche Website in Phase 1
**Kontext:** Es gibt einen UI-Bedarf, aber die Versuchung ist gross, zu frueh in Produkt- oder Marketing-Oberflaechen zu investieren.
**Entscheidung:** In Phase 1 wird keine oeffentliche Website gebaut. Die einzige eigene UI ist eine Operator-Only Review-UI. Next.js ist der empfohlene Stack, die finale UI-Framework-Entscheidung faellt spaetestens Ende Woche 3.
**Begruendung:** Das Projekt ist eine interne Pipeline. Phase-1-Wert entsteht durch funktionierende Discovery-, Matching- und Outreach-Prozesse, nicht durch eine oeffentliche Flaeche.
**Verworfene Alternativen:** Oeffentliche Landingpage in Phase 1, sofortige Festlegung ohne Review bis Ende Woche 3, Customer-Portal

## 2026-04-16 - MailProvider als zweiter Adapter-Layer
**Kontext:** Neben `LLMProvider` gibt es Bedarf, Sending-Vendor wie Instantly, Smartlead und spaeter SMTP austauschbar zu halten.
**Entscheidung:** Es gibt einen eigenen `MailProvider`-Adapter parallel zu `LLMProvider`; beide gehoeren in das Woche-1-Fundament.
**Begruendung:** Das verhindert Vendor-Lock-in auf Sending-Seite und erlaubt spaetere Wechsel ohne Workflow-Refactor.
**Verworfene Alternativen:** Direkte Instantly-SDK-Calls im Fachcode, Sending-Logik nur in Temporal-Activities ohne Abstraktion

## 2026-04-16 - Suppression als fuenf getrennte Tabellen
**Kontext:** Suppression kann als einzelne Liste oder nach Grund getrennt modelliert werden.
**Entscheidung:** Es werden fuenf getrennte Tabellen genutzt (`unsubscribe`, `hard_bounce`, `spam_complaint`, `wrong_person`, `manual`) statt einer einzigen `suppression_list`.
**Begruendung:** Unterschiedliche Gruende brauchen unterschiedliche Workflows. Spam Complaint ist kritischer als Wrong Person. Zusaetzlich verbessert die Trennung Audit-Trails, DSGVO-Nachweisbarkeit und eine differenzierbare No-Reimport-Policy pro Grund.
**Verworfene Alternativen:** Einzelne `suppression_list` mit `reason`-Spalte

## 2026-04-16 - Growth-Bewertung ueber Snapshots statt Punktwert-Overwrite
**Kontext:** Creator-Growth soll explizit ueber Trajectory statt ueber eine einzelne absolute Follower-Zahl bewertet werden. Dafuer braucht das System historische Metriken, die spaeter durch Harvester und Enricher inkrementell fortgeschrieben werden koennen.
**Entscheidung:** Growth wird ueber eine eigene Tabelle `creator_metric_snapshots` modelliert. Der erste Week-2-Scoring-Pfad liest mehrere Snapshots und berechnet daraus `growth_score`, statt nur den aktuellen `follower_count` in `creators` zu interpretieren.
**Begruendung:** Das passt zur Architekturregel "Trajectory nicht Absolutzahl", ermoeglicht spaetere Re-Scorings ohne Datenverlust und entkoppelt Rohmetriken von abgeleiteten Scores.
**Verworfene Alternativen:** Growth nur als direkt ueberschriebener Wert in `creators`, Follower-Deltas ohne historischen Snapshot-Verlauf, reine Absolutzahl ohne Verlauf
