# Monitor-Preistracker

Ruft täglich die Preise deiner Monitore bei mehreren Anbietern ab, speichert den Verlauf und zeigt ihn auf einer Webseite an.

```
monitors.json            welche Monitore, Zielpreise und Angebots-URLs
scraper/fetch_prices.py  Preisabruf (läuft täglich in GitHub Actions)
data/prices.json         gespeicherter Preisverlauf (wird automatisch ergänzt)
index.html               Oberfläche, liest data/prices.json
.github/workflows/       täglicher Zeitplan
```

## Einrichten (ca. 10 Minuten, kostenlos)

1. Neues GitHub-Repository anlegen und alle Dateien hochladen.
2. **Settings → Pages**: Quelle „Deploy from a branch“, Branch `main`, Ordner `/ (root)`. Danach ist die Seite unter `https://DEIN-NAME.github.io/REPO/` erreichbar.
3. **Settings → Actions → General → Workflow permissions**: „Read and write permissions“ aktivieren.
4. **Actions → Preise abrufen → Run workflow** startet den ersten Abruf. Danach läuft er täglich um 06:00 UTC von selbst.

Lokal testen: `pip install -r requirements.txt`, `python scraper/fetch_prices.py`, dann `python -m http.server` und `http://localhost:8000` öffnen.

## Monitore und Anbieter hinzufügen

In `monitors.json` pro Monitor einen Eintrag mit Produktseiten der Anbieter anlegen. Eine Produktseiten-URL pro Anbieter, keine Suchseiten.

```json
{"id": "acer", "name": "Acer Predator X27U F5", "spec": "26,5 Zoll, QD-OLED, 500 Hz", "target": 550,
 "offers": [{"shop": "MediaMarkt", "url": "https://…"},
            {"shop": "Notebooksbilliger", "url": "https://…", "selector": ".product-price"}]}
```

`"pin": true` zeigt den Monitor groß oben an. Der optionale `selector` (CSS) hilft bei Seiten ohne maschinenlesbare Preisdaten.

## Benachrichtigung bei Zielpreis (optional)

1. In der App ntfy ([ntfy.sh](https://ntfy.sh)) ein Thema mit schwer erratbarem Namen abonnieren.
2. In GitHub unter **Settings → Secrets → Actions** das Secret `NTFY_TOPIC` mit diesem Namen anlegen.

Solange der Preis unter dem Ziel liegt, kommt täglich eine Nachricht.

## Wichtig

- **Nicht jeder Shop liefert Preise ab.** Große Shops (Amazon, MediaMarkt, Preisvergleiche) blockieren automatische Abrufe oft. Fehler stehen unten auf der Seite. Dann hilft ein `selector`, ein anderer Anbieter oder der Weg über eine offizielle Schnittstelle (z. B. Amazon-Partnerprogramm).
- **Nutzungsbedingungen beachten.** Das Skript hält robots.txt ein und ruft jede Seite nur einmal pro Tag ab. Prüfe trotzdem die Bedingungen des jeweiligen Anbieters. Preisvergleiche wie Geizhals und Idealo sind für automatisches Auslesen meist nicht vorgesehen.
- Die Startdaten in `data/prices.json` stammen aus einer manuellen Recherche. Sie werden vom ersten Lauf an um echte Abrufe ergänzt.
- Nach 60 Tagen ohne Aktivität pausiert GitHub geplante Workflows. Dann einmal unter Actions wieder aktivieren.
