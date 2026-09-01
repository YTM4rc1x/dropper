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
   - ha a nyertes `YTM4rc1x` (figyelt nyertesek listája a
     `WATCHED_WINNERS`-ben a script tetején), elmenti a nyerést a
     `YTM4rc1x.txt` fájlba (dátum, óra:perc, skin, ár),
   - **Eddig nyert pénz**: a figyelt nyertes összes elmentett nyereményét
     összeadja, és minden körben kiírja (`[INFO] Eddig nyert pénz : 12,34 €`).
     Indításkor a meglévő `YTM4rc1x.txt` fájlból betölti az
     eddigi összeget (újraindítás után sem nullázódik), és minden új
     elmentett nyeréssel hozzáadja az árhoz.
   - **frissíti az oldalt és újra belép** a következő körben.
   ESC-re leáll (ha `ABORT_ON_ESC = True`). A konzol minden nyertes után
   törlődik, így csak a legfrissebb nyertes látszik.

## Jelenlegi nyeremény kiírása + minimum skin-ár
- Minden kör elején a script kiírja a **jelenlegi (még nyerhető) skin nevét
  és árát**: `[SKIN] Jelenlegi nyeremény: AK-47 | Aphrodite – 37,55 €`.
  Forrás sorrend: `case-roll-won-item-*` testid-ek, ha azok üresek, akkor a
  csatlakozás gomb körüli kártya szövege (JS fallback, az első "X EUR"
  értéket veszi ki a gomb szövegét kivágva).
- Indításkor megadhatod a minimum nyeremény-árat (EUR, pl. `5` vagy `10,5`).
  A **döntés azonnal a kör elején** történik, és a kör fejlécében látszik:
  - ha az ár **>= minimum** → a fejléc a szokásos
    `KÖR #X – belépés a giveawaybe`, és a bot a célidő elérésénél belép;
  - ha az ár **< minimum** → a kör fejléce már az elején
    `KÖR #X – NEM LÉP BE (a skin ára < minimum 38,00 €)`, és a bot a kör
    végéig (a nyertes kipörgéséig) vár, nem kattint, a nyertest
    kiírja/menti, aztán tovább a következőre;
  - ha a kör elején nem olvasható az ár (pl. a giveaway még nem indult el)
    → a döntés a belépési pillanatban történik; ha akkor sem olvasható,
    belép (biztonsági alaphelyzet, `[WARN]`-rel).
- Fontos: a minimum a **lefelső határ** – pl. minimum 37-nél a 37,55 €-os
  skin BELÉP (mert 37,55 >= 37). Ha azt a skint is ki akarod zárni, 38-ra
  (vagy 37,56-ra) állítsd a minimumot.

## Konzol színezés
- A `[TAG]-ek` (pl. `[INFO]`, `[SKIN]`, `[TIME]`, `[JOIN]`, `[ERROR]`)
  színesek: minden tag egy saját színt kap (infó cián, skin félkövér cián,
  időzítő zöld, hiba félkövér piros stb.).
- Működik **VSCode terminálban** és **sima Windows konzolban** (cmd,
  PowerShell, Windows Terminal – Windows 10+; a script indításkor
  automatikusan bekapcsolja a Windows ANSI/VT színeket).
- Ha a színeket kikapcsolnád (pl. régebbi Windows-on furcsa karakterek
  jönnek), a `scraper.py` tetején: `ENABLE_COLORS = False`.

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
- `ENABLE_COLORS` – konzol színezés be/kikapcsolása (alapértelmezés: be).
- `OPERA_GX_PATH` – ha nem találná automatikusan, add meg környezeti változóval:
  ```bat
  set OPERA_GX_PATH="C:\Users\Marci\AppData\Local\Programs\Opera GX\opera.exe"
  python scraper.py
  ```
