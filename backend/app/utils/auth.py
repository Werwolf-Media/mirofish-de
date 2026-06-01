"""
Einfacher Zugriffsschutz (Login)
================================

Geteiltes Passwort (Config.APP_PASSWORD). Nach erfolgreichem Login erhält der
Client ein deterministisches Token (gesalzener SHA-256-Hash aus Passwort +
SECRET_KEY). Das Token wird bei jeder API-Anfrage im Header geprüft – das
rohe Passwort verlässt nach dem Login nie wieder Server oder Client.
"""

import hashlib
import hmac

from ..config import Config


def expected_token() -> str:
    """Erwartetes Zugriffstoken aus Passwort + SECRET_KEY ableiten."""
    raw = f"{Config.APP_PASSWORD}|{Config.SECRET_KEY}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def check_password(password: str) -> bool:
    """Passwort konstant-zeitlich gegen das konfigurierte Passwort prüfen."""
    if not isinstance(password, str):
        return False
    return hmac.compare_digest(password, Config.APP_PASSWORD or "")


def check_token(token: str) -> bool:
    """Vom Client gesendetes Token validieren."""
    if not isinstance(token, str) or not token:
        return False
    return hmac.compare_digest(token, expected_token())
