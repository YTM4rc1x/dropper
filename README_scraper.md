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
     (pl. `30s`, `1m`, `1m30s`, vagy tartomány: `1s-1m` -> minden körben
     véletlenszerűen a két érték között). Figyeli az élő visszaszámlálót, és
     akkor kattint a **Csatlakozás Nyereményjátékhoz** gombra, amikor a
     hátralévő idő eléri a célt (pl. `30s` = 30 mp hátralévőkor),
   - kiírja a **hátralévő időt** (mozgó időzítővel, nem új sorba írja),
   - amikor kipörgetik a nyertest, kiírja a **nyertes nevét** és a **nyert
     skin kategóriáját / nevét / árát** egy fix szélességű dobozban,
   - ha a nyertes `YTM4rc1x` vagy `1r4z1`, elmenti a nyerést a saját
     `YTM4rc1x.txt` / `1r4z1.txt` fájlba (dátum, óra:perc, skin, ár),
   - **Eddig nyert pénz**: a figyelt nyertesek összes elmentett nyereményét
     összeadja, és minden körben kiírja (`[INFO] Eddig nyert pénz : 12,34 €`).
     Indításkor a meglévő `YTM4rc1x.txt` / `1r4z1.txt` fájlokból betölti az
     eddigi összeget (újraindítás után sem nullázódik), és minden új
     elmentett nyeréssel hozzáadja az árhoz,
   - **frissíti az oldalt és újra belép** a következő körben.
   ESC-re leáll (ha `ABORT_ON_ESC = True`). A konzol minden nyertes után
   törlődik, így csak a legfrissebb nyertes látszik.

## Körök kihagyása (skip) – fix 1/1
A bot fixen **1/1** ritmusban játszik: 1 kör, majd 1 kihagyott (a
`SKIP_CFG` konstanssal a scraper.py tetején változtatható, `None` = sosem
hagy ki).
- A **kihagyott körben a bot NEM lép be a giveawaybe**: a belépési cél
  `-1s`-re áll, amit a visszaszámláló soha nem éri el, így a csatlakozás
  gombra **nem kattint**. A bot a kör végéig (a nyertes kipörgéséig) vár,
  a nyertest kiírja/elmenti (így a figyelt nyertesek kihagyott körben is
  rögzülnek), aztán frissít és tovább a következő körre.
- A konzol így jelzi: `KÖR #X – KIHAGYVA (ez a körben nem lép be)` +
  `[SKIP] Hátralévő idő: 00:02:25 (cél: -1s)`.

## Jelenlegi nyeremény kiírása + minimum skin-ár
- Minden kör elején a script kiírja a **jelenlegi (még nyerhető) skin nevét
  és árát**: `[SKIN] Jelenlegi nyeremény: AWP | Ice Coaled – 37,55 €`.
  Forrás sorrend: `case-roll-won-item-*` testid-ek, ha azok üresek, akkor a
  csatlakozás gomb körüli kártya szövege (JS fallback, az első "X EUR"
  értéket veszi ki a gomb szövegét kivágva).
- Indításkor megadhatod a minimum nyeremény-árat (EUR, pl. `5` vagy `10,5`).
  A belépési pillanatban a script kikeresi a skin árát:
  - ha az ár **>= minimum** → belép a giveawaybe
    (`[PRICE] AWP | Ice Coaled – 37,55 € >= minimum 37,00 € – belemegyek.`),
  - ha az ár **< minimum** → **nem lép be**: a kör végéig (a nyertes
    kipörgéséig) vár, a nyertest kiírja/menti, aztán tovább a következőre
    (`[PRICE] ... – 36,00 € < minimum 37,00 € – NEM lépek be...`),
  - ha az ár nem olvasható → belép (biztonsági alaphelyzet, `[WARN]`-rel).
- Fontos: a minimum a **lefelső határ** – pl. minimum 37-nél a 37,55 €-os
  skin BELÉP (mert 37,55 >= 37). Ha azt a skint is ki akarod zárni, 38-ra
  (vagy 37,56-ra) állítsd a minimumot.

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
