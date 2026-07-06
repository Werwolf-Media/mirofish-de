# MiroFish Maschinen-API (`/api/v1`)

Schnittstelle, damit andere Tools (Strataigy, AI Act Checker, eigene Backends …)
MiroFish-Prognosen **direkt aus dem Tool heraus** nutzen können — ohne UI und
ohne App-Passwort.

Ein **Run** = die komplette Pipeline in einem Aufruf:
Ontologie → Zep-Graph → Simulation vorbereiten → Simulation laufen lassen → Bericht.
Der Aufrufer startet den Run, pollt den Status (oder bekommt einen Webhook) und
holt am Ende den fertigen Bericht als Markdown ab.

---

## Einrichtung (einmalig)

1. API-Key erzeugen:
   ```bash
   openssl rand -hex 24
   ```
2. In der `backend/.env` (bzw. Projekt-`.env`) auf dem MiroFish-Rechner eintragen:
   ```
   EXTERNAL_API_KEY=<der-erzeugte-key>
   ```
3. MiroFish neu starten (`MiroFish-Starten.command`).

Ohne gesetzten Key antwortet die Schnittstelle mit `503 external_api_disabled`.

**Auth bei jedem Request:** Header `X-Api-Key: <key>`
(alternativ `Authorization: Bearer <key>`).

Basis-URL im LAN z. B.: `http://<mac-mini-ip>:5001`

---

## Endpunkte

### `GET /api/v1/ping` — Verbindung/Key testen
```bash
curl -s -H "X-Api-Key: $KEY" http://localhost:5001/api/v1/ping
```
→ `{"success": true, "service": "MiroFish external API", "version": 1}`

### `POST /api/v1/runs` — Run starten
```bash
curl -s -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  http://localhost:5001/api/v1/runs -d '{
  "requirement": "Wie reagiert der Markt auf die Einführung unseres neuen SaaS-Preismodells?",
  "seed_text": "Kontext/Daten: Zielgruppe Handwerksbetriebe 5-50 MA, Preis 49-199 EUR ...",
  "project_name": "Kunde X – Preismodell",
  "platform": "parallel",
  "max_rounds": 30,
  "callback_url": "https://mein-tool.example/webhooks/mirofish"
}'
```

| Feld | Pflicht | Beschreibung |
|---|---|---|
| `requirement` | ✅ | Was soll simuliert/prognostiziert werden? |
| `seed_text` | ✅* | Kontext/Daten als Text (\*oder `include_german_sources: true`) |
| `project_name` | – | Name für Verlauf + Abrechnung (Default `API-Run`) |
| `additional_context` | – | Zusätzliche Hinweise für die Ontologie |
| `include_german_sources` | – | Aktuelle deutsche Quellen als Seed einbeziehen |
| `platform` | – | `twitter` \| `reddit` \| `parallel` (Default) |
| `max_rounds` | – | Runden-Deckel (1–500), begrenzt Dauer & Kosten |
| `callback_url` | – | Webhook: `POST {run_id, status, report_id, error}` bei Abschluss/Fehler |

Antwort `202`:
```json
{"success": true, "data": {"run_id": "run_ab12cd34ef56", "status": "running", "phase": "queued", "progress": 0}}
```

`409 run_in_progress`: Es läuft bereits ein Run — MiroFish verarbeitet externe
Runs bewusst **seriell** (nur so ist die Kosten-Zuordnung pro Run korrekt).

### `GET /api/v1/runs/<run_id>` — Status pollen
```bash
curl -s -H "X-Api-Key: $KEY" http://localhost:5001/api/v1/runs/run_ab12cd34ef56
```
```json
{"success": true, "data": {
  "run_id": "run_ab12cd34ef56",
  "status": "running",            // running | completed | failed
  "phase": "simulation",          // queued|ontology|graph|create|prepare|simulation|report|completed
  "progress": 71,
  "current_cost_eur": 2.34,       // Live-Kosten (OpenRouter-Delta)
  "report_id": null,
  "error": null
}}
```
Empfohlenes Poll-Intervall: 15–30 s. Ein Run dauert je nach Umfang **15–60+ Minuten**.

### `GET /api/v1/runs/<run_id>/report` — Bericht abholen
```bash
curl -s -H "X-Api-Key: $KEY" http://localhost:5001/api/v1/runs/run_ab12cd34ef56/report
```
```json
{"success": true, "data": {
  "run_id": "run_ab12cd34ef56",
  "report_id": "report_898c272aee60",
  "title": "Zukunftsprognose: ...",
  "markdown": "# ...",
  "completed_at": "2026-07-06T14:02:11"
}}
```
`409 report_not_ready` solange der Run noch läuft (Body enthält `phase`/`progress`).

### `POST /api/v1/runs/<run_id>/chat` — Rückfragen an den Report-Agenten
```bash
curl -s -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  http://localhost:5001/api/v1/runs/run_ab12cd34ef56/chat \
  -d '{"message": "Was war der größte Kritikpunkt der simulierten Nutzer?"}'
```
Optional `chat_history` (Array aus `{role, content}`) für Folgefragen mitschicken.

### `POST /api/v1/runs/<run_id>/cancel` — Run abbrechen
Stoppt eine laufende Simulation und markiert den Run als `failed`.

### `GET /api/v1/runs` — Alle Runs auflisten

---

## Typischer Client-Ablauf (Pseudocode)

```js
const r = await post('/api/v1/runs', { requirement, seed_text, project_name })
const runId = r.data.run_id

let run
do {
  await sleep(20_000)
  run = (await get(`/api/v1/runs/${runId}`)).data
} while (run.status === 'running')

if (run.status === 'completed') {
  const report = (await get(`/api/v1/runs/${runId}/report`)).data
  // report.markdown weiterverarbeiten
} else {
  // run.error auswerten (z. B. Kosten-Deckel, OpenRouter 402 ...)
}
```

Mit `callback_url` entfällt das Polling: MiroFish meldet sich per
`POST {run_id, status, report_id, error}`, sobald der Run fertig oder
fehlgeschlagen ist.

---

## Gut zu wissen

- **Kosten & Abrechnung:** Externe Runs erscheinen ganz normal in der
  Abrechnungs-Übersicht (echte LLM-Kosten via OpenRouter-Delta, Projektname =
  `project_name`). Der **Kosten-Deckel** (`MAX_COST_EUR`, Admin-einstellbar)
  gilt auch hier — bei Überschreitung bricht der Run mit `failed` ab.
- **Seriell:** Nur ein externer Run gleichzeitig (409 bei Parallelversuch).
- **Sicherheit:** Der API-Key ist ein Vollzugriff auf Runs — nur serverseitig
  in den Tools hinterlegen, nie in Frontend-Code. Bei Verdacht auf Leak: Key in
  der `.env` tauschen + Neustart.
- **Fehlerbilder:** `401 invalid_api_key`, `503 external_api_disabled`,
  `409 run_in_progress` / `report_not_ready`, `400` mit `hint`-Feld bei
  fehlenden Parametern.
