# Wikimedia Commons Media Usage Tracker

Dieses Repository überwacht täglich die Nutzung mehrerer Wikimedia-Commons-Kategorien.

Aktuell konfigurierte Kategorien (`check_media_glamtools.py` → `CATEGORY_CONFIGS`):

- Media supplied by Universitätsarchiv St. Gallen (Label: **HSG**)
- Rahn Collection (Label: **Rahn**)
- Breitinger Collection (Label: **Breitinger**)

## Funktionsweise

Das Skript nutzt Browser-Automation (Selenium), um https://glamtools.toolforge.org/glamorgan.html aufzurufen und pro Kategorie automatisch auszuwerten:

- Automatisches Ausfüllen des Formulars (Kategorie, Depth, Jahr/Monat)
- Verwendung des jeweils **vorherigen Kalendermonats** (UTC) für konsistente Daten
- Warten auf vollständiges Laden der Ergebnisse inkl. „show all“-Erweiterung
- Speichern der Ergebnisse als HTML, Screenshot, JSON und Metadaten
- Ermittlung von Änderungen gegenüber dem vorherigen Lauf (neue/entfernte Dateien & Seiten)
- Optional (am 1. Tag eines Monats): Vergleich mit dem frühesten Report des Vormonats

Alle Kategorien werden mit einer gemeinsamen Browser-Session sequenziell abgearbeitet. Für jeden Lauf entsteht ein eigener Report-Ordner.

## Automatische Ausführung

Eine GitHub Action (`.github/workflows/check_media_glamtools.yml`) führt das Skript täglich um 2:00 Uhr UTC aus. Nach einem erfolgreichen Durchlauf werden Änderungen im `reports/`-Verzeichnis automatisch committed und mit einer zusammengefassten Änderungsschlagzeile pro Kategorie gepusht. Zusätzlich wird der komplette `reports/`-Ordner als Build-Artifact archiviert.

## Generierte Reports

Reports liegen nach Kategorien getrennt unter `reports/<Kategorie>/`. Jeder Lauf erzeugt einen Ordner nach dem Muster `YYYY-MM_timestamp_[±N]/`:

- `YYYY-MM` – Datensatzmonat (immer der vorherige Monat zur Ausführung)
- `timestamp` – Zeitpunkt des Abrufs (UTC)
- `[±N]` – Anzahl der Seiten-Nutzungsänderungen (neue + entfernte Seiten), z. B. `[+3]` oder `[0]`

Typische Inhalte eines Report-Ordners:

- `glamtools_results_*.html` – Vollständige GLAM-Tools-Ergebnisseite
- `glamtools_screenshot_*.png` sowie `latest_screenshot.png` – Screenshots (oberer Seitenbereich)
- `glamtools_data_*.json` – Extrahierte Tabellendaten inkl. Zusammenfassung, Datei- und Seitennutzung
- `metadata_*.json` – Metadaten zum Lauf (Kategorie, Zeitstempel, Diff-Übersicht etc.)
- `changes_summary.txt` – Vergleich zum unmittelbar vorherigen Report (Datei-, Seiten- und View-Deltas)
- `previous_month_summary.txt` – (optional) Vergleich mit dem frühesten Report des vorherigen Datensatzmonats
- `latest.html` – Kopie der Ergebnisseite für schnellen Zugriff

Außerdem wird ein laufübergreifender Überblick geschrieben: `reports/run_summary.json` enthält Zeitstempel, die Gesamtzahl aller Änderungen sowie eine pro Kategorie aufgeschlüsselte Übersicht der letzten Ausführung.

## Manuelle Ausführung

### Voraussetzungen

```bash
pip install -r requirements.txt
```

Erfordert einen installierten Chrome/Chromium-Browser. In lokalen Umgebungen kann es nötig sein, einen kompatiblen ChromeDriver bereitzustellen (die GitHub Action erledigt dies automatisch).

### Skript ausführen

```bash
python check_media_glamtools.py
```

Die Reports werden anschließend wie oben beschrieben aktualisiert.

## Report-Inhalte

Die Reports zeigen unter anderem:

- **Gesamtzahl der Dateien** sowie **verwendete Dateien** der Kategorie
- **View-Zahlen** pro Datei für den ausgewählten Monat
- **Seitennutzung**: Welche Wikipedia-/Wikimedia-Seiten welche Medien einsetzen
- **Differenzen** zu vorherigen Läufen (neue/entfallene Dateien & Seiten, View-Veränderungen)
- **Aggregierte Monatsvergleiche**, sofern Daten für den Vormonat vorliegen

## Anpassungen

- Neue Kategorien können durch Hinzufügen eines weiteren `CategoryConfig`-Eintrags in `check_media_glamtools.py` aufgenommen werden.
- Timeout- und Wartezeiten lassen sich pro Kategorie konfigurieren (`max_wait_seconds`, `initial_wait_seconds`).
- Für Debugging-Zwecke kann `setup_driver(headless=True)` auf `False` gesetzt werden, um den Browser sichtbar zu starten.
