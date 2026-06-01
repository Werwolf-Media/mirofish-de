<div align="center">

# 🐟 MiroFish — Alles vorhersagen

**KI-Prognose-Engine mit Multi-Agenten-Schwarmintelligenz**
Deutsche Ausgabe · bereitgestellt von **Werwolf Media**

[English](./README.md) | [中文文档](./README-ZH.md) | [Deutsch](./README-DE.md)

</div>

## ⚡ Überblick

**MiroFish** ist eine KI-Prognose-Engine auf Basis von Multi-Agenten-Technologie.
Aus „Seed"-Informationen aus der realen Welt (z. B. aktuelle Nachrichten,
Gesetzentwürfe oder Marktsignale) baut das System automatisch eine hochauflösende,
parallele digitale Welt. Darin interagieren tausende Agenten mit eigener
Persönlichkeit, Langzeitgedächtnis und Verhaltenslogik und durchlaufen eine soziale
Entwicklung. Aus der „Vogelperspektive" lassen sich Variablen einspielen, um
Zukunftsverläufe durchzuspielen — **die Zukunft im digitalen Sandkasten proben und
Entscheidungen nach unzähligen Simulationen treffen.**

> Du lädst nur hoch: Seed-Material (z. B. einen Bericht oder eine Nachricht) und
> beschreibst deine Prognosefrage in natürlicher Sprache.
> MiroFish liefert: einen detaillierten Prognosebericht und eine interaktive,
> hochauflösende digitale Welt.

## 🇩🇪 Diese deutsche Ausgabe

Dieser Fork von [MiroFish](https://github.com/666ghj/MiroFish) ist für den deutschen
Markt aufbereitet:

- **Vollständig deutsche Oberfläche** (`locales/de.json`) — Deutsch ist Standardsprache.
- **Deutsche KI-Ausgabe** — Personas, Simulationskonfiguration, Ontologie und Berichte
  werden auf Deutsch generiert (über `get_language_instruction()`).
- **Deutsche Beispiel-Seeds** im Ordner [`beispiel-seeds/`](./beispiel-seeds/) zum
  sofortigen Ausprobieren.
- **Opt-in „Deutsche Quellen einbeziehen"** — auf der Startseite anhakbar. Ist es
  aktiv, holt MiroFish vor der Simulation aktuelle deutsche Nachrichten passend zum
  Prompt (öffentlicher Google-News-RSS, kein API-Schlüssel nötig) und hängt sie als
  zusätzliches Seed-Material an die hochgeladenen Dokumente an. Standardmäßig **aus**.
- **Co-Branding** Werwolf Media (Logo + Favicon).

Die Sprache lässt sich oben rechts jederzeit umstellen (Deutsch / English / 中文).

## 🚀 Installation (Mac mini / Apple Silicon)

Voraussetzung: Node.js ≥ 18. Homebrew oder Docker sind **nicht** nötig.

```bash
git clone https://github.com/Werwolf-Media/mirofish-de.git
cd mirofish-de
bash setup-mac.sh          # installiert uv + Python 3.12 + alle Dependencies
```

Anschließend die beiden Schlüssel in `.env` eintragen:

- `LLM_API_KEY` — OpenAI-kompatibler Schlüssel (z. B. [OpenRouter](https://openrouter.ai))
- `ZEP_API_KEY` — Memory-Graph, kostenloser Tarif unter [app.getzep.com](https://app.getzep.com)

Starten:

```bash
export PATH="$HOME/.local/bin:$PATH"   # falls uv nicht auf PATH ist
npm run dev
```

Dann im Browser öffnen: **http://localhost:3100**

> Für den ersten Durchlauf den *Benutzerdefinierten Modus* mit wenigen Runden
> (z. B. 20–40) wählen — das hält Kosten und Fehlerrisiko niedrig.

## 🧪 Schnelltest

1. Eine Datei aus [`beispiel-seeds/`](./beispiel-seeds/) hochladen.
2. Den vorgeschlagenen Prompt aus der Datei in das Feld *Simulations-Prompt* kopieren.
3. **Engine starten** und den Bericht ansehen.

## 📄 Lizenz

MiroFish steht unter **AGPL-3.0**. Diese deutsche Ausgabe veröffentlicht ihre
Änderungen entsprechend offen. Bei einem späteren Betrieb als gehosteter Dienst
(„anmieten") ist gemäß AGPL §13 der Quellcode inklusive Änderungen für Nutzer
bereitzustellen.
