# Projekt-Nordstern

## Was gebaut wird

Gebaut wird eine zu etwa 90 Prozent automatisierte Influencer Marketing Agency (IMA) als interne Pipeline. Das System verbindet Creator mit 100k bis 1M Followern mit passenden Brands fuer Sponsoring-Deals und automatisiert Discovery, Scoring, Matching, evidenzbasierte Personalisierung, Reply-Klassifikation und Draft-Generierung.

Wichtig ist die Klarstellung: Das Projekt ist kein oeffentliches Produkt und keine Kundenseite. Es gibt keine Brand- oder Creator-Onboarding-Website. Gebaut wird eine interne Operator-Pipeline mit einer kleinen Review-UI fuer den Solo-Owner.

## Warum das gebaut wird

Das Ziel ist, repetitive Research-, Matching- und Outreach-Arbeit weitgehend zu automatisieren, ohne die kritischen Kontrollpunkte aufzugeben. Dadurch soll ein Solo-Owner mit Hilfe von Coding-Agents eine IMA betreiben koennen, ohne fuer jede Pipeline-Stufe manuell in Tools, Tabellen und Postfaecher springen zu muessen.

## Fuer wen das System ist

Das System ist fuer einen Solo-Owner gebaut, der mit Coding-Agents zusammenarbeitet. Die Nutzerrolle in Phase 1 ist genau eine Person: der Operator.

## Die vier System-Komponenten

1. **Backend-Pipeline:** Headless auf VPS, 24/7. Temporal-Workflows plus Postgres, Redis, Qdrant und die Agent-Rollen. Das ist der Motor.
2. **Sending-Infrastruktur:** Instantly oder Smartlead, eigene Sending-Domains und Google-Workspace-Postfaecher. Das ist die Bruecke zur echten Welt.
3. **Review-UI:** Next.js-Operator-Frontend nur fuer den Owner. Es bedient Human Gates und macht Pipeline-Zustaende sichtbar.
4. **Externe Observability-Tools:** Langfuse, Temporal UI, Metabase oder Grafana. Das sind Zusatz-UIs fuer Debugging und Metriken.

## Die zwei unverhandelbaren Grundregeln

1. Kein Outbound-Reply ohne Human-Approval in Phase 1.
2. Evidence-Coverage 100 Prozent: Jede faktische Behauptung in jeder Mail braucht eine `evidence_id`, sonst kein Send.

## Die fuenf harten Regeln

1. No evidence, no send.
2. No human promise without guardrails.
3. Deliverability schlaegt Copy.
4. Match vor Message.
5. Eval-driven Modellwahl.

## Was explizit nicht gebaut wird

- Oeffentliche Website, Kunden-Landingpage oder Onboarding-Portal
- Multi-User-Auth, User-Management, Public Signup
- Kafka, NATS oder ClickHouse in Phase 1
- Auto-Reply-Sending
- Auto-Negotiation oder Preiszusagen ohne Human Gate
- Multi-Geo oder Multi-Language
- Mehr als eine Nische in Phase 1
- Agent-SDKs oder Multi-Agent-Frameworks wie CrewAI, LangGraph, Autogen oder Anthropic Agent SDK
- Schoene UIs, Animationen, Dark-Mode-Toggle oder Mobile-Optimierung
- Rate-Card-Prediction
- Contract-Drafting

## Phase-1-Zielkorridor

Phase 1 ist auf einen Zielkorridor von 6 bis 10 Wochen ausgelegt:

- Woche 1: Fundament und erster End-to-End-Workflow, noch ohne UI
- Woche 2: Creator-Scoring, Growth-Tracking, Evidence-Building
- Woche 3 bis 4: Brand-Seite, Spend-Intent, UI-Entscheidung bis Ende Woche 3
- Woche 4: Matching plus Review-UI v0 mit `/matches`
- Woche 5: Personalization Factory plus `/approvals`
- Woche 6: Erste 10 Live-Mails mit manueller Approval
- Woche 7 bis 8: Reply-Handling, weitere UI-Seiten, Dashboard, Observability
- Ab Woche 9: Kalibrierung, A/B-Tests, Policy-Matrix-Vorbereitung
