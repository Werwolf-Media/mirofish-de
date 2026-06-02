"""
KI-Onboarding-Assistent
=======================

Dialogbasierter Assistent, der aus einer groben Idee (Text + optional Dokument)
über wenige Rückfragen einen optimalen MiroFish-Input erzeugt:
einen strukturierten `simulation_requirement` + ein reiches `seed_text`-Dokument.

Stateless: das Frontend sendet bei jedem Turn die ganze Konversation.
Nutzt ein konfigurierbares (i. d. R. stärkeres) Modell über denselben
OpenRouter-Key (Config.WIZARD_MODEL_NAME).
"""

import os
import re
import json
import tempfile
import traceback

from flask import request, jsonify

from . import wizard_bp
from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction
from ..utils.logger import get_logger
from ..utils.file_parser import FileParser
from ..services.text_processor import TextProcessor

logger = get_logger('mirofish.wizard')

MAX_MESSAGES = 40
MAX_DOC_CHARS = 8000

# Few-Shot-Beispiele (Gold-Standard-Prompts) einmal beim Import laden
_SEEDS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'beispiel-seeds')
_EXAMPLE_FILES = [
    'produktlaunch-elektro-kleinwagen.md',
    'gesetzentwurf-heizungsfoerderung.md',
    'lokaler-einzelhandel-innenstadt.md',
]


def _load_examples() -> str:
    parts = []
    for name in _EXAMPLE_FILES:
        path = os.path.join(_SEEDS_DIR, name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                parts.append(f.read().strip())
        except Exception:
            continue
    return "\n\n=====\n\n".join(parts)


_EXAMPLES = _load_examples()


def allowed_file(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


def _build_system_prompt(document_text: str = "") -> str:
    doc_block = ""
    if document_text:
        doc_block = (
            "\n\n## Vom Nutzer bereitgestelltes Dokument (Auszug, als Kontext nutzen)\n"
            f"{document_text[:MAX_DOC_CHARS]}\n"
        )

    return f"""Du bist der Onboarding-Assistent von MiroFish – einer Simulation, die aus Seed-Material eine Social-Media-Welt mit tausenden KI-Agenten baut und Meinungs-/Marktdynamiken vorhersagt.

Deine Aufgabe: Aus der groben Idee des Nutzers durch WENIGE gezielte Rückfragen einen optimalen Simulations-Input erzeugen – einen Prompt UND ein reiches Seed-Dokument.

## Was einen optimalen Simulations-Prompt ausmacht (4 Säulen)
1. Expliziter Zeitraum (2–12 Wochen).
2. 4–6 KONKRETE, benannte Akteursgruppen.
3. 3–5 messbare Outcome-Fragen (z. B. Stimmungswandel, welche Argumente sich durchsetzen, wer mobilisiert, wo Konsens kippt).
4. 3–5 testbare, quantifizierte Szenario-Variablen (z. B. Rabattaktion, kritischer Testbericht, Wettbewerber-Schritt, Politikänderung).

## Harte Regel zu Akteuren
Akteure müssen KONKRETE, real handelnde Subjekte sein, die auf Social Media posten/reagieren können: konkrete Personen, Firmen, Institutionen, Medien, Behörden, Verbands-/Gruppenvertreter.
NIEMALS Abstrakta wie „die Meinung", „der Trend", „Befürworter/Gegner", „Stimmung".

## Was ein gutes Seed-Dokument (seedText) enthält
- Ein datiertes, benanntes Auslöser-Ereignis.
- Benannte Akteure mit ihren konkreten Positionen/Aussagen.
- Hintergrund/Kontext (warum es JETZT relevant ist).
- Konkrete Zahlen (Preise, Budgets, Fristen, Reichweiten).
- 3–5 offene Variablen zum Testen.
Reich benannte Akteure verbessern direkt die Qualität der später generierten Personas.

## Gesprächspolitik
- Stelle höchstens 2–4 kurze Rückfragen, eine fokussierte Frage pro Turn.
- Sobald Thema, grober Zeitraum, einige konkrete Akteure und die Kernfrage bekannt sind: NICHT weiter ausfragen, sondern fertigstellen (status="ready").
- Erfinde fehlende plausible Details selbst sinnvoll, statt endlos nachzufragen.

## Antwortformat (PFLICHT)
Antworte AUSSCHLIESSLICH mit EINEM JSON-Objekt, ohne weiteren Text, ohne Markdown-Codeblock:
{{
  "status": "asking" oder "ready",
  "reply": "deine Nachricht an den Nutzer (Rückfrage ODER kurze Zusammenfassung des erstellten Inputs)",
  "simulationRequirement": "nur bei status=ready: der fertige, strukturierte Simulations-Prompt (sonst \\"\\")",
  "seedText": "nur bei status=ready: das reiche Seed-Dokument mit benannten Akteuren, Positionen, Zahlen, Variablen (sonst \\"\\")",
  "title": "nur bei status=ready: kurzer Projekttitel (sonst \\"\\")"
}}

## Gold-Standard-Beispiele (Struktur & Niveau nachahmen, NICHT kopieren)
{_EXAMPLES}
{doc_block}
{get_language_instruction()}"""


def _parse_json_loose(text: str) -> dict:
    """JSON aus LLM-Antwort robust extrahieren (auch ohne response_format-Unterstützung)."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def _sanitize_messages(raw) -> list:
    out = []
    if isinstance(raw, list):
        for m in raw[-MAX_MESSAGES:]:
            if not isinstance(m, dict):
                continue
            role = m.get('role')
            content = m.get('content')
            if role in ('user', 'assistant') and isinstance(content, str) and content.strip():
                out.append({"role": role, "content": content})
    return out


@wizard_bp.route('/chat', methods=['POST'])
def wizard_chat():
    """Dialog-Turn: ganze Konversation rein, JSON-Contract raus."""
    data = request.get_json(silent=True) or {}
    convo = _sanitize_messages(data.get('messages'))
    document_text = data.get('documentText', '')
    if not isinstance(document_text, str):
        document_text = ''

    if not convo:
        # Kein Nutzer-Input -> freundliche Aufforderung
        return jsonify({
            "success": True,
            "data": {"status": "asking", "reply": get_language_instruction(),
                     "simulationRequirement": "", "seedText": "", "title": ""}
        })

    system_prompt = _build_system_prompt(document_text)
    messages = [{"role": "system", "content": system_prompt}] + convo

    try:
        client = LLMClient(model=Config.WIZARD_MODEL_NAME)
    except ValueError as e:
        logger.error(f"Wizard: LLM nicht konfiguriert: {e}")
        return jsonify({"success": False, "error": "wizard_llm_unconfigured"}), 502

    try:
        raw = client.chat(messages=messages, temperature=0.4, max_tokens=4096)
        result = _parse_json_loose(raw)
    except Exception as e:
        logger.error(f"Wizard-Chat fehlgeschlagen: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"success": False, "error": "wizard_failed"}), 502

    status = result.get('status')
    if status not in ('asking', 'ready'):
        status = 'asking'

    return jsonify({
        "success": True,
        "data": {
            "status": status,
            "reply": str(result.get('reply', '') or ''),
            "simulationRequirement": str(result.get('simulationRequirement', '') or ''),
            "seedText": str(result.get('seedText', '') or ''),
            "title": str(result.get('title', '') or '')
        }
    })


@wizard_bp.route('/extract', methods=['POST'])
def wizard_extract():
    """Text aus einem hochgeladenen Dokument extrahieren (für den Gesprächskontext)."""
    uploaded = request.files.get('file')
    if not uploaded or not uploaded.filename:
        return jsonify({"success": False, "error": "no_file"}), 400
    if not allowed_file(uploaded.filename):
        return jsonify({"success": False, "error": "invalid_file_type"}), 400

    ext = os.path.splitext(uploaded.filename)[1].lower()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            uploaded.save(tmp.name)
            tmp_path = tmp.name
        text = FileParser.extract_text(tmp_path)
        text = TextProcessor.preprocess_text(text)
        if len(text) > MAX_DOC_CHARS:
            text = text[:MAX_DOC_CHARS]
        return jsonify({"success": True, "data": {"text": text, "filename": uploaded.filename}})
    except Exception as e:
        logger.error(f"Wizard-Extract fehlgeschlagen: {e}")
        return jsonify({"success": False, "error": "extract_failed"}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
