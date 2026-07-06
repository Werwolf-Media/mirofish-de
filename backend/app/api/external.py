"""
Maschinen-Schnittstelle /api/v1 — für Saschas andere Tools.

Auth: Header `X-Api-Key` (oder `Authorization: Bearer <key>`) gegen
Config.EXTERNAL_API_KEY. Kein App-Passwort nötig; ohne konfigurierten
Key ist die Schnittstelle komplett deaktiviert (503).

Ein Run = komplette Pipeline (Ontologie → Graph → Simulation → Bericht),
orchestriert von ExternalRunManager im Hintergrund.

    POST /api/v1/runs                 Run starten (202 + run_id)
    GET  /api/v1/runs                 Runs auflisten
    GET  /api/v1/runs/<run_id>        Status/Fortschritt/Kosten
    GET  /api/v1/runs/<run_id>/report Fertiger Bericht (Markdown)
    POST /api/v1/runs/<run_id>/chat   Mit dem Report-Agenten chatten
    POST /api/v1/runs/<run_id>/cancel Laufende Simulation abbrechen
    GET  /api/v1/ping                 Auth-/Erreichbarkeits-Check
"""

import hmac

from flask import request, jsonify

from . import external_bp
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.external')

# Whitelist der Felder, die ein Run-Status nach außen zeigt
_PUBLIC_FIELDS = (
    'run_id', 'status', 'phase', 'progress', 'created_at', 'updated_at',
    'project_name', 'requirement', 'platform', 'max_rounds',
    'report_id', 'error', 'current_cost_eur',
)


def _api_key_ok() -> bool:
    configured = Config.EXTERNAL_API_KEY or ''
    if not configured:
        return False
    sent = request.headers.get('X-Api-Key', '')
    if not sent:
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            sent = auth[7:]
    return bool(sent) and hmac.compare_digest(sent, configured)


def _guard():
    """None wenn ok, sonst (response, status)."""
    if not Config.EXTERNAL_API_KEY:
        return jsonify({"success": False, "error": "external_api_disabled",
                        "hint": "EXTERNAL_API_KEY in .env setzen"}), 503
    if not _api_key_ok():
        return jsonify({"success": False, "error": "invalid_api_key"}), 401
    return None


def _public(run: dict) -> dict:
    return {k: run.get(k) for k in _PUBLIC_FIELDS}


@external_bp.route('/ping', methods=['GET'])
def ping():
    err = _guard()
    if err:
        return err
    return jsonify({"success": True, "service": "MiroFish external API", "version": 1})


@external_bp.route('/runs', methods=['POST'])
def create_run():
    err = _guard()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    requirement = (data.get('requirement') or '').strip()
    seed_text = (data.get('seed_text') or '').strip()

    if not requirement:
        return jsonify({"success": False, "error": "requirement_required",
                        "hint": "Was soll simuliert/prognostiziert werden?"}), 400
    if not seed_text and not data.get('include_german_sources'):
        return jsonify({"success": False, "error": "seed_text_required",
                        "hint": "seed_text (Kontext/Daten) mitgeben oder "
                                "include_german_sources=true setzen"}), 400

    platform = data.get('platform') or 'parallel'
    if platform not in ('twitter', 'reddit', 'parallel'):
        return jsonify({"success": False, "error": "invalid_platform",
                        "hint": "platform: twitter | reddit | parallel"}), 400

    max_rounds = data.get('max_rounds')
    if max_rounds is not None:
        try:
            max_rounds = max(1, min(500, int(max_rounds)))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "invalid_max_rounds"}), 400

    # Nur ein externer Run gleichzeitig: das OpenRouter-Kosten-Delta
    # (Billing + Kosten-Deckel) ist nur bei seriellen Runs korrekt zuordenbar
    from ..services.external_pipeline import ExternalRunManager
    active = [r for r in ExternalRunManager.list() if r.get('status') == 'running']
    if active:
        return jsonify({
            "success": False,
            "error": "run_in_progress",
            "hint": f"Es läuft bereits Run {active[0]['run_id']} — bitte warten.",
            "active_run_id": active[0]['run_id'],
        }), 409

    run = ExternalRunManager.start_run({
        'requirement': requirement,
        'seed_text': seed_text,
        'project_name': (data.get('project_name') or '').strip() or 'API-Run',
        'additional_context': (data.get('additional_context') or '').strip(),
        'include_german_sources': bool(data.get('include_german_sources')),
        'platform': platform,
        'max_rounds': max_rounds,
        'callback_url': (data.get('callback_url') or '').strip() or None,
    })
    return jsonify({"success": True, "data": _public(run)}), 202


@external_bp.route('/runs', methods=['GET'])
def list_runs():
    err = _guard()
    if err:
        return err
    from ..services.external_pipeline import ExternalRunManager
    return jsonify({"success": True,
                    "data": [_public(r) for r in ExternalRunManager.list()]})


@external_bp.route('/runs/<run_id>', methods=['GET'])
def get_run(run_id: str):
    err = _guard()
    if err:
        return err
    from ..services.external_pipeline import ExternalRunManager
    run = ExternalRunManager.get(run_id)
    if not run:
        return jsonify({"success": False, "error": "run_not_found"}), 404
    return jsonify({"success": True, "data": _public(run)})


@external_bp.route('/runs/<run_id>/report', methods=['GET'])
def get_run_report(run_id: str):
    err = _guard()
    if err:
        return err
    from ..services.external_pipeline import ExternalRunManager
    run = ExternalRunManager.get(run_id)
    if not run:
        return jsonify({"success": False, "error": "run_not_found"}), 404
    if run.get('status') != 'completed' or not run.get('report_id'):
        return jsonify({"success": False, "error": "report_not_ready",
                        "status": run.get('status'), "phase": run.get('phase'),
                        "progress": run.get('progress')}), 409

    from ..services.report_agent import ReportManager
    report = ReportManager.get_report(run['report_id'])
    if not report:
        return jsonify({"success": False, "error": "report_not_found"}), 404
    rep = report.to_dict()
    return jsonify({"success": True, "data": {
        "run_id": run_id,
        "report_id": run['report_id'],
        "title": (rep.get('outline') or {}).get('title'),
        "markdown": rep.get('markdown_content'),
        "created_at": rep.get('created_at'),
        "completed_at": rep.get('completed_at'),
    }})


@external_bp.route('/runs/<run_id>/chat', methods=['POST'])
def chat_run(run_id: str):
    """Frage an den Report-Agenten des Runs (nutzt die bestehende Chat-Route)."""
    err = _guard()
    if err:
        return err
    from ..services.external_pipeline import ExternalRunManager, _http
    run = ExternalRunManager.get(run_id)
    if not run:
        return jsonify({"success": False, "error": "run_not_found"}), 404
    if not run.get('simulation_id'):
        return jsonify({"success": False, "error": "run_not_ready"}), 409

    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"success": False, "error": "message_required"}), 400

    res = _http('POST', '/api/report/chat', payload={
        'simulation_id': run['simulation_id'],
        'message': message,
        'chat_history': data.get('chat_history') or [],
    })
    status = 200 if res.get('success') else 502
    return jsonify(res), status


@external_bp.route('/runs/<run_id>/cancel', methods=['POST'])
def cancel_run(run_id: str):
    err = _guard()
    if err:
        return err
    from ..services.external_pipeline import ExternalRunManager, _http
    run = ExternalRunManager.get(run_id)
    if not run:
        return jsonify({"success": False, "error": "run_not_found"}), 404
    if run.get('status') != 'running':
        return jsonify({"success": False, "error": "run_not_running",
                        "status": run.get('status')}), 409

    # Läuft gerade die Simulation? Dann Prozess stoppen; der Orchestrator
    # erkennt runner_status=stopped und markiert den Run als failed.
    if run.get('simulation_id'):
        _http('POST', '/api/simulation/stop',
              payload={'simulation_id': run['simulation_id']})
    ExternalRunManager._update(run_id, status='failed',
                               error='Vom Aufrufer abgebrochen (cancel)')
    return jsonify({"success": True, "data": {"run_id": run_id, "status": "failed"}})
