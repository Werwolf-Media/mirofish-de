"""
Modell-Wächter: prüft das konfigurierte Simulations-Modell auf bekannte
Problemklassen und liefert strukturierte Warnungen.

Codes (Übersetzung übernimmt das Frontend via i18n, fürs Log gibt es
deutsche Klartexte):
  reasoning  -> Reasoning-Modell, inkompatibel mit MiroFish (Parameter-Quirks,
                versteckte Denk-Tokens explodieren bei tausenden Agent-Calls)
  expensive  -> Bekannt teures Modell; ein Run kann zweistellige EUR kosten
  chinese    -> Modell neigt zu chinesischen Ausgaben trotz Sprachdirektive
"""

RECOMMENDED_MODEL = 'openai/gpt-4o-mini'

# Substrings, die auf Reasoning-Modelle hindeuten (nach Provider-Präfix egal)
_REASONING_MARKERS = (
    '/o1', '/o3', '/o4', 'o1-', 'o3-', 'o4-',
    'gpt-5', 'deepseek-r1', 'qwq', '-thinking', 'grok-4',
)

# Teure Modelle (nur relevant als Simulations-Hauptmodell mit tausenden Calls)
_EXPENSIVE_MARKERS = (
    'gpt-4o', 'gpt-4-turbo', 'gpt-4.1', 'chatgpt-4o',
    'claude-opus', 'claude-sonnet', 'claude-3.5-sonnet', 'claude-3-5-sonnet',
    'gemini-2.5-pro', 'gemini-pro-1.5', 'mistral-large',
)

# Ausnahmen: kleine/billige Varianten, die einen teuren Marker enthalten
_CHEAP_MARKERS = ('mini', 'nano', 'lite', 'flash', 'haiku', 'small')

# Modelle mit bekannter Neigung zu chinesischer Ausgabe
_CHINESE_MARKERS = ('qwen', 'deepseek', 'glm-', 'minimax', 'kimi', 'yi-', 'ernie', 'hunyuan')

_LOG_TEXT = {
    'reasoning': (
        "'{model}' ist ein Reasoning-Modell — läuft über den Kompatibilitäts-Layer, "
        "aber versteckte Denk-Tokens verteuern jeden Agent-Call erheblich. "
        f"Empfohlen: {RECOMMENDED_MODEL}"
    ),
    'expensive': (
        "'{model}' ist ein teures Modell — ein Simulations-Run kann zweistellige "
        f"EUR-Beträge kosten. Empfohlen: {RECOMMENDED_MODEL}"
    ),
    'chinese': (
        "'{model}' neigt zu chinesischsprachiger Ausgabe trotz Sprachdirektive. "
        f"Empfohlen: {RECOMMENDED_MODEL}"
    ),
}


def check_model(model: str) -> list:
    """
    Prüft einen Modellnamen und gibt eine Liste von Warnungen zurück:
    [{"code": "reasoning", "level": "error", "model": "..."}]
    level: "error" = wird sehr wahrscheinlich nicht funktionieren,
           "warning" = funktioniert, aber teuer/riskant.
    """
    warnings = []
    if not model or not isinstance(model, str):
        return warnings
    m = model.strip().lower()

    # Seit dem Kompat-Layer (openai_chat_compat) laufen Reasoning-Modelle
    # technisch — aber versteckte Denk-Tokens verteuern jeden Agent-Call,
    # daher weiterhin Warnung (nur nicht mehr als harter Fehler)
    if any(marker in m for marker in _REASONING_MARKERS):
        warnings.append({'code': 'reasoning', 'level': 'warning', 'model': model})

    is_cheap_variant = any(marker in m for marker in _CHEAP_MARKERS)
    if not is_cheap_variant and any(marker in m for marker in _EXPENSIVE_MARKERS):
        warnings.append({'code': 'expensive', 'level': 'warning', 'model': model})

    if any(marker in m for marker in _CHINESE_MARKERS):
        warnings.append({'code': 'chinese', 'level': 'warning', 'model': model})

    return warnings


def log_text(warning: dict) -> str:
    """Deutscher Klartext für Backend-Logs."""
    template = _LOG_TEXT.get(warning.get('code'), "Modell-Warnung: {model}")
    return template.format(model=warning.get('model', '?'))
