# scraper.py – Opera GX webscraper (keydrop amateur giveaway)

Ez a script a régi `clicker.py` helyett **webscraper stílusban** dolgozik:
nem a képernyőt figyeli (pyautogui/képfelismerés), hanem megnyit egy valódi
**Opera GX** böngészőt, és a böngésző DOM-ját olvassa/vezérli.

## Mit csinál most
1. Megnyitja az Opera GX-et (látható ablakban).
2. Betölti: `https://keydrop.com/hu/giveaways/amateur`
3. A további lépéseket a `run_scraper_logic()` függvénybe írom, amikor
   elmondod, mit kell az oldalon csinálni.

## Telepítés (saját gépen)
```bash
pip install -r requirements.txt
playwright install chromium     # Opera GX hiányában ez a tartalék böngésző
```

## Futtatás
```bash
python scraper.py
```
Ha nincs automatikusan megtalálva az Opera GX, add meg az útvonalát:
```bash
OPERA_GX_PATH="C:\Users\TeNeved\AppData\Local\Opera Software\Opera GX Stable\opera.exe" python scraper.py
```

## Fontosabb beállítások (scraper.py teteje)
- `HEADLESS = False` – látható Opera GX ablak (így kérted).
- `KEEP_BROWSER_OPEN = True` – nyitva hagyja az ablakot Enterig.
- `TARGET_URL` – az oldal, amit megnyit.
- `ABORT_ON_ESC` – ESC-re leáll (mint a régi clicker.py).
