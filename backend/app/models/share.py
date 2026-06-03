"""
Share-Token-Store
=================

Persistiert teilbare Ergebnis-Links als JSON unter uploads/share_tokens/<token>.json.
Ein Token bindet genau einen Report (+ Simulation) und erlaubt Empfängern ohne
Login: Bericht ansehen + chatten (gedeckelt durch message_limit, widerrufbar).

Bewusst abhängigkeitsfrei (nur Config) – das Auflösen report_id -> sim/graph
passiert in der API-Schicht (api/share.py).
"""

import os
import json
import uuid
from datetime import datetime, timezone

from ..config import Config

DEFAULT_MESSAGE_LIMIT = 50


class ShareTokenManager:
    SHARE_DIR = os.path.join(Config.UPLOAD_FOLDER, 'share_tokens')

    @classmethod
    def _ensure_dir(cls):
        os.makedirs(cls.SHARE_DIR, exist_ok=True)

    @classmethod
    def _path(cls, token: str) -> str:
        return os.path.join(cls.SHARE_DIR, f"{token}.json")

    @classmethod
    def _save(cls, rec: dict):
        cls._ensure_dir()
        with open(cls._path(rec['token']), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

    @classmethod
    def lookup(cls, token: str):
        """Token-Datensatz laden oder None (auch bei ungültigem Token-Format)."""
        if not token or '/' in token or '\\' in token or '.' in token:
            return None
        path = cls._path(token)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def get_by_report(cls, report_id: str):
        """Vorhandenen Token für einen Report finden (1 Token pro Report)."""
        cls._ensure_dir()
        for name in os.listdir(cls.SHARE_DIR):
            if not name.endswith('.json'):
                continue
            try:
                with open(os.path.join(cls.SHARE_DIR, name), 'r', encoding='utf-8') as f:
                    rec = json.load(f)
                if rec.get('report_id') == report_id:
                    return rec
            except Exception:
                continue
        return None

    @classmethod
    def create(cls, report_id: str, simulation_id: str, graph_id: str = "",
               simulation_requirement: str = "", message_limit: int = DEFAULT_MESSAGE_LIMIT):
        """Token anlegen oder vorhandenen für diesen Report zurückgeben."""
        existing = cls.get_by_report(report_id)
        if existing:
            return existing
        token = f"share_{uuid.uuid4().hex[:20]}"
        rec = {
            "token": token,
            "report_id": report_id,
            "simulation_id": simulation_id,
            "graph_id": graph_id or "",
            "simulation_requirement": simulation_requirement or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
            "message_count": 0,
            "message_limit": int(message_limit),
        }
        cls._save(rec)
        return rec

    @classmethod
    def set_active(cls, token: str, active: bool):
        rec = cls.lookup(token)
        if not rec:
            return None
        rec['active'] = bool(active)
        cls._save(rec)
        return rec

    @classmethod
    def reset_count(cls, token: str):
        rec = cls.lookup(token)
        if not rec:
            return None
        rec['message_count'] = 0
        cls._save(rec)
        return rec

    @classmethod
    def increment(cls, token: str):
        rec = cls.lookup(token)
        if not rec:
            return None
        rec['message_count'] = int(rec.get('message_count', 0)) + 1
        cls._save(rec)
        return rec

    @staticmethod
    def is_chat_allowed(rec: dict) -> bool:
        if not rec or not rec.get('active', False):
            return False
        return int(rec.get('message_count', 0)) < int(rec.get('message_limit', DEFAULT_MESSAGE_LIMIT))

    @staticmethod
    def public_status(rec: dict) -> dict:
        """Status fürs Ersteller-UI (kein Geheimnis enthalten außer dem Token selbst)."""
        return {
            "token": rec.get('token'),
            "active": rec.get('active', False),
            "message_count": int(rec.get('message_count', 0)),
            "message_limit": int(rec.get('message_limit', DEFAULT_MESSAGE_LIMIT)),
        }
