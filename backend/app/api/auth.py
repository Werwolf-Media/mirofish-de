"""
Auth-API: Login gegen geteiltes Passwort.
"""

from flask import request, jsonify

from . import auth_bp
from ..utils.auth import check_password, expected_token
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
