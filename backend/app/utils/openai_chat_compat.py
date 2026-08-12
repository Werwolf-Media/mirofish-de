"""
OpenAI Chat Completions compatibility helpers.

Portiert aus dem Upstream-MiroFish (fix ontology provider compatibility),
angepasst für OpenRouter: Modell-Ids tragen dort ein Provider-Präfix
("openai/gpt-5-mini"), und neben der GPT-5-Familie brauchen auch die
o-Reasoning-Modelle (o1/o3/o4) die angepassten Parameter
(kein `temperature`, `max_completion_tokens` statt `max_tokens`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _base_model_name(model: Optional[str]) -> str:
    """Provider-Präfix abstreifen: 'openai/gpt-5-mini' -> 'gpt-5-mini'."""
    if not model:
        return ""
    return model.strip().lower().rsplit('/', 1)[-1]


def is_reasoning_family(model: Optional[str]) -> bool:
    """True für Modelle mit Reasoning-Parameter-Regeln (GPT-5, o1/o3/o4)."""
    m = _base_model_name(model)
    if m.startswith("gpt-5"):
        return True
    return m in ("o1", "o3", "o4") or m.startswith(("o1-", "o3-", "o4-"))


def create_chat_completion(
    client: Any,
    *,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Chat-Completion mit modell-spezifischen Request-Parametern.

    - Reasoning-Familie: kein `temperature`, `max_completion_tokens`
    - Alle anderen Modelle/Provider: unverändertes Legacy-Format
    - Provider-Fehler werden unverändert durchgereicht
    """
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    if response_format is not None:
        kwargs["response_format"] = response_format

    reasoning = is_reasoning_family(model)

    if temperature is not None and not reasoning:
        kwargs["temperature"] = temperature

    if max_tokens is not None:
        if reasoning:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

    return client.chat.completions.create(**kwargs)


def extract_chat_completion_text(response: Any) -> str:
    """Text aus der Response ziehen — robust über alle SDK-Content-Formen
    (str, None, Liste von Text-Parts)."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""

    message = getattr(choices[0], "message", None)
    if message is None:
        return ""

    content = getattr(message, "content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text_obj = item.get("text")
                if isinstance(text_obj, dict):
                    text_obj = text_obj.get("value")
                if isinstance(text_obj, str):
                    chunks.append(text_obj)
                elif isinstance(item.get("content"), str):
                    chunks.append(item["content"])
                continue

            text_obj = getattr(item, "text", None)
            if isinstance(text_obj, dict):
                text_obj = text_obj.get("value")
            if isinstance(text_obj, str):
                chunks.append(text_obj)
                continue

            content_obj = getattr(item, "content", None)
            if isinstance(content_obj, str):
                chunks.append(content_obj)

        return "".join(chunks).strip()

    return str(content or "")
