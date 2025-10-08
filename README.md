# Wikimedia Commons Media Usage Tracker

Dieses Repository überwacht täglich die Nutzung von Medien aus der Wikimedia Commons-Kategorie "Media supplied by Universitätsarchiv St. Gallen".

## Funktionsweise

Das Skript nutzt Browser-Automation (Selenium) um https://glamtools.toolforge.org/glamorgan.html zu verwenden:
- Automatisches Ausfüllen des Formulars (Kategorie, Depth, Jahr/Monat)
- Warten auf vollständiges Laden der Ergebnisse (~1-2 Minuten)
- Speichern der Ergebnisse als HTML, Screenshot und JSON

Jeder Durchlauf erstellt einen eigenen timestamped Ordner unter `reports/YYYY-MM_timestamp/`.

## Automatische Ausführung

Eine GitHub Action führt das Skript täglich um 2:00 Uhr UTC aus.

### Generierte Reports

Für jeden Durchlauf wird ein Ordner erstellt: `reports/YYYY-MM_timestamp/`

Enthält:
- `glamtools_results_*.html` - Vollständige GLAM Tools Ergebnisseite
- `glamtools_screenshot_*.png` - Screenshot der Ergebnisse
- `glamtools_data_*.json` - Extrahierte Tabellendaten (Views pro Datei)
- `metadata_*.json` - Metadaten zum Durchlauf
- `latest.html` und `latest_screenshot.png` - Kopien für schnellen Zugriff

## Manuelle Ausführung

### Voraussetzungen

```bash
pip install -r requirements.txt
```

Benötigt Chrome/Chromium Browser (wird von Selenium automatisch verwaltet).

### Skript ausführen

```bash
python check_media_glamtools.py
```

## Report-Inhalte

Die Reports zeigen:

- **Gesamtzahl Dateien** in der Kategorie
- **View-Zahlen** pro Datei für den gewählten Monat
- **Nutzung auf Seiten**: Welche Wikipedia/Wiki-Seiten verwenden welche Bilder
- **Top-Dateien**: Nach Views sortiert
- **Statistiken**: Gesamtviews, verwendete vs. ungenutzte Dateien