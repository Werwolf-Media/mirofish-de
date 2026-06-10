"""
Auth-API: Login gegen geteiltes Passwort.
"""

from flask import request, jsonify

from . import auth_bp
from ..utils.auth import check_password, expected_token, check_admin_password, expected_admin_token
from ..utils.locale import t


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    password = data.get('password', '')

    if check_password(password):
        return jsonify({
            "success": True,
            "token": expected_token()
        })

    return jsonify({
        "success": False,
        "error": t('api.loginInvalid')
    }), 401


@auth_bp.route('/admin-login', methods=['POST'])
def admin_login():
    """Admin-Login (nur Inhaber) – schaltet die Abrechnung frei."""
    data = request.get_json(silent=True) or {}
    if check_admin_password(data.get('password', '')):
        return jsonify({"success": True, "token": expected_admin_token()})
    return jsonify({"success": False, "error": t('api.loginInvalid')}), 401
