"""
Abrechnungs-API (hinter dem Login). Liste aller Runs + Bearbeiten (Projekt/Preis).
"""

from flask import request, jsonify

from . import billing_bp
from ..config import Config
from ..models.billing import BillingManager
from ..utils.logger import get_logger

logger = get_logger('mirofish.billing')


def _enrich(rec: dict) -> dict:
    rate = float(getattr(Config, 'EUR_PER_USD', 0.92))
    cost_usd = rec.get('cost_usd')
    has_cost = isinstance(cost_usd, (int, float)) and cost_usd > 0
    cost_eur = round(float(cost_usd) * rate, 2) if has_cost else None
    price = float(rec.get('billing_price_eur', 0.0) or 0.0)
    margin = round(price - cost_eur, 2) if cost_eur is not None else None
    return {
        "project_id": rec.get('project_id'),
        "project_name": rec.get('project_name', ''),
        "requirement": rec.get('requirement', ''),
        "simulation_id": rec.get('simulation_id', ''),
        "report_id": rec.get('report_id', ''),
        "status": rec.get('status', ''),
        "created_at": rec.get('created_at', ''),
        "completed_at": rec.get('completed_at', ''),
        "billing_price_eur": price,
        "cost_usd": float(cost_usd) if has_cost else None,
        "cost_eur": cost_eur,
        "margin_eur": margin,
    }


@billing_bp.route('/list', methods=['GET'])
def list_billing():
    records = [_enrich(r) for r in BillingManager.list()]
    return jsonify({"success": True, "data": records, "eur_per_usd": float(getattr(Config, 'EUR_PER_USD', 0.92))})


@billing_bp.route('/<project_id>/update', methods=['POST'])
def update_billing(project_id: str):
    data = request.get_json(silent=True) or {}
    fields = {}
    if 'project_name' in data:
        fields['project_name'] = data['project_name']
    if 'billing_price_eur' in data:
        fields['billing_price_eur'] = data['billing_price_eur']
    rec = BillingManager.update(project_id, fields)
    if not rec:
        return jsonify({"success": False, "error": "billing_not_found"}), 404
    return jsonify({"success": True, "data": _enrich(rec)})
