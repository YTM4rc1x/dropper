# scraper.py – Google Chrome webscraper (keydrop amateur giveaway)

Ez a script a régi `clicker.py` helyett **webscraper stílusban** dolgozik:
nem a képernyőt figyeli (pyautogui/képfelismerés), hanem megnyit egy valódi
**Google Chrome** böngészőt, és a böngésző DOM-ját olvassa/vezérli.

## Mit csinál most
1. Megnyitja a Google Chrome-ot (látható ablakban).
2. Betölti: `https://keydrop.com/hu/giveaways/amateur`
3. A további lépéseket a `run_scraper_logic()` függvénybe írom, amikor
   elmondod, mit kell az oldalon csinálni.

## Telepítés (saját gépen)
```bash
pip install -r requirements.txt
playwright install chromium     # Chrome hiányában ez a tartalék böngésző
```

## Futtatás
```bash
python scraper.py
```
Ha nincs automatikusan megtalálva a Chrome, add meg az útvonalát:
```bash
CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe" python scraper.py
```

## Fontosabb beállítások (scraper.py teteje)
- `HEADLESS = False` – látható Chrome ablak.
- `KEEP_BROWSER_OPEN = True` – nyitva hagyja az ablakot Enterig.
- `TARGET_URL` – az oldal, amit megnyit.
- `ABORT_ON_ESC` – ESC-re leáll (mint a régi clicker.py).
