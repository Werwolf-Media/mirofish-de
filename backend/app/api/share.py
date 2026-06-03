"""
Share-Verwaltung (Login nötig, hinter dem Auth-Gate).
Erstellen/Status/Deaktivieren/Aktivieren/Zähler-Reset von teilbaren Ergebnis-Links.
"""

from flask import request, jsonify

from . import share_bp
from ..models.share import ShareTokenManager
from ..services.report_agent import ReportManager
from ..utils.logger import get_logger

logger = get_logger('mirofish.share')


@share_bp.route('/create', methods=['POST'])
def create_share():
    data = request.get_json(silent=True) or {}
    report_id = data.get('report_id')
    if not report_id:
        return jsonify({"success": False, "error": "report_id_required"}), 400

    report = ReportManager.get_report(report_id)
    if not report:
        return jsonify({"success": False, "error": "report_not_found"}), 404

    rec = ShareTokenManager.create(
        report_id=report_id,
        simulation_id=getattr(report, 'simulation_id', '') or '',
        graph_id=getattr(report, 'graph_id', '') or '',
        simulation_requirement=getattr(report, 'simulation_requirement', '') or '',
    )
    return jsonify({"success": True, "data": ShareTokenManager.public_status(rec)})


@share_bp.route('/by-report/<report_id>', methods=['GET'])
def share_by_report(report_id: str):
    rec = ShareTokenManager.get_by_report(report_id)
    if not rec:
        return jsonify({"success": True, "data": {"exists": False}})
    status = ShareTokenManager.public_status(rec)
    status["exists"] = True
    return jsonify({"success": True, "data": status})


@share_bp.route('/<token>/deactivate', methods=['POST'])
def deactivate_share(token: str):
    rec = ShareTokenManager.set_active(token, False)
    if not rec:
        return jsonify({"success": False, "error": "share_not_found"}), 404
    return jsonify({"success": True, "data": ShareTokenManager.public_status(rec)})


@share_bp.route('/<token>/activate', methods=['POST'])
def activate_share(token: str):
    rec = ShareTokenManager.set_active(token, True)
    if not rec:
        return jsonify({"success": False, "error": "share_not_found"}), 404
    return jsonify({"success": True, "data": ShareTokenManager.public_status(rec)})


@share_bp.route('/<token>/reset', methods=['POST'])
def reset_share(token: str):
    rec = ShareTokenManager.reset_count(token)
    if not rec:
        return jsonify({"success": False, "error": "share_not_found"}), 404
    return jsonify({"success": True, "data": ShareTokenManager.public_status(rec)})
