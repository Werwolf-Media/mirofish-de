"""
OpenRouter-Kostenmessung
========================

Liest den kumulativen USD-Verbrauch des OpenRouter-Kontos. Differenz zweier
Snapshots (vor/nach einem Run) = echte Kosten dieses Runs – inkl. der
Simulations-Subprozesse, da derselbe API-Key genutzt wird.

Nur aktiv, wenn LLM_BASE_URL auf OpenRouter zeigt; sonst None (Kosten unbekannt).
Stdlib-urllib, keine zusätzliche Dependency. Header bewusst ASCII.
"""

import json
import urllib.request

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.cost')

_USER_AGENT = "MiroFish/1.0 OpenRouter-Cost"


def _is_openrouter() -> bool:
    base = (Config.LLM_BASE_URL or '').lower()
    return 'openrouter' in base and bool(Config.LLM_API_KEY)


def _get(url: str, timeout: int = 6):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {Config.LLM_API_KEY}",
        "User-Agent": _USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def get_usage():
    """
    Kumulativer USD-Verbrauch (monoton steigend) oder None.
    """
    if not _is_openrouter():
        return None
    # Primär: /credits -> data.total_usage
    try:
        data = _get("https://openrouter.ai/api/v1/credits")
        usage = data.get('data', {}).get('total_usage')
        if usage is not None:
            return float(usage)
    except Exception as e:
        logger.warning(f"OpenRouter /credits fehlgeschlagen: {e}")
    # Fallback: /auth/key -> data.usage
    try:
        data = _get("https://openrouter.ai/api/v1/auth/key")
        usage = data.get('data', {}).get('usage')
        if usage is not None:
            return float(usage)
    except Exception as e:
        logger.warning(f"OpenRouter /auth/key fehlgeschlagen: {e}")
    return None
