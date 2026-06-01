"""
Deutsche Quellen (Opt-in)
=========================

Optionaler Abruf aktueller deutscher Nachrichtenquellen passend zur
Simulationsanforderung. Wird nur ausgeführt, wenn der Nutzer das Opt-in
"Deutsche Quellen einbeziehen" aktiviert.

Bewusst ohne externe Abhängigkeit und ohne API-Schlüssel umgesetzt:
Es wird der öffentliche Google-News-RSS-Such-Feed genutzt (deutschsprachig,
Region DE). Der abgerufene Text wird als zusätzliches Seed-Material an die
hochgeladenen Dokumente angehängt und durchläuft anschließend die normale
Ontologie- und Graph-Pipeline.

Stolperfalle (siehe Projekt-Konventionen): HTTP-Header müssen ASCII sein.
Der Suchbegriff steht URL-codiert in der URL, nicht im Header.
"""

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ..utils.logger import get_logger

logger = get_logger('mirofish.sources')

# Öffentlicher, suchbasierter RSS-Feed (kein API-Key nötig)
_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=de&gl=DE&ceid=DE:de"

# ASCII-only User-Agent (Umlaute/Em-Dash würden urllib/Node-fetch crashen)
_USER_AGENT = "MiroFish/1.0 (+https://github.com/Werwolf-Media/mirofish-de) German-Sources"

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Einfaches Entfernen von HTML-Tags aus RSS-Beschreibungen."""
    if not text:
        return ""
    cleaned = _TAG_RE.sub(" ", text)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _build_query(requirement: str, max_len: int = 200) -> str:
    """Aus der Simulationsanforderung einen kompakten Suchbegriff bauen."""
    q = (requirement or "").strip().replace("\n", " ")
    q = re.sub(r"\s+", " ", q)
    if len(q) > max_len:
        q = q[:max_len]
    return q


class GermanSourcesService:
    """Holt aktuelle deutsche Nachrichten passend zum Simulationsthema."""

    @staticmethod
    def fetch(requirement: str, max_items: int = 8, timeout: int = 10):
        """
        Args:
            requirement: Simulationsanforderung (wird als Suchbegriff genutzt)
            max_items: maximale Anzahl Artikel
            timeout: HTTP-Timeout in Sekunden

        Returns:
            (text, items):
              text  – formatierter deutscher Textblock (oder "" bei Fehler/leer)
              items – Liste von Dicts {title, source, published, summary, link}
        """
        query = _build_query(requirement)
        if not query:
            return "", []

        url = _GOOGLE_NEWS_RSS.format(query=urllib.parse.quote(query))

        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except Exception as e:  # Netzwerk/Timeout/Block – niemals die Pipeline brechen
            logger.warning(f"Deutsche Quellen: Abruf fehlgeschlagen: {e}")
            return "", []

        try:
            root = ET.fromstring(raw)
        except Exception as e:
            logger.warning(f"Deutsche Quellen: RSS-Parsing fehlgeschlagen: {e}")
            return "", []

        items = []
        for item in root.iterfind(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            published = (item.findtext("pubDate") or "").strip()
            summary = _strip_html(item.findtext("description") or "")
            # Google News packt die Quelle separat in <source>
            source_el = item.find("source")
            source = (source_el.text.strip() if source_el is not None and source_el.text else "")
            if not title:
                continue
            items.append({
                "title": title,
                "source": source,
                "published": published,
                "summary": summary,
                "link": link,
            })
            if len(items) >= max_items:
                break

        if not items:
            return "", []

        text = GermanSourcesService._format(query, items)
        logger.info(f"Deutsche Quellen: {len(items)} Artikel zu '{query[:60]}' eingebunden")
        return text, items

    @staticmethod
    def _format(query: str, items: list) -> str:
        """Artikel als zusammenhängenden Seed-Text aufbereiten."""
        lines = [
            "=== Aktuelle deutsche Quellen (automatisch eingebunden) ===",
            f"Suchthema: {query}",
            "",
        ]
        for i, it in enumerate(items, 1):
            head = f"{i}. {it['title']}"
            meta = " — ".join(filter(None, [it.get("source"), it.get("published")]))
            lines.append(head)
            if meta:
                lines.append(f"   Quelle: {meta}")
            if it.get("summary"):
                lines.append(f"   {it['summary']}")
            lines.append("")
        return "\n".join(lines)
