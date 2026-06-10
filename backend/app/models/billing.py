"""
Abrechnungs-Store
=================

Ein Datensatz pro Run (Projekt) unter uploads/billing/<project_id>.json.
Hält Echtkosten (OpenRouter-Saldo-Delta), Abrechnungspreis und Projektname.
Abhängigkeitsfrei (nur Config), Muster wie ShareTokenManager.
"""

import os
import json
from datetime import datetime, timezone

from ..config import Config


class BillingManager:
    BILLING_DIR = os.path.join(Config.UPLOAD_FOLDER, 'billing')

    @classmethod
    def _ensure_dir(cls):
        os.makedirs(cls.BILLING_DIR, exist_ok=True)

    @classmethod
    def _path(cls, project_id: str) -> str:
        return os.path.join(cls.BILLING_DIR, f"{project_id}.json")

    @classmethod
    def _save(cls, rec: dict):
        cls._ensure_dir()
        with open(cls._path(rec['project_id']), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

    @classmethod
    def get(cls, project_id: str):
        path = cls._path(project_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def start(cls, project_id: str, project_name: str, requirement: str, usage_start):
        """Run-Beginn: Datensatz anlegen (oder usage_start setzen)."""
        rec = cls.get(project_id) or {
            "project_id": project_id,
            "project_name": project_name or "",
            "requirement": requirement or "",
            "simulation_id": "",
            "report_id": "",
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": "",
            "billing_price_eur": float(getattr(Config, 'DEFAULT_BILLING_PRICE_EUR', 50.0)),
            "cost_usd": 0.0,
            "usage_start": None,
            "usage_end": None,
        }
        rec["usage_start"] = usage_start
        if requirement and not rec.get("requirement"):
            rec["requirement"] = requirement
        cls._save(rec)
        return rec

    @classmethod
    def finish(cls, project_id: str, report_id: str, simulation_id: str, usage_end):
        """Run-Ende: usage_end + Kosten festhalten."""
        rec = cls.get(project_id)
        if not rec:
            rec = {
                "project_id": project_id, "project_name": "", "requirement": "",
                "simulation_id": "", "report_id": "", "status": "running",
                "created_at": datetime.now(timezone.utc).isoformat(), "completed_at": "",
                "billing_price_eur": float(getattr(Config, 'DEFAULT_BILLING_PRICE_EUR', 50.0)),
                "cost_usd": 0.0, "usage_start": None, "usage_end": None,
            }
        rec["report_id"] = report_id or rec.get("report_id", "")
        rec["simulation_id"] = simulation_id or rec.get("simulation_id", "")
        rec["usage_end"] = usage_end
        rec["status"] = "completed"
        rec["completed_at"] = datetime.now(timezone.utc).isoformat()
        start = rec.get("usage_start")
        if isinstance(start, (int, float)) and isinstance(usage_end, (int, float)):
            rec["cost_usd"] = max(0.0, float(usage_end) - float(start))
        cls._save(rec)
        return rec

    @classmethod
    def update(cls, project_id: str, fields: dict):
        rec = cls.get(project_id)
        if not rec:
            return None
        if 'project_name' in fields and fields['project_name'] is not None:
            rec['project_name'] = str(fields['project_name'])[:200]
        if 'billing_price_eur' in fields and fields['billing_price_eur'] is not None:
            try:
                price = float(fields['billing_price_eur'])
            except (TypeError, ValueError):
                price = rec.get('billing_price_eur', 0.0)
            rec['billing_price_eur'] = max(0.0, min(500.0, price))
        cls._save(rec)
        return rec

    @classmethod
    def list(cls):
        cls._ensure_dir()
        out = []
        for name in os.listdir(cls.BILLING_DIR):
            if not name.endswith('.json'):
                continue
            try:
                with open(os.path.join(cls.BILLING_DIR, name), 'r', encoding='utf-8') as f:
                    out.append(json.load(f))
            except Exception:
                continue
        out.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        return out
