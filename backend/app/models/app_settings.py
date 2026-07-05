"""
App-weite Laufzeit-Einstellungen (Admin-Bereich).

Erlaubt es, das LLM-Modell und den Kosten-Deckel zur Laufzeit zu ändern,
ohne die .env anzufassen und das Backend neu zu starten. Gespeichert als
JSON unter uploads/app_settings.json (gleiches Muster wie BillingManager).
"""

import os
import json
import threading

from ..config import Config

_lock = threading.Lock()

SETTINGS_PATH = os.path.join(Config.UPLOAD_FOLDER, 'app_settings.json')

# Erlaubte Schlüssel + einfache Validierung
_ALLOWED_KEYS = {'llm_model', 'max_cost_eur'}


class AppSettings:
    """Laufzeit-Overrides; Fallback ist immer die .env (Config)."""

    @classmethod
    def get(cls) -> dict:
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @classmethod
    def set(cls, fields: dict) -> dict:
        with _lock:
            data = cls.get()
            for key, value in (fields or {}).items():
                if key not in _ALLOWED_KEYS:
                    continue
                if value is None or value == '':
                    # Leerer Wert = Override entfernen -> zurück zur .env
                    data.pop(key, None)
                else:
                    data[key] = value
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            tmp = SETTINGS_PATH + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, SETTINGS_PATH)
            return data

    # --- Bequeme Zugriffe mit Config-Fallback ---

    @classmethod
    def llm_model(cls):
        """Modell-Override oder None (dann gilt Config.LLM_MODEL_NAME)."""
        value = cls.get().get('llm_model')
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @classmethod
    def effective_llm_model(cls) -> str:
        return cls.llm_model() or Config.LLM_MODEL_NAME

    @classmethod
    def max_cost_eur(cls) -> float:
        """Kosten-Deckel in EUR (Override oder .env-Wert); 0 = deaktiviert."""
        value = cls.get().get('max_cost_eur')
        try:
            if value is not None:
                return max(0.0, float(value))
        except (TypeError, ValueError):
            pass
        return max(0.0, Config.MAX_COST_EUR)
