"""
Externe Pipeline: kompletter MiroFish-Run als EIN Aufruf.

Für die Maschinen-Schnittstelle (/api/v1) fährt dieser Orchestrator die
gesamte Pipeline automatisch durch, die sonst das Frontend Schritt für
Schritt treibt:

    1. Ontologie generieren   POST /api/graph/ontology/generate
    2. Zep-Graph bauen        POST /api/graph/build            (+ Task-Poll)
    3. Simulation anlegen     POST /api/simulation/create
    4. Simulation vorbereiten POST /api/simulation/prepare     (+ Status-Poll)
    5. Simulation starten     POST /api/simulation/start       (+ Run-Poll)
    6. Bericht erzeugen       POST /api/report/generate        (+ Report-Poll)

Bewusst über die INTERNEN HTTP-Routen (localhost) statt Service-Aufrufe:
null Logik-Duplikation — externe Runs verhalten sich exakt wie UI-Runs
(inkl. Billing-Hooks, Kosten-Deckel, Sprach-Direktiven).

Run-Zustand als JSON unter uploads/external_runs/<run_id>.json
(gleiches Muster wie BillingManager/ShareTokenManager).
"""

import os
import json
import time
import uuid
import threading
from datetime import datetime

from ..config import Config
from ..utils.logger import get_logger
from ..utils.auth import expected_token

logger = get_logger('mirofish.external')

RUNS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'external_runs')

# Interne Basis-URL (eigener Prozess); FLASK_PORT wie in run.py
_BASE_URL = f"http://127.0.0.1:{int(os.environ.get('FLASK_PORT', 5001))}"

# Phasen in Reihenfolge (für progress-Berechnung)
PHASES = ['queued', 'ontology', 'graph', 'create', 'prepare', 'simulation', 'report', 'completed']

# Obergrenzen pro Phase (Sekunden) — großzügig, aber endlich
_TIMEOUTS = {
    'ontology': 600,
    'graph': 3600,
    'prepare': 3600,
    'simulation': 6 * 3600,
    'report': 3600,
}

_lock = threading.Lock()


# ---------------------------------------------------------------- HTTP intern

def _http(method: str, path: str, payload=None, form=None, timeout=590):
    """Interner HTTP-Aufruf mit App-Token. JSON rein/raus."""
    import urllib.request
    import urllib.parse
    import urllib.error

    url = _BASE_URL + path
    headers = {
        'X-App-Token': expected_token(),
        'Accept-Language': 'de',
    }
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        # Fehler-Body mit zurückgeben (enthält meist {"error": ...})
        try:
            body = json.loads(e.read().decode('utf-8'))
        except Exception:
            body = {}
        body.setdefault('success', False)
        body.setdefault('error', f'HTTP {e.code}')
        return body


# ---------------------------------------------------------------- Run-Store

class ExternalRunManager:
    """Verwaltet externe Runs (JSON-Dateien) + Orchestrierungs-Threads."""

    @classmethod
    def _path(cls, run_id: str) -> str:
        # run_id ist selbst erzeugt (run_<hex>) — kein Pfad-Injection möglich,
        # trotzdem defensiv säubern
        safe = ''.join(c for c in run_id if c.isalnum() or c == '_')
        return os.path.join(RUNS_DIR, f"{safe}.json")

    @classmethod
    def get(cls, run_id: str) -> dict:
        try:
            with open(cls._path(run_id), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    @classmethod
    def list(cls) -> list:
        os.makedirs(RUNS_DIR, exist_ok=True)
        runs = []
        for name in os.listdir(RUNS_DIR):
            if not name.endswith('.json'):
                continue
            try:
                with open(os.path.join(RUNS_DIR, name), 'r', encoding='utf-8') as f:
                    runs.append(json.load(f))
            except Exception:
                continue
        runs.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        return runs

    @classmethod
    def _save(cls, run: dict):
        os.makedirs(RUNS_DIR, exist_ok=True)
        run['updated_at'] = datetime.now().isoformat()
        path = cls._path(run['run_id'])
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(run, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    @classmethod
    def _update(cls, run_id: str, **fields):
        with _lock:
            run = cls.get(run_id) or {'run_id': run_id}
            run.update(fields)
            # Fortschritt grob aus der Phase ableiten
            phase = run.get('phase', 'queued')
            if phase in PHASES:
                run['progress'] = round(PHASES.index(phase) / (len(PHASES) - 1) * 100)
            cls._save(run)
            return run

    # ------------------------------------------------------------ Start

    @classmethod
    def recover_stale(cls):
        """Beim Backend-Start: verwaiste 'running'-Runs als failed markieren.
        Orchestrator-Threads überleben einen Neustart nicht — ohne diese
        Bereinigung stünden solche Runs für immer auf 'running'."""
        count = 0
        for run in cls.list():
            if run.get('status') == 'running':
                cls._update(run['run_id'], status='failed',
                            error='Backend wurde neu gestartet — Run abgebrochen. Bitte neu starten.')
                count += 1
        if count:
            logger.warning(f"{count} verwaiste externe Run(s) als failed markiert")

    @classmethod
    def start_run(cls, params: dict) -> dict:
        """Legt einen Run an und startet den Orchestrierungs-Thread."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run = {
            'run_id': run_id,
            'status': 'running',        # running | completed | failed
            'phase': 'queued',
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            # Eingaben (fürs Nachvollziehen)
            'requirement': params['requirement'],
            'project_name': params.get('project_name') or 'API-Run',
            'platform': params.get('platform') or 'parallel',
            'max_rounds': params.get('max_rounds'),
            'callback_url': params.get('callback_url'),
            # Ergebnisse der Pipeline-Schritte
            'project_id': None,
            'graph_id': None,
            'simulation_id': None,
            'report_id': None,
            'error': None,
        }
        cls._save(run)

        thread = threading.Thread(
            target=cls._orchestrate,
            args=(run_id, params),
            daemon=True,
            name=f"external-{run_id}"
        )
        thread.start()
        logger.info(f"Externer Run gestartet: {run_id} ({run['project_name']})")
        return run

    # ------------------------------------------------------------ Pipeline

    @classmethod
    def _orchestrate(cls, run_id: str, params: dict):
        try:
            # ---- 1) Ontologie -------------------------------------------
            cls._update(run_id, phase='ontology')
            form = {
                'simulation_requirement': params['requirement'],
                'project_name': params.get('project_name') or 'API-Run',
                'seed_text': params.get('seed_text') or '',
                'additional_context': params.get('additional_context') or '',
            }
            if params.get('include_german_sources'):
                form['include_german_sources'] = 'true'
            res = _http('POST', '/api/graph/ontology/generate', form=form)
            if not res.get('success'):
                raise RuntimeError(f"Ontologie: {res.get('error')}")
            project_id = res['data']['project_id']
            cls._update(run_id, project_id=project_id)

            # ---- 2) Graph bauen (async Task) ----------------------------
            cls._update(run_id, phase='graph')
            res = _http('POST', '/api/graph/build', payload={'project_id': project_id})
            if not res.get('success'):
                raise RuntimeError(f"Graph-Build: {res.get('error')}")
            task_id = res['data']['task_id']
            graph_id = cls._poll(
                lambda: _http('GET', f'/api/graph/task/{task_id}'),
                done=lambda d: d.get('status') == 'completed',
                failed=lambda d: d.get('status') == 'failed',
                extract=lambda d: (d.get('result') or {}).get('graph_id'),
                timeout=_TIMEOUTS['graph'], interval=10,
                label='Graph-Build'
            )
            # graph_id notfalls aus dem Projekt lesen
            if not graph_id:
                pres = _http('GET', f'/api/graph/project/{project_id}')
                graph_id = ((pres.get('data') or {}).get('graph_id')) if pres.get('success') else None
            cls._update(run_id, graph_id=graph_id)

            # ---- 3) Simulation anlegen ----------------------------------
            cls._update(run_id, phase='create')
            res = _http('POST', '/api/simulation/create', payload={'project_id': project_id})
            if not res.get('success'):
                raise RuntimeError(f"Simulation anlegen: {res.get('error')}")
            simulation_id = res['data']['simulation_id']
            cls._update(run_id, simulation_id=simulation_id)

            # ---- 4) Vorbereiten (async Task) ----------------------------
            cls._update(run_id, phase='prepare')
            res = _http('POST', '/api/simulation/prepare', payload={'simulation_id': simulation_id})
            if not res.get('success'):
                raise RuntimeError(f"Vorbereitung: {res.get('error')}")
            prep_task = (res.get('data') or {}).get('task_id')
            cls._poll(
                lambda: _http('POST', '/api/simulation/prepare/status',
                              payload={'task_id': prep_task, 'simulation_id': simulation_id}),
                done=lambda d: d.get('status') in ('ready', 'completed') or d.get('already_prepared'),
                failed=lambda d: d.get('status') == 'failed',
                timeout=_TIMEOUTS['prepare'], interval=10,
                label='Vorbereitung'
            )

            # ---- 5) Simulation starten + laufen lassen ------------------
            cls._update(run_id, phase='simulation')
            start_payload = {
                'simulation_id': simulation_id,
                'platform': params.get('platform') or 'parallel',
                'enable_graph_memory_update': True,
            }
            if params.get('max_rounds'):
                start_payload['max_rounds'] = int(params['max_rounds'])
            res = _http('POST', '/api/simulation/start', payload=start_payload)
            if not res.get('success'):
                raise RuntimeError(f"Simulation-Start: {res.get('error')}")

            def _sim_status():
                r = _http('GET', f'/api/simulation/{simulation_id}/run-status')
                d = r.get('data') or {}
                # Live-Kosten in den Run-Zustand spiegeln
                if d.get('current_cost_eur') is not None:
                    cls._update(run_id, current_cost_eur=d.get('current_cost_eur'))
                return r

            cls._poll(
                _sim_status,
                done=lambda d: d.get('runner_status') == 'completed',
                failed=lambda d: d.get('runner_status') in ('failed', 'stopped'),
                fail_msg=lambda d: d.get('error') or f"runner_status={d.get('runner_status')}",
                timeout=_TIMEOUTS['simulation'], interval=15,
                label='Simulation'
            )

            # ---- 6) Bericht ---------------------------------------------
            cls._update(run_id, phase='report')
            res = _http('POST', '/api/report/generate', payload={'simulation_id': simulation_id})
            if not res.get('success'):
                raise RuntimeError(f"Bericht-Start: {res.get('error')}")
            report_id = (res.get('data') or {}).get('report_id')
            cls._update(run_id, report_id=report_id)

            def _report_status():
                return _http('GET', f'/api/report/{report_id}')

            cls._poll(
                _report_status,
                done=lambda d: d.get('status') == 'completed',
                failed=lambda d: d.get('status') == 'failed',
                fail_msg=lambda d: d.get('error') or 'Berichtserstellung fehlgeschlagen',
                timeout=_TIMEOUTS['report'], interval=10,
                label='Bericht'
            )

            run = cls._update(run_id, phase='completed', status='completed', progress=100)
            logger.info(f"Externer Run abgeschlossen: {run_id} -> report {report_id}")
            cls._notify(run)

        except Exception as e:
            logger.error(f"Externer Run fehlgeschlagen: {run_id}: {e}")
            run = cls._update(run_id, status='failed', error=str(e))
            cls._notify(run)

    # ------------------------------------------------------------ Helpers

    @classmethod
    def _poll(cls, fetch, done, failed, timeout, interval, label,
              extract=None, fail_msg=None):
        """Pollt fetch() bis done/failed/timeout. Gibt extract(data) zurück."""
        deadline = time.time() + timeout
        last = {}
        while time.time() < deadline:
            try:
                res = fetch()
            except Exception as e:
                logger.warning(f"{label}: Poll-Fehler (weiter): {e}")
                time.sleep(interval)
                continue
            data = res.get('data') or {}
            last = data
            if res.get('success'):
                if failed(data):
                    msg = fail_msg(data) if fail_msg else (data.get('error') or f'{label} fehlgeschlagen')
                    raise RuntimeError(f"{label}: {msg}")
                if done(data):
                    return extract(data) if extract else None
            time.sleep(interval)
        raise RuntimeError(f"{label}: Zeitlimit ({timeout}s) überschritten "
                           f"(letzter Status: {last.get('status') or last.get('runner_status')})")

    @classmethod
    def _notify(cls, run: dict):
        """Optionaler Webhook bei Abschluss/Fehler (best effort)."""
        url = (run or {}).get('callback_url')
        if not url or not str(url).lower().startswith(('http://', 'https://')):
            return
        try:
            import urllib.request
            payload = {
                'run_id': run['run_id'],
                'status': run['status'],
                'report_id': run.get('report_id'),
                'error': run.get('error'),
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=15)
            logger.info(f"Webhook benachrichtigt: {url}")
        except Exception as e:
            logger.warning(f"Webhook fehlgeschlagen ({url}): {e}")
