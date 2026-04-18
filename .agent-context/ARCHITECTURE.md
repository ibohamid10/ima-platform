# Architektur

## Architektur-Zielbild

Das System ist eine interne, workflow-getriebene Outreach-Pipeline mit einem kleinen Operator-Frontend. Der Schwerpunkt liegt auf reproduzierbarer Automatisierung, klaren Human Gates und austauschbaren Integrationen statt auf einem oeffentlichen Produkt oder einem Agent-Framework.

## Stack-Komponenten mit Begruendung

| Komponente | Wahl | Begruendung |
|---|---|---|
| Workflow-Orchestrierung | Temporal self-hosted via Docker | Lange laufende, retry-faehige, beobachtbare Workflows mit Activities statt ad-hoc Cron-Skripten |
| Primarer State | Postgres | Relationaler Kern fuer Entities, Matches, Outreach, Suppression und `agent_runs` |
| Cache / Locks | Redis | Schnelle Caches, Deduping, Locks und Queue-nahe Kurzzeitzustaende |
| Embeddings | Qdrant | Vektorstore fuer Matching, Aehnlichkeit und Retrieval-Aufgaben |
| Object Storage | R2 oder S3 | Persistenz fuer Artefakte wie Media-Kits, Screenshots oder Rohdaten |
| LLMs | Anthropic + OpenAI ueber Adapter | Modellwahl pro Rolle und spaeteres Swapping ohne Vendor-Lock |
| Scraping / Data | APIs, Apify, Playwright | API-first, oeffentliche Signale zweitens, Scraping nur als Gap-Filler |
| Sending | Instantly oder Smartlead + Google Workspace | Versand ueber spezialisierte Infrastruktur statt Eigenbau-SMTP in Phase 1 |
| Review-UI | Next.js 15 + Tailwind + shadcn/ui | Schnelles Operator-Frontend mit pragmatischem App-Router-Stack |
| Observability | Langfuse, Temporal UI, Metabase oder Grafana | Traces, Workflow-Debugging und KPI-Sichtbarkeit |
| Deployment | Lokal Docker Compose, live Hetzner VPS | Schneller Start lokal, einfacher Betrieb in Phase 1 |

## System-Komponenten und Zusammenspiel

```text
                +-------------------------------+
                |        Review-UI (Owner)      |
                | Next.js /approvals /replies   |
                | /matches /creators /brands    |
                +---------------+---------------+
                                |
                                v
+-------------------------------+-------------------------------+
|                   Backend-Pipeline (headless)                |
| Temporal Workflows -> Activities -> AgentExecutor -> Storage |
| Postgres | Redis | Qdrant | R2/S3 | Langfuse hooks           |
+-------------------+--------------------+---------------------+
                    |                    |
                    v                    v
       +------------+---------+   +------+------------------+
       | Sending-Infrastruktur |   | Externe Observability |
       | Instantly/Smartlead   |   | Langfuse / Temporal UI|
       | Sending-Domains       |   | Metabase oder Grafana |
       | Google Workspace      |   +-----------------------+
       +-----------------------+
```

Die Backend-Pipeline ist der Kern. Sie sammelt Daten, scoret, matcht, erzeugt Evidence Packs und Drafts und schreibt den Zustand in Postgres. Das Review-UI liest und steuert diese Zustaende fuer den Solo-Owner. Die Sending-Infrastruktur setzt genehmigte Mails um. Externe Observability-Tools helfen beim Debugging und bei Metriken, ersetzen aber nicht die Operator-UI.

## Die vier eigenen Abstraktionen

### `LLMProvider`

Generisches Interface fuer Modellaufrufe. Es kapselt Anbieter-spezifische APIs und erlaubt Model-Swap per Config. Direkte Vendor-Calls im Fachcode sind verboten.

### `MailProvider`

Adapter-Layer fuer Sending-Provider wie Instantly oder Smartlead. Er trennt Business-Logik von Provider-spezifischen APIs und haelt einen spaeteren SMTP-Adapter offen.

### `AgentContract`

Versionierte Pydantic-Rollen-Definition mit Input-Schema, Output-Schema, System-Prompt-Template auf Jinja2-Basis, Model-Preference mit Fallback, optionalen Tools und optionalen Few-Shots.

### `AgentExecutor`

Runner fuer Agent-Aufrufe. Er rendert Prompts, ruft LLMs ueber `LLMProvider` auf, validiert Outputs gegen das Schema, retried bei Schema-Failures und loggt in Langfuse sowie in `agent_runs`.

Temporal-Activities wrappen `AgentExecutor`-Calls. Workflows orchestrieren mehrere Activities und damit Agent-Ketten.

## Agent-Rollen

| # | Agent | Typ | Default-Modell |
|---|---|---|---|
| 1 | Harvester | Python + APIs/Apify | Kein LLM |
| 2 | Enricher | Python + APIs | Kein LLM |
| 3 | Growth-Tracker | Python/SQL | Kein LLM |
| 4 | Classifier | LLM-Call | Claude Haiku 4.5 |
| 5 | Sponsorship-Detector | LLM + Vision | Claude Haiku 4.5 |
| 6 | Brand-Intent-Agent | Python + LLM | Claude Haiku 4.5 |
| 7 | Matcher | LLM Reasoning | Claude Sonnet 4.6 |
| 8 | Evidence-Builder | LLM + Tools | Claude Sonnet 4.6 |
| 9 | Angle-Selector | LLM | Claude Sonnet 4.6 |
| 10 | Copywriter | LLM + Few-Shots | Claude Opus 4.6 als Hypothese |
| 11 | Validator | LLM + Regeln | Claude Haiku 4.5 |
| 12 | Reply-Handler | LLM | Claude Sonnet 4.6 |

Ein Negotiation-Assistant gehoert bewusst nicht zu Phase 1.

## Kern-Datenmodell

| Tabelle | Zweck |
|---|---|
| `creators` | Stammdaten, Nische, Consent-Basis, Scores und Status qualifizierter Creator |
| `creator_niche_scores` | Per-Nische-Fit-Breakdown fuer denselben Creator ueber mehrere Nischen hinweg |
| `creator_content` | Inhalte, Signals und Rohdatenpunkte fuer Growth, Sponsorship-Erkennung und Evidence |
| `brands` | Stammdaten, Spend-Intent-Signale, Kontakt- und Consent-Basis der Brands |
| `brand_creator_matches` | Ergebnis der Matching-Logik mit Match-Score, Begruendung und Status |
| `evidence_items` | Einzelne belegbare Fakten fuer Creator oder Brands mit `evidence_id` als Grundlage fuer Evidence-Coverage |
| `outreach_threads` | Thread-Zustand fuer Erstmail, Sequenz, Replies, Approval und Status |
| `agent_runs` | Non-negotiable Audit-Tabelle fuer Modell, Kosten, Laufzeit, Version und Validierungsergebnis |
| `suppression_unsubscribe` | Permanente Unterdrueckung nach Abmeldung |
| `suppression_hard_bounce` | Permanente Unterdrueckung nach Hard Bounce |
| `suppression_spam_complaint` | Permanente Unterdrueckung nach Spam Complaint |
| `suppression_wrong_person` | Permanente Unterdrueckung fuer falsche Ansprechpartner |
| `suppression_manual` | Manuelle Unterdrueckung durch den Operator |

## Discovery-Hierarchie

### Tier 1: API-first

- YouTube Data API
- Meta Graph API und Meta Ad Library

### Tier 2: Offizielle oeffentliche Signale

- Brand-Websites
- Creator-Websites
- Media-Kits
- Press
- Newsletter
- Affiliate-Pages

### Tier 3: Scraping als Gap-Filler

- Instagram via Apify
- TikTok via Apify

TikTok ist explizit als plattformrisiko-behaftete Saeule markiert. Die Architektur muss ohne TikTok weiterlaufen koennen.

## Nischen-System

Nischen werden nicht mehr als einzelne Zielvariable behandelt, sondern als Registry aus YAML-definierten `NicheConfig`-Dokumenten. Jede Nische beschreibt Discovery-Keywords, Subscriber-Filter, Sprach- und Regionshinweise, Nischen-Fit-Labels sowie Brand-Signal-Keywords in genau einer Quelle.

Die Registry ist absichtlich multi-nische-faehig, obwohl Phase 1 operativ mit `productivity` und `tech` startet. Creator koennen mehreren Nischen gleichzeitig zugeordnet sein. Das detaillierte Breakdown wird in `creator_niche_scores` gespeichert; `creators.niche_fit_score` bleibt der Best-Score-Shortcut fuer bestehende Qualification- und Ranking-Pfade.

## Scoring-Logik

### Creator-Seite

| Score | Bedeutung |
|---|---|
| `niche_fit` | Passung zur Zielnische bzw. Sub-Nische |
| `growth` | Trajectory statt reine Absolutzahl |
| `commercial_readiness` | Wie sponsorfaehig der Creator bereits wirkt |
| `fraud_risk` | Risiko fuer gekaufte Reichweite oder andere Qualitaetsprobleme |
| `evidence_coverage` | Anteil der Aussagen, die belegbar sind |

### Brand-Seite

Phase 1 nutzt drei Spend-Intent-Signale:

- Branded Content Presence
- Hiring Signals
- Creator-Program-Pages

Diese Signale werden zuerst ueber einfache, austauschbare Python-Services erzeugt: Website-HTML-Analyse, suchbasierte Hiring-Heuristik und ein Meta-Ad-Library-Service mit Fallback-Pfad, falls kein Access Token vorhanden ist. Die Gewichte liegen in `ScoringConfig`, nicht im Fachcode.

Phase 2 kann spaeter ergaenzen:

- Ad Spend Proxy
- Competitor Pressure
- DTC Readiness
- Trend Alignment
- Recency

### Match-Score

```text
0.30 niche_fit
+ 0.20 audience_alignment
+ 0.15 commercial_readiness
+ 0.15 brand_spend_intent
+ 0.10 geo_fit
+ 0.05 competitor_penalty
+ 0.05 growth_momentum
```

Die harte Regel lautet: Match vor Message. Eine starke Mail kompensiert keinen schlechten Match.

## Personalization Factory

Die Personalisierung folgt vier klaren Schritten:

1. Evidence Pack Builder
2. Angle Selector, der genau einen Angle waehlt
3. Style Renderer mit 60 bis 120 Woertern und Few-Shots aus echten Mails
4. Validator fuer Evidence-Coverage, Spam-Trigger, Similarity, Laenge und Link-Ratio

## Email-Infrastruktur-Regeln

- Zwei Sending-Domains in Phase 1, niemals die Hauptdomain
- SPF, DKIM und DMARC mit `p=quarantine` als Start
- Eskalation auf `p=reject` nur datenbasiert nach stabilen Reports und guten Kennzahlen
- Custom Tracking-Domain via CNAME
- RFC 8058 One-Click Unsubscribe
- Warmup pro Mailbox fuer 3 bis 4 Wochen
- Start mit 5 bis 10 Mails pro Tag, Ramp-up auf 30 bis 40 pro Tag
- Plaintext oder minimales HTML
- Kein Tracking-Pixel
- Maximal ein Link in der Erstmail
- Maximal vier Touches pro Sequenz
- Spam-Complaint-Rate groesser als 0.1 Prozent pro Domain fuehrt zu automatischer Domain-Pause

## Suppression-System

Das System nutzt bewusst fuenf getrennte Tabellen statt einer einzigen Blacklist:

- `suppression_unsubscribe`
- `suppression_hard_bounce`
- `suppression_spam_complaint`
- `suppression_wrong_person`
- `suppression_manual`

Vor jedem Versand laeuft ein globaler Pre-Send-Check als eigene Temporal-Activity. Es gilt eine No-Reimport-Policy: Einmal Suppression bedeutet nie wieder automatische Rueckkehr in die Send-Queue.

## KPI-Framework

Kernmetriken:

- Delivery Rate
- Reply Rate
- Positive Reply Rate
- Cost per Qualified Reply
- Spam Rate laut Postmaster
- Bounce Rate

Open Rate ist explizit keine Kern-KPI, weil das System bewusst ohne Tracking-Pixel designt ist.

## Review-UI

### Rolle

Die Review-UI ist der einzige visuelle Teil des Systems. Sie ist kein Produkt-Frontend, sondern ein Operator-Werkzeug fuer den Solo-Owner, um die autonome Pipeline zu ueberwachen und Human Gates zu bedienen.

### Stack-Empfehlung

Die Review-UI startet verbindlich mit Next.js 15, App Router, Tailwind und `shadcn/ui`. FastAPI plus HTMX bleibt verworfen fuer den Primaerpfad, weil Woche 4 eine belastbare, klar entschiedene Frontend-Basis braucht.

### Scope-Grenze in Phase 1

- Nur ein User
- Basic Auth oder ein einziger Magic-Link
- Fokus auf funktionale Review-Workflows
- Keine Settings-Pages
- Kein User-Management
- Keine komplexen Filter-UIs
- Keine Animationen, kein Dark Mode, keine Mobile-Optimierung

### Seiten-Reihenfolge mit Wochen-Mapping

| Woche | Seite | Zweck |
|---|---|---|
| 4 | `/matches` | Browser fuer generierte Brand-Creator-Paare |
| 5 | `/approvals` | Pending Outbound-Mails mit Approve, Edit, Reject |
| 7 | `/replies` | Neue Replies mit Klassifikation und Draft-Responses |
| 7 | `/creators` | Durchsuchbare Liste qualifizierter Creator |
| 7 | `/brands` | Durchsuchbare Liste aller Brands |
| 8 | `/dashboard` | KPIs und Domain Health |

### Pre-UI-Phase Woche 1 bis 3

In Woche 1 bis 3 gibt es bewusst keine UI. Interaktion mit der Pipeline erfolgt ueber SQL-Queries, PGAdmin, TablePlus oder Supabase-UI, ueber Temporal UI und ueber CLI-Skripte. Das verhindert, dass UI-Polish vor Pipeline-Funktionalitaet priorisiert wird.

## Deployment-Setup

Phase 1 startet lokal mit Docker Compose fuer schnelles Iterieren. Das Live-Setup laeuft auf einem Hetzner VPS. Temporal ist in Phase 1 self-hosted. Die Frage, ob spaeter Temporal Cloud sinnvoll ist, bleibt offen fuer Phase 2.
