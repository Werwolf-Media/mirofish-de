"""
Öffentliche, token-gebundene Share-Endpunkte (ohne Login, vom Auth-Gate ausgenommen).
Bedienen ausschließlich den zum Token gehörenden Report/Sim:
Bericht ansehen + chatten (Report Agent / einzelne Agenten), gedeckelt + widerrufbar.
"""

import traceback

from flask import request, jsonify

from . import shared_bp
from ..models.share import ShareTokenManager
from ..services.report_agent import ReportManager, ReportAgent
from ..services.simulation_manager import SimulationManager
from ..services.simulation_runner import SimulationRunner
from ..utils.logger import get_logger
from .simulation import _persona_chat_fallback, optimize_interview_prompt

logger = get_logger('mirofish.shared')


def _resolve(token):
    """Token -> (record, error_response). Bei Fehler ist record None."""
    rec = ShareTokenManager.lookup(token)
    if not rec:
        return None, (jsonify({"success": False, "error": "share_invalid"}), 404)
    if not rec.get('active', False):
        return None, (jsonify({"success": False, "error": "share_revoked"}), 403)
    return rec, None


@shared_bp.route('/<token>/report', methods=['GET'])
def shared_report(token):
    rec, err = _resolve(token)
    if err:
        return err
    report = ReportManager.get_report(rec['report_id'])
    if not report:
        return jsonify({"success": False, "error": "report_not_found"}), 404

    title = ""
    summary = ""
    if getattr(report, 'outline', None):
        title = getattr(report.outline, 'title', '') or ''
        summary = getattr(report.outline, 'summary', '') or ''
    if not title:
        title = (getattr(report, 'simulation_requirement', '') or 'MiroFish')[:120]

    agents_available = 0
    try:
        profiles = SimulationManager().get_profiles(rec['simulation_id'])
        agents_available = len(profiles or [])
    except Exception:
        agents_available = 0

    return jsonify({"success": True, "data": {
        "title": title,
        "summary": summary,
        "markdown": getattr(report, 'markdown_content', '') or '',
        "agentsAvailable": agents_available
    }})


@shared_bp.route('/<token>/profiles', methods=['GET'])
def shared_profiles(token):
    rec, err = _resolve(token)
    if err:
        return err
    platform = request.args.get('platform', 'reddit')
    try:
        profiles = SimulationManager().get_profiles(rec['simulation_id'], platform=platform) or []
    except Exception as e:
        logger.warning(f"Shared profiles fehlgeschlagen: {e}")
        profiles = []
    out = []
    for idx, p in enumerate(profiles):
        out.append({
            "agent_id": idx,
            "username": p.get('username') or p.get('name') or f"Agent {idx}",
            "profession": p.get('profession', ''),
            "bio": p.get('bio', '')
        })
    return jsonify({"success": True, "data": {"profiles": out, "count": len(out)}})


@shared_bp.route('/<token>/chat', methods=['POST'])
def shared_chat(token):
    rec, err = _resolve(token)
    if err:
        return err
    if not ShareTokenManager.is_chat_allowed(rec):
        return jsonify({"success": False, "error": "share_limit"}), 429

    data = request.get_json(silent=True) or {}
    message = data.get('message')
    history = data.get('chat_history', []) or []
    if not message:
        return jsonify({"success": False, "error": "message_required"}), 400

    try:
        agent = ReportAgent(
            graph_id=rec.get('graph_id', ''),
            simulation_id=rec.get('simulation_id', ''),
            simulation_requirement=rec.get('simulation_requirement', '')
        )
        result = agent.chat(message=message, chat_history=history)
    except Exception as e:
        logger.error(f"Shared chat fehlgeschlagen: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

    ShareTokenManager.increment(token)
    return jsonify({"success": True, "data": result})


@shared_bp.route('/<token>/interview', methods=['POST'])
def shared_interview(token):
    rec, err = _resolve(token)
    if err:
        return err
    if not ShareTokenManager.is_chat_allowed(rec):
        return jsonify({"success": False, "error": "share_limit"}), 429

    data = request.get_json(silent=True) or {}
    agent_id = data.get('agent_id')
    prompt = data.get('prompt')
    if agent_id is None or not prompt:
        return jsonify({"success": False, "error": "agent_id_and_prompt_required"}), 400

    simulation_id = rec.get('simulation_id', '')
    interviews = [{"agent_id": agent_id, "prompt": prompt}]
    try:
        if SimulationRunner.check_env_alive(simulation_id):
            optimized = [{"agent_id": agent_id, "prompt": optimize_interview_prompt(prompt)}]
            result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id, interviews=optimized, platform=None, timeout=120
            )
        else:
            result = _persona_chat_fallback(simulation_id, interviews)
            if result is None:
                return jsonify({"success": False, "error": "interview_unavailable"}), 503
    except Exception as e:
        logger.error(f"Shared interview fehlgeschlagen: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

    ShareTokenManager.increment(token)
    return jsonify({"success": True, "data": result})
