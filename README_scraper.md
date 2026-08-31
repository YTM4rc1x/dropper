# scraper.py – Opera GX webscraper (csatlakozás a futó böngészőhöz, új lap)

Ez a script a régi `clicker.py` helyett **webscraper stílusban** dolgozik:
nem a képernyőt figyeli (pyautogui/képfelismerés), hanem **csatlakozik a már
futó Opera GX-hez** (Chrome DevTools Protocol), és abban **nyit egy új lapot**,
amit aztán közvetlenül vezérel/olvas.

## Mit csinál
1. Megpróbál csatlakozni a futó Opera GX-hez a `--remote-debugging-port` (9222)
   kapcsolóval.
2. Ha nincs ilyen, a script elindítja az Opera GX-et ugyanazon a porton (ugyanaz
   a profilod / bejelentkezésed), és abban nyitja az új lapot.
3. A meglévő ablakban új lapot nyit, betölti:
   `https://keydrop.com/hu/giveaways/amateur`
4. Folyamatos automata (`run_scraper_logic`):
   - indításkor **egyszer megkérdezi, hány mp hátralévőkor lépjen be**
     (pl. `30s`, `1m`, `1m30s`). Figyeli az élő visszaszámlálót, és akkor
     kattint a **Csatlakozás Nyereményjátékhoz** gombra, amikor a hátralévő
     idő eléri a célt (pl. `30s` = 30 mp hátralévőkor),
   - kiírja a **hátralévő időt** (mozgó időzítővel, nem új sorba írja),
   - amikor kipörgetik a nyertest, kiírja a **nyertes nevét** és a **nyert
     skin kategóriáját / nevét / árát** egy fix szélességű dobozban,
   - ha a nyertes `YTM4rc1x` vagy `1r4z1`, elmenti a nyerést a saját
     `YTM4rc1x.txt` / `1r4z1.txt` fájlba (dátum, óra:perc, skin, ár),
   - **frissíti az oldalt és újra belép** a következő körben.
   ESC-re leáll (ha `ABORT_ON_ESC = True`). A konzol minden nyertes után
   törlődik, így csak a legfrissebb nyertes látszik.

## Telepítés (saját gépen)
```bash
pip install -r requirements.txt
playwright install chromium     # Opera GX hiányában ez a tartalék böngésző
```

## Futtatás
```bash
python scraper.py
```

### A már megnyitott Opera GX-hez csatlakozás
A böngészőt **távoli vezérléssel** kell indítani, különben a script nem tud
rácsatlakozni (ilyenkor saját maga indít egyet). A Te gépeden:
```bat
"C:\Users\Marci\AppData\Local\Programs\Opera GX\opera.exe" --remote-debugging-port=9222
```
Ezután futtasd a `python scraper.py`-t – a script a futó ablakban nyit új lapot,
és a végén NEM zárja be a böngészőt.

## Fontosabb beállítások (scraper.py teteje)
- `REMOTE_DEBUG_PORT = 9222` – a CDP port.
- `ATTACH_TO_RUNNING = True` – először a futó böngészőhöz próbál csatlakozni.
- `HEADLESS = False` – látható ablak.
- `KEEP_BROWSER_OPEN = True` – ha mi indítottuk, nyitva hagyja Enterig.
- `TARGET_URL` – az oldal, amit megnyit.
- `OPERA_GX_PATH` – ha nem találná automatikusan, add meg környezeti változóval:
  ```bat
  set OPERA_GX_PATH="C:\Users\Marci\AppData\Local\Programs\Opera GX\opera.exe"
  python scraper.py
  ```
