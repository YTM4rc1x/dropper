"""
scraper.py – Webscraper stílusú keydrop automatizáló (Opera GX böngészővel)

A régi clicker.py a KÉPERNYŐT nézte (pyautogui / képfelismerés).
Ez a script ehelyett egy VALÓDI Opera GX böngészőhöz csatlakozik (CDP /
Chrome DevTools Protocol), és abban NYIT EGY ÚJ LAPOT, amit aztán közvetlenül
vezérel – tehát nem a képernyőt figyeli, hanem "webscraper" módon dolgozik.

HOGYAN MŰKÖDIK:
  1) Megpróbál csatlakozni a MÁR FUTÓ Opera GX-hez a --remote-debugging-port
     kapcsolóval (alapértelmezett: 9222).
  2) Ha nincs ilyen futó böngésző, a script elindítja az Opera GX-et a
     távoli vezérlő porttal (ugyanaz a profilod / bejelentkezésed), és abban
     nyitja az új lapot.
  3) A meglévő (default) ablakban nyit egy új lapot, és betölti az oldalt.

FUTTATÁS (saját gépen):
  1) pip install playwright
  2) playwright install chromium   (Opera GX hiányában ez a tartalék)
  3) python scraper.py

Ha a MÁR MEGNYITOTT Opera GX-edhez akarsz csatlakozni, indítsd így a kapcsolóval:
  "C:\\Users\\Marci\\AppData\\Local\\Programs\\Opera GX\\opera.exe" --remote-debugging-port=9222
"""

import os
import random
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeoutError

# ----------------------------------------------------------------------
# BEÁLLÍTÁSOK (ezeket nyugodtan átírhatod)
# ----------------------------------------------------------------------

TARGET_URL = "https://keydrop.com/hu/giveaways/contender"

# A távoli vezérlő (Chrome DevTools Protocol) portja.
# A futó Opera GX-nek ezen a porton kell figyelnie (--remote-debugging-port=...).
REMOTE_DEBUG_PORT = 9222
CDP_URL = f"http://localhost:{REMOTE_DEBUG_PORT}"

# Először a MÁR FUTÓ böngészőhöz próbál csatlakozni (CDP).
# Ha False, a script mindig új Opera GX-ET indít a porttal.
ATTACH_TO_RUNNING = True

# True = látható ablak (Opera GX), False = háttérben (headless).
HEADLESS = False

# Az indítás után ennyi mp-et vár, mielőtt nekiállna (debughoz hasznos).
STARTUP_WAIT = 3

# Oldal betöltésére adott maximális idő (ms).
PAGE_TIMEOUT = 60_000

# ESC-kilépés engedélyezése (mint a régi clicker.py-ban).
ABORT_ON_ESC = True

# Ha a script INDÍTOTTA a böngészőt: True esetén nyitva hagyja Enterig.
# Ha csak csatlakoztunk a futó böngészőhöz, azt SOHA nem zárjuk be.
KEEP_BROWSER_OPEN = True

# Ha meg van adva, ezt az Opera GX futtathatót használja (teljes útvonal).
# Üresen hagyva automatikusan keresi az alapértelmezett helyeken.
OPERA_GX_PATH = os.environ.get("OPERA_GX_PATH", "")

# ----------------------------------------------------------------------
# KONZOL SZÍNEZÉS (ANSI)
# ----------------------------------------------------------------------
# True = színes kimenet. A [TAG]-ek (pl. [INFO], [SKIN], [TIME]) színre
# festve jelennek meg. Működik: Windows 10+ (cmd/PowerShell/Windows
# Terminal), VSCode terminál, Linux. Régebbi Windows-on, ha furcsa
# karakterek (pl. "^[") bukkannak fel, állítsd False-ra (sima kimenet).
ENABLE_COLORS = True

# Tag -> ANSI szin. (9x = "fényes" változat, 1; = félkövér)
_TAG_COLORS = {
    "INFO":    "\033[96m",   # fényes cián
    "OK":      "\033[92m",   # fényes zöld
    "WAIT":    "\033[33m",   # sárga
    "TIME":    "\033[92m",   # fényes zöld
    "ENTRY":   "\033[36m",   # cián
    "JOIN":    "\033[1;92m", # félkövér zöld
    "SKIN":    "\033[1;96m", # félkövér cián
    "PRICE":   "\033[1;93m", # félkövér sárga
    "WIN":     "\033[1;94m", # félkövér kék
    "WINNER":  "\033[94m",   # kék
    "REFRESH": "\033[90m",   # szürke
    "RETRY":   "\033[33m",   # sárga
    "WARN":    "\033[93m",   # fényes sárga
    "ERROR":   "\033[1;91m", # félkövér piros
    "ESC":     "\033[95m",   # lila
    "PAUSE":   "\033[90m",
    "STEP":    "\033[90m",
    "KEY":     "\033[90m",
    "ARROW":   "\033[90m",
    "CLICK":   "\033[90m",
}
_COLOR_RESET = "\033[0m"
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _visible_len(s: str) -> int:
    """Látható hossz (az ANSI kódok nélkül) – a mozgó timer igazításához."""
    return len(_ANSI_RE.sub("", s))


def _paint(text: str) -> str:
    """
    A sor eleji [TAG]-re (vagy a külön sorokra) ANSI színt tesz.
    Ha ENABLE_COLORS = False vagy nincs ismert tag, visszatér a szöveggel.
    """
    if not ENABLE_COLORS:
        return text
    m = re.match(r"^\[([A-Z]+)\]", text)
    if m:
        color = _TAG_COLORS.get(m.group(1))
        if color:
            return f"{color}{text}{_COLOR_RESET}"
        return text
    stripped = text.strip()
    if text.startswith(" KÖR #"):
        return f"\033[1;97m{text}{_COLOR_RESET}"  # félkövér fehér
    if stripped and set(stripped) == {"="}:
        return f"\033[90m{text}{_COLOR_RESET}"  # szürke
    if stripped and set(stripped) == {"-"}:
        return f"\033[90m{text}{_COLOR_RESET}"  # szürke
    return text


def _enable_ansi():
    """
    Windows konzolban engedélyezi az ANSI/VT escape kódokat (Windows 10+).
    Linux-on / VSCode-ban nem kell semmi (ott alapból be van kapcsolva).
    """
    if os.name == "nt":
        os.system("")  # ez a hívás önmagában is bekapcsolja a VT-t (Win10+)
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            for sid in (-11, -12):  # -11 = stdout, -12 = stderr
                h = k32.GetStdHandle(sid)
                mode = ctypes.c_uint32()
                if k32.GetConsoleMode(h, ctypes.byref(mode)):
                    k32.SetConsoleMode(h, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            pass  # ha nem sikerül, legfeljebb nem lesz színes


# ----------------------------------------------------------------------

def typewriter(text: str):
    """Konzol kimenet – a [TAG]-ek színesek (ha ENABLE_COLORS = True)."""
    print(_paint(text))


def find_opera_gx_executable() -> str | None:
    """
    Megkeresi az Opera GX futtatható fájlt az alapértelmezett helyeken.
    Ha OPERA_GX_PATH környezeti változó be van állítva, azt használja.
    """
    if OPERA_GX_PATH and os.path.isfile(OPERA_GX_PATH):
        typewriter(f"[INFO] Opera GX útvonal (env): {OPERA_GX_PATH}")
        return OPERA_GX_PATH

    candidates = []

    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Opera Software\Opera GX Stable\opera.exe"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Local\Opera Software\Opera GX Stable\opera.exe"),
            r"C:\Program Files\Opera GX\opera.exe",
            r"C:\Program Files (x86)\Opera GX\Opera.exe",
            r"C:\Users\Marci\AppData\Local\Programs\Opera GX\opera.exe",
        ]
        if local:
            candidates.insert(0, os.path.join(local, "Programs", "Opera GX", "opera.exe"))
            candidates.insert(1, os.path.join(local, "Opera Software", "Opera GX Stable", "opera.exe"))

    elif sys.platform == "darwin":  # macOS
        candidates = [
            "/Applications/Opera GX.app/Contents/MacOS/Opera GX",
            os.path.expanduser("~/Applications/Opera GX.app/Contents/MacOS/Opera GX"),
        ]

    else:  # Linux
        candidates = [
            os.path.expanduser("~/opera-gx/opera"),
            "/usr/bin/opera-gx",
            "/opt/opera-gx/opera",
            "/usr/bin/opera",
        ]

    for path in candidates:
        if path and os.path.isfile(path):
            typewriter(f"[INFO] Opera GX megtalálva: {path}")
            return path

    typewriter("[WARN] Opera GX nem található az alapértelmezett helyeken.")
    return None


def attach_to_running_browser(p) -> Browser | None:
    """
    Csatlakozik a MÁR FUTÓ böngészőhöz a Chrome DevTools Protocolon keresztül.
    Ez akkor működik, ha az Opera GX --remote-debugging-port=PORT kapcsolóval
    fut. Ilyenkor a script nem indít új böngészőt, csak "rásimul" a meglevőre.
    """
    try:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        typewriter(f"[INFO] Csatlakozva a futó böngészőhöz (CDP {CDP_URL}).")
        return browser
    except Exception as e:
        typewriter(f"[WARN] Nem található futó böngésző CDP-vel a {CDP_URL} címen: {e}")
        return None


def launch_opera_with_cdp(p) -> Browser | None:
    """
    Elindítja az Opera GX-et a távoli vezérlő porttal. Ugyanazt a profilt
    használja (cookie-k, bejelentkezés), tehát a Te Opera GX-ed lesz – csak
    a script indítja el a --remote-debugging-port kapcsolóval.
    """
    opera = find_opera_gx_executable()
    if not opera:
        typewriter("[ERROR] Opera GX nem található, nem tudom elindítani CDP-vel.")
        return None

    typewriter(f"[INFO] Opera GX indítása távoli vezérléssel (CDP {REMOTE_DEBUG_PORT}): {opera}")
    try:
        return p.chromium.launch(
            headless=HEADLESS,
            executable_path=opera,
            args=[
                f"--remote-debugging-port={REMOTE_DEBUG_PORT}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
            ],
        )
    except Exception as e:
        typewriter(f"[ERROR] Opera GX indítása sikertelen: {e}")
        typewriter("  Tipp: ha már fut az Opera GX, előbb zárd be, vagy indítsd a")
        typewriter(f"  --remote-debugging-port={REMOTE_DEBUG_PORT} kapcsolóval, hogy a script csatlakozhasson.")
        return None


def open_new_tab(browser: Browser) -> tuple[BrowserContext, Page]:
    """
    Nyit egy ÚJ LAPOT a böngészőben:
      - ha csatlakoztunk a futó böngészőhöz: a meglévő (default) ablakban
        nyitjuk az új lapot (így a Te megnyitott ablakaid is megmaradnak);
      - ha mi indítottuk: létrehozunk egy contextet és abban az új lapot.
    """
    if browser.contexts:
        context = browser.contexts[0]
        typewriter("[INFO] Új lap nyitása a meglévő Opera GX ablakban...")
    else:
        context = browser.new_context()
        typewriter("[INFO] Új lap nyitása (új context)...")

    page = context.new_page()
    return context, page


def open_target_page(page: Page):
    """Megnyitja a keydrop amateur giveaway oldalt és vár a betöltésre."""
    typewriter(f"[INFO] Oldal megnyitása: {TARGET_URL}")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    time.sleep(2)
    title = page.title()
    typewriter(f"[INFO] Oldal címe: {title}")
    typewriter(f"[INFO] Aktuális URL: {page.url}")


# ----------------------------------------------------------------------
# SELECTOROK (a keydrop oldalról – ezeket adtad meg)
# ----------------------------------------------------------------------

JOIN_BTN = 'button[data-testid="btn-giveaway-join-the-giveaway"]'
TIME_LEFT = '[data-testid="label-giveaway-current-status"]'
WINNER_AVATAR = '[data-winner-avatar]'
SKIN_CATEGORY = '[data-testid="case-roll-won-item-category"]'
SKIN_NAME = '[data-testid="case-roll-won-item-name"]'
SKIN_PRICE = '[data-testid="case-roll-won-item-price"]'

# Egy kör max várakozási ideje a nyertesre (mp).
WINNER_WAIT_TIMEOUT = 30 * 60

# Figyelt nyertesek -> melyik txt fájlba mentsük a nyeréseiket.
# A kulcs kisbetűsen van tárolva (egyezés is kisbetűsen történik).
WATCHED_WINNERS = {
    "ytm4rc1x": "YTM4rc1x.txt",
}

# Eddigi nyeremény-összegek játékonként (EUR) – a WATCHED_WINNERS kulcsai szerint.
# Indításkor a meglévő txt fájlokból betöltődik (load_win_totals), futás közben
# minden elmentett nyeréssel nő (report_winner).
WIN_TOTALS = {name: 0.0 for name in WATCHED_WINNERS}


def parse_duration(text: str) -> int | None:
    """
    Emberi időtartamot parse-ol másodpercre.
    Példák: '1m30s', '2m', '60s', '120s', '90', '1h', '1h30m'.
    None, ha nem értelmezhető.
    """
    s = text.lower().replace(" ", "")
    if not s:
        return 0
    if re.fullmatch(r"\d+", s):
        return int(s)
    parts = re.findall(r"(\d+)\s*([hms])", s)
    if not parts:
        return None
    total = 0
    for val, unit in parts:
        v = int(val)
        if unit == "h":
            total += v * 3600
        elif unit == "m":
            total += v * 60
        else:
            total += v
    return total if total > 0 else None


def _time_to_seconds(text: str) -> int | None:
    """'00:01:30' vagy '1:30' -> 90 (mp). None, ha nem értelmezhető."""
    if not text:
        return None
    try:
        nums = [int(p) for p in text.split(":")]
    except ValueError:
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    return None


def ask_join_target():
    """
    Egyszer kérdezi meg indításkor: hány mp hátralévő időnél lépjen be.
    Fix érték (pl. 30s) VAGY tartomány (pl. 1s-1m, 1m30s-2m): utóbbi esetén
    minden körben véletlenszerűen választ a két érték között.
    Üres válasz = azonnali belépés (0s).
    Visszatérés: int (fix) vagy tuple[int, int] (tartomány).
    """
    typewriter("=" * 60)
    typewriter(" BEÁLLÍTÁS: mikor lépjen be? (hátralévő idő alapján)")
    typewriter(" Fix: 30s, 1m, 1m30s, 90 ...  |  Tartomány: 1s-1m, 1m30s-2m")
    typewriter(" Tartomány esetén minden körben random választ a kettő között. (üres = azonnal)")
    typewriter("=" * 60)
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if not raw:
            return 0
        if raw.count("-") == 1:
            lo_s, hi_s = raw.split("-", 1)
            lo, hi = parse_duration(lo_s), parse_duration(hi_s)
            if lo is not None and hi is not None and 0 <= lo <= hi:
                lo, hi = int(lo), int(hi)
                typewriter(f"[OK] Belépés véletlenszerűen: {lo}–{hi} mp hátralévőkor (minden körben).")
                return (lo, hi)
            typewriter(" Rossz tartomány. Pl. 1s-1m vagy 30s-2m.")
            continue
        secs = parse_duration(raw)
        if secs is not None:
            typewriter(f"[OK] Belépés, amikor ennyi mp van hátra: {secs} s")
            return secs
        typewriter(" Nem értem a formátumot, próbáld újra (pl. 30s vagy 1s-1m).")


def ask_min_price():
    """
    Egyszer kérdezi meg indításkor: milyen minimális skin-ár felett lépjen be.
    Pl. '5', '10,5', '10 EUR'. Üres = nincs minimum (mindig lép be).
    Visszatérés: float (EUR) vagy None.
    """
    typewriter("=" * 60)
    typewriter(" BEÁLLÍTÁS: minimum skin-ár (opcionális)")
    typewriter(" Csak akkor lép be, ha a nyeremény ára >= ez az érték (EUR).")
    typewriter(" Pl.: 5 vagy 10,5.  Üres = nincs minimum (mindig lép be).")
    typewriter("=" * 60)
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not raw:
            typewriter("[OK] Nincs minimum ár – mindig lép be.")
            return None
        val = parse_price(raw)
        if val is not None:
            typewriter(f"[OK] Minimum ár: {fmt_eur(val)} – ennél olcsóbb skinnél nem lép be.")
            return val
        typewriter(" Nem értem az árat, próbáld újra (pl. 5 vagy 10,5).")


def clear_console():
    """Törli a konzolt, hogy csak a legfrissebb nyertes látszódjon."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def print_timer(text: str):
    """Mozgó időzítő: ugyanazon a soron írja át az időt (nem új sorba)."""
    painted = _paint(text)
    # a paddinget a LÁTHATÓ hossz alapján adjuk meg, hogy az ANSI kódok
    # ne csúsztassák el az igazítást (a korábbi hosszabb sor maradványa
    # teljesen le legyen írva)
    sys.stdout.write("\r" + painted + " " * max(0, 80 - _visible_len(painted)))
    sys.stdout.flush()


def save_win(player: str, category: str, name: str, price: str) -> str | None:
    """
    Ha a nyertes figyelt játékos, elmenti a nyerést a saját txt fájljába.
    Visszaadja a fájlnevet, ha mentett; egyébként None.
    """
    fname = WATCHED_WINNERS.get(player.lower())
    if not fname:
        return None

    def _clean(s: str) -> str:
        # a keydrop beleszór láthatatlan karaktereket: soft-hyphen (U+00AD,
        # pl. "AWP­") és no-break space (U+00A0, pl. "6,84&nbsp;EUR")
        return s.replace("\u00ad", "").replace("\xa0", " ").strip()

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    # a keydrop kategóriája gyakran tartalmaz záró '|'-t (pl. "Desert Eagle |"),
    # ezért levágjuk, hogy ne legyen dupla elválasztó.
    cat = _clean(category).rstrip("|").rstrip()
    name = _clean(name)
    price = _clean(price)
    item = f"{cat} | {name}".strip()
    line = f"{ts} | {item} | ár {price}\n"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        return fname
    except Exception as e:
        typewriter(f"[WIN] Mentés sikertelen ({fname}): {e}")
        return None


def parse_price(text: str) -> float | None:
    """
    Ár-szöveget parse-ol euróra. Kezeli az európai formátumokat is:
    '1,86 EUR', '1.86 €', '1 234,56 EUR', '1.234' (ezres), '90'.
    None, ha nem található értelmezhető szám.
    """
    if not text:
        return None
    # először az ezreselválasztós, utána az egyszerű szám
    m = re.search(r"\d{1,3}(?:[ .\u00a0]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?", text)
    if not m:
        return None
    s = re.sub(r"[\s\u00a0]", "", m.group(0))
    if "," in s and "." in s:
        # az utolsó elválasztó a tizedjel
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        # '1.234' / '1.234.567' -> ezres elválasztó, nem tized
        if len(parts) > 1 and len(parts[0]) <= 3 and all(len(p) == 3 for p in parts[1:]):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def fmt_eur(value: float) -> str:
    """0.0 -> '0,00 €'; 1234.5 -> '1 234,50 €' (magyar formátum)."""
    s = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def load_win_totals():
    """
    Beolvassa a meglévő nyertest-fájlokat, és onnan összeadja az eddigi
    nyereményeket – így újraindítás után is a TÖBBET mutatja, nem csak az
    aktuális futásbelit. A fájl sora: '... | ár 1,86 EUR' -> a 'ár ' utáni részt parse-olja.
    """
    base = os.path.dirname(os.path.abspath(__file__))
    for player, fname in WATCHED_WINNERS.items():
        path = os.path.join(base, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if "ár " not in line:
                        continue
                    val = parse_price(line.rsplit("ár ", 1)[1])
                    if val:
                        WIN_TOTALS[player] += val
        except Exception:
            pass
    for player, val in WIN_TOTALS.items():
        if val > 0:
            typewriter(f"[INFO] Eddig nyert pénz ({player}): {fmt_eur(val)} – a meglévő fájlból beolvasva")


def _esc_pressed() -> bool:
    """ESC lenyomva? (csak ha a keyboard modul elérhető)."""
    try:
        import keyboard
        return keyboard.is_pressed("esc")
    except Exception:
        return False


def safe_inner_text(page: Page, selector: str, default: str = "") -> str:
    """Beolvas egy elem szövegét; ha nincs/hiba, visszaadja a defaultot."""
    try:
        loc = page.locator(selector).first
        if loc.count() > 0:
            return loc.inner_text().strip()
    except Exception:
        pass
    return default


def click_join(page: Page) -> bool:
    """
    Rákattint a 'Csatlakozás Nyereményjátékhoz' gombra.
    Ha már benne vagy a giveawayben, a gomb szövege megváltozik (pl.
    "Szerezd meg a(z) #2. nevezést · befizetés 1,86 EUR") – ilyenkor NEM
    kattintunk újra (nem veszünk fel fizetős #2 nevezést), hanem jelezzük,
    hogy már bent vagyunk. Ha a gomb teljesen tiltva van, szintén kihagyjuk.
    """
    try:
        page.wait_for_selector(JOIN_BTN, state="attached", timeout=20000)
    except Exception as e:
        typewriter(f"[JOIN] A gomb nem található 20s alatt: {e}")
        return False

    btn = page.locator(JOIN_BTN).first
    try:
        raw = btn.inner_text().strip()
        label = re.sub(r"\s+", " ", raw).lower()
    except Exception:
        raw = ""
        label = ""

    # A giveaway még nem indult el: a gomb le van tiltva, és egy 'múlva'
    # visszaszámlálót mutat. A bot nem tud csatlakozni -> hiba, timert kiírjuk.
    if "múlva" in label:
        typewriter(f"[ERROR] A giveaway még nem indult el – a bot nem tud csatlakozni. Indulásig hátralévő: {raw}")
        return False

    # Már benne vagyunk: a gomb a következő (fizetős) nevezést ajánlja.
    if "nevezést" in label or "szerezd meg" in label:
        typewriter(f"[ERROR] Már benne vagy a giveawayben (gomb: '{raw}') – nem kattintok újra.")
        return True

    try:
        if btn.is_enabled():
            btn.click(timeout=10000)
            typewriter("[JOIN] Rákattintottam a 'Csatlakozás Nyereményjátékhoz' gombra.")
        else:
            typewriter("[JOIN] A gomb tiltva – már benne vagy a giveawayben.")
        return True
    except Exception as e:
        typewriter(f"[JOIN] Kattintás sikertelen: {e}")
        return False


def read_time_left(page: Page) -> str:
    """Beolvassa a hátralévő időt (pl. 00:01:30)."""
    txt = safe_inner_text(page, TIME_LEFT)
    m = re.search(r"\d{1,2}:\d{2}(:\d{2})?", txt)
    return m.group(0) if m else txt


# A JELENTI (még nyerhető) skin nevét + árát a csatlakozás gomb körüli
# kártyából olvassa ki: a gombból felfelé mászik, amíg egy "X EUR" árat
# nem talál az adott szülőben, és az ár sorát megelőző szövegsorokat
# a skin névként adja vissza. (A gomb saját szövegét kivágja, mert a
# "befizetés 1,86 EUR" második-nevezés szöveget elcsaphatná.)
_JS_CARD_PRICE = r"""
(btnSel) => {
  const btn = document.querySelector(btnSel);
  if (!btn) return null;
  const btnText = (btn.innerText || '');
  let el = btn;
  // max. 5 szülő: annyi elég a kártyáig, de annyi már nem, hogy a teljes
  // oldal (vagy más giveaway kártyái) árát elkapjuk, ha a kártyában nincs
  for (let i = 0; i < 5 && el && el.parentElement; i++) {
    el = el.parentElement;
    let txt = (el.innerText || '').replace(/\u00a0/g, ' ').replace(/\u00ad/g, '');
    if (btnText) {
      const bi = txt.indexOf(btnText);
      if (bi >= 0) txt = txt.slice(0, bi) + txt.slice(bi + btnText.length);
    }
    const m = txt.match(/(\d{1,3}(?:[ .]\d{3})*(?:[.,]\d{1,2})?)\s*EUR/);
    if (m) {
      const idx = txt.indexOf(m[0]);
      const before = txt.slice(0, idx).split('\n').map(s => s.trim()).filter(Boolean);
      const clean = [];
      for (let j = before.length - 1; j >= 0 && clean.length < 2; j--) {
        const L = before[j];
        if (/^\d/.test(L)) continue;
        if (/EUR/i.test(L)) continue;
        if (/csatlakoz|nevezés|belép/i.test(L)) continue;
        clean.unshift(L);
      }
      return { price: m[0], name: clean.join(' | ') };
    }
  }
  return null;
}
"""


def read_current_prize(page: Page):
    """
    A JELENTI (még nyerhető) skin nevet és árát olvassa ki a giveaway
    kártyáról. Sorrend:
      1. case-roll-won-item-* testid-k (ha az oldalon jelen vannak),
      2. ha azok üresek: a csatlakozás gomb körüli kártya szövege (JS).
    Visszaad: (név, ár_szöveg, ár_float). A név/ár lehet üres, a float None.
    """
    cat = safe_inner_text(page, SKIN_CATEGORY)
    name = safe_inner_text(page, SKIN_NAME)
    price_txt = safe_inner_text(page, SKIN_PRICE)
    price_val = parse_price(price_txt)

    if price_val is None:
        try:
            res = page.evaluate(_JS_CARD_PRICE, JOIN_BTN)
        except Exception:
            res = None
        if res:
            if price_val is None and res.get("price"):
                price_txt = res["price"]
                price_val = parse_price(price_txt)
            if not name:
                name = res.get("name") or ""

    def _clean(s: str) -> str:
        return s.replace("\u00ad", "").replace("\xa0", " ").strip()

    cat = _clean(cat).rstrip("|").rstrip()
    name = _clean(name)
    full = f"{cat} | {name}" if cat and name else (name or cat)
    return full.strip(), _clean(price_txt), price_val


def giveaway_not_started(page: Page) -> bool:
    """
    True, ha a giveaway még nem indult el (a csatlakozás gomb egy 'múlva'
    visszaszámlálót mutat). ilyenkor a kártya még nem a Jelenlegi kör
    nyereményét mutatja, így a min-ár döntést nem most, hanem a belépési
    pillanatban tesszük meg.
    """
    try:
        jraw = page.locator(JOIN_BTN).first.inner_text().strip()
    except Exception:
        return False
    return "múlva" in re.sub(r"\s+", " ", jraw).lower()


def read_winner(page: Page) -> str:
    """
    Beolvassa a nyertes játékos nevét a winner blokkból.
    A név a `title` attribútumban is benne van, azt használjuk (pontos).
    """
    try:
        name = (
            page.locator(WINNER_AVATAR)
            .first
            .locator('xpath=ancestor::div[contains(@class,"gap-2")]//span[@title]')
            .first
            .get_attribute("title")
        )
        if name:
            return name.strip()
    except Exception as e:
        typewriter(f"[WINNER] Név kiolvasása sikertelen: {e}")
    return "?"


def wait_for_winner(page: Page, poll: int = 1) -> bool:
    """
    Megvárja, amíg kipörgetik a nyertest (megjelenik a WINNER_AVATAR).
    Közben MOZGÓ időzítőt ír ki (ugyanazon a soron írja át az időt).
    ESC-re, vagy WINNER_WAIT_TIMEOUT után False-val tér vissza.
    """
    typewriter("[WAIT] Várakozás a nyertes kipörgésére...")
    last = None
    waited = 0
    while waited < WINNER_WAIT_TIMEOUT:
        if ABORT_ON_ESC and _esc_pressed():
            typewriter("[ESC] Kilépés a várakozásból.")
            sys.stdout.write("\n")
            return False

        if page.locator(WINNER_AVATAR).count() > 0:
            sys.stdout.write("\n")
            return True

        t = read_time_left(page)
        if t and t != last:
            print_timer(f"[TIME] Hátralévő idő: {t}")
            last = t

        time.sleep(poll)
        waited += poll

    sys.stdout.write("\n")
    typewriter("[WARN] Időtúllépés a nyertes várásakor (WINNER_WAIT_TIMEOUT).")
    return False


def wait_until_join(page: Page, target: int, poll: int = 1, label: str = "[ENTRY]") -> str:
    """
    Figyeli az élő visszaszámlálót, és akkor tér vissza 'join'-nel, amikor a
    hátralévő idő <= target (mp). Ha a giveaway még nem indult el (a gomb egy
    'múlva' visszaszámlálót mutat), 'not_started'-dal tér vissza (hiba jelezve).
    Ha közben kipörgetik a nyertest, 'winner'-t ad vissza; ESC esetén 'esc'-t.
    Mozgó időzítőt ír ki (ugyanazon a soron).

    target < 0 esetén (pl. -1s, "NEM LÉP BE" KÖR) a 'join' SOHA nem érhető el:
    a visszaszámláló nem lesz soha <= -1, tehát a függvény addig figyel,
    amíg a kör véget nem ér (a nyertest kipörgetik) – így a script abban a
    körben biztosan NEM lép be a giveawaybe.
    """
    if target < 0:
        typewriter("[INFO] Ebben a körben nem lépünk be – várakozás a kör végéig (a nyertes kipörgéséig)...")
    else:
        typewriter(f"[WAIT] Várakozás a belépési időpontra (cél: <= {target}s hátralévő)...")
    last = None
    last_notstart = None
    while True:
        if ABORT_ON_ESC and _esc_pressed():
            sys.stdout.write("\n")
            return "esc"

        if page.locator(WINNER_AVATAR).count() > 0:
            sys.stdout.write("\n")
            return "winner"

        # A giveaway még nem indult el? A gomb egy 'múlva' visszaszámlálót mutat.
        if page.locator(JOIN_BTN).first.count() > 0:
            try:
                jraw = page.locator(JOIN_BTN).first.inner_text().strip()
                jl = re.sub(r"\s+", " ", jraw).lower()
            except Exception:
                jl = ""
            if "múlva" in jl:
                if jl != last_notstart:
                    timer = re.sub(r"\s+", " ", jraw)
                    typewriter(
                        f"[ERROR] A giveaway még nem indult el – a bot nem tud "
                        f"csatlakozni. Indulásig hátralévő: {timer}"
                    )
                    last_notstart = jl
                sys.stdout.write("\n")
                return "not_started"

        t = read_time_left(page)
        if t:
            secs = _time_to_seconds(t)
            if secs is not None and secs <= target:
                sys.stdout.write("\n")
                return "join"

        if t and t != last:
            print_timer(f"[TIME] Hátralévő idő: {t}  (cél: {target}s)")
            last = t

        time.sleep(poll)


def report_winner(page: Page):
    """Kiírja a konzolra a nyertest (fix szélességű dobozban, nem csúszik el)."""
    time.sleep(1.5)  # pár mp, amíg a skin adatok is megjelennek

    winner = read_winner(page)
    category = safe_inner_text(page, SKIN_CATEGORY)
    name = safe_inner_text(page, SKIN_NAME)
    price = safe_inner_text(page, SKIN_PRICE)

    clear_console()  # csak a jelenlegi nyertes látszódjon

    # --- fix szélességű doboz (címke oszlop rögzített, nem csúszik el) ---
    INNER = 50
    LBL = 18
    VAL = INNER - LBL - 3  # 29

    def cl(label: str, value: str) -> str:
        v = value if value else "?"
        if len(v) > VAL:
            v = v[: VAL - 1] + "…"
        return "  ║ " + (label + ":").ljust(LBL) + " " + v.ljust(VAL) + " ║"

    top = "  ╔" + "═" * INNER + "╗"
    title = "  ║" + " NYERTES KIPORGETVE ".center(INNER) + "║"
    mid = "  ╠" + "═" * INNER + "╣"
    bot = "  ╚" + "═" * INNER + "╝"

    typewriter(top)
    typewriter(title)
    typewriter(mid)
    typewriter(cl("Nyertes játékos", winner))
    typewriter(cl("Skin kategória", category))
    typewriter(cl("Skin neve", name))
    typewriter(cl("Skin ára", price))
    typewriter(bot)
    typewriter("")

    # --- mentés, ha figyelt nyertes nyert + eddigi nyeremény összegzése ---
    if winner and winner.lower() in WATCHED_WINNERS:
        fname = save_win(winner, category, name, price)
        if fname:
            typewriter(f"[WIN] {winner} nyert! Elmentve ide: {fname}")
            val = parse_price(price)
            if val is not None:
                WIN_TOTALS[winner.lower()] += val
                typewriter(
                    f"[WIN] Eddig nyert pénz: {winner} = {fmt_eur(WIN_TOTALS[winner.lower()])}"
                    f" | összesen: {fmt_eur(sum(WIN_TOTALS.values()))}"
                )
            else:
                typewriter(f"[WARN] Az ár nem olvasható ki ('{price}') – nem lett hozzáadva az összeghez.")


def run_scraper_logic(page, join_target=0, start_time: datetime | None = None, min_price=None):
    """
    FOLYAMATOS AUTOMATA (nem áll le):
      - minden kör elején kiolvassa és kiírja a JELENTI (még nyerhető) skin
        nevét + árát,
      - ha meg van adva a min_price: a DÖNTÉS AZONNAL A KÖR ELEJÉN történik:
        * skin ára < minimum  -> a körben NEM lép be (a kör végéig, a nyertes
          kipörgéséig vár, nem kattint),
        * skin ára >= minimum -> a célidő elérésénél belép,
        (ha a kör elején nem olvasható az ár – pl. a giveaway még nem indult –
         a döntés a belépési pillanatban történik),
      - figyeli a visszaszámlálót, és akkor lép be a giveawaybe, amikor a
        hátralévő idő eléri a célidőt (fix, vagy tartomány => minden körben
        véletlenszerűen a két érték közül),
      - kiírja a hátralévő időt (mozgó időzítővel),
      - amikor kipörgetik a nyertest, kiírja a nyertest + a nyert skin
        kategóriáját/nevét/árát (és elmenti a figyelt nyerteseket),
      - frissíti az oldalt és újra belép (új kör).
    ESC-re leáll (ha ABORT_ON_ESC = True).
    """
    if isinstance(join_target, tuple):
        tdisp = f"{join_target[0]}–{join_target[1]}s (random/kör)"
    else:
        tdisp = f"{join_target}s"

    extra = ""
    if min_price is not None:
        extra += f" | min skin-ár: {fmt_eur(min_price)}"
    slug = TARGET_URL.rstrip("/").split("/")[-1].upper()
    typewriter("=" * 60)
    typewriter(f" KEYDROP {slug} – AUTOMATA (belépés, amikor <= {tdisp} van hátra{extra} | ESC = kilépés)")
    typewriter("=" * 60)

    round_no = 0
    while True:
        if ABORT_ON_ESC and _esc_pressed():
            typewriter("[ESC] Kilépés a főciklusból.")
            break

        round_no += 1

        # futásidő + indítás ideje (HH:MM, nullákkal padded: 09:05, ne 9:5)
        if start_time is None:
            start_time = datetime.now()
        elapsed = datetime.now() - start_time
        total_min = int(elapsed.total_seconds() // 60)
        run_h, run_m = divmod(total_min, 60)
        start_str = start_time.strftime("%H:%M")

        # a JELENTI (még nyerhető) skin + ára, és a min-ár DÖNTÉS AZONNAL a
        # kör elején (ha a giveaway már fut – a megkezdett körskinje állandó)
        skin_now, price_txt_now, price_val_now = read_current_prize(page)
        not_started = giveaway_not_started(page)
        no_entry = (
            min_price is not None
            and price_val_now is not None
            and not not_started
            and price_val_now < min_price
        )

        typewriter("")
        typewriter("-" * 60)
        if no_entry:
            typewriter(f" KÖR #{round_no} – NEM LÉP BE (a skin ára < minimum {fmt_eur(min_price)})")
        else:
            typewriter(f" KÖR #{round_no} – belépés a giveawaybe")
        typewriter("-" * 60)

        typewriter(f"[INFO] A script {run_h} óra {run_m} perce fut  [indítva: {start_str}]")
        # eddigi nyeremény (figyelt nyertesek), játékonkénti bontással
        tot = sum(WIN_TOTALS.values())
        parts = [f"{p}: {fmt_eur(v)}" for p, v in WIN_TOTALS.items() if v > 0]
        suffix = f"  ({' | '.join(parts)})" if parts else ""
        typewriter(f"[INFO] Eddig nyert pénz : {fmt_eur(tot)}")
        # a JELENTI (még nyerhető) skin + ára – így látszik, mit olvas a bot
        if not_started:
            typewriter("[SKIN] A giveaway még nem indult el – a min-ár ellenőrzést a belépési pillanatban teszem meg.")
        elif price_val_now is not None:
            typewriter(f"[SKIN] Jelenlegi nyeremény: {skin_now or '?'} – {fmt_eur(price_val_now)}")
        elif price_txt_now or skin_now:
            typewriter(f"[SKIN] Jelenlegi nyeremény: {skin_now or '?'} – {price_txt_now or '?'}")
        else:
            typewriter("[SKIN] A jelenlegi nyeremény (név/ár) most nem olvasható ki.")

        # a min-ár DÖNTÉS azonnali kiírása (ha most eldönthető)
        #if no_entry:
        #    typewriter(
        #        f"[PRICE] {skin_now or 'A skin'} – {fmt_eur(price_val_now)} < minimum {fmt_eur(min_price)}"
        #        f" – ez a körben NEM lépek be, a kör végéig (a nyertesig) várok."
        #    )
        #elif min_price is not None and price_val_now is not None:
        #    typewriter(
        #        f"[PRICE] {skin_now or 'A skin'} – {fmt_eur(price_val_now)} >= minimum {fmt_eur(min_price)}"
        #        f" – belemegyek."
        #    )

        # célidő:
        #  - "nem lép be" kör: -1s -> a 'join' soha nem jön, a kör végéig vár
        #  - egyébként: fix érték, vagy tartományból random
        if no_entry:
            target = -1
            wlabel = "[PRICE]"
        elif isinstance(join_target, tuple):
            lo, hi = join_target
            target = random.randint(min(lo, hi), max(lo, hi))
            wlabel = "[ENTRY]"
        else:
            target = join_target
            wlabel = "[ENTRY]"

        # 0) Várakozás: belépő körnél a belépési időpontra, "nem lép be" körnél
        #    a kör végéig (target=-1 -> 'join' soha nem jön, csak 'winner'/'esc')
        status = wait_until_join(page, target, label=wlabel)
        while status == "not_started":
            # a giveaway még nem indult el (hiba már jelezve a wait_until_join-ben)
            # -> UGYANENNEK a körnek a keretében várunk és újrapróbálkozunk
            if ABORT_ON_ESC and _esc_pressed():
                status = "esc"
                break
            typewriter("[WAIT] Várakozás a giveaway indítására – újrapróbálkozás...")
            time.sleep(15)
            page.reload(wait_until="domcontentloaded")
            time.sleep(2)
            status = wait_until_join(page, target, label=wlabel)

        if status == "esc":
            typewriter("[ESC] Kilépés a várakozásból.")
            break

        if no_entry:
            # "NEM LÉP BE" KÖR: a kör a nyertes kipörgésével ért véget (a
            # 'join' target=-1 mellett nem jöhet). A csatlakozás gombra
            # NEM kattintunk. A nyertest kiírjuk/mentjük (figyelt nyertesek
            # miatt is), aztán frissítünk és tovább a következő körre.
            if status == "winner":
                typewriter("[PRICE] Kör véget ért – nyertes kipörgetve, nem léptünk be.")
                report_winner(page)
            else:
                typewriter("[PRICE] Kör véget ért, nem léptünk be.")
            typewriter("[REFRESH] Oldal frissítése, következő kör...")
            page.reload(wait_until="domcontentloaded")
            time.sleep(2)
            continue

        if status == "winner":
            # már kipörgettek a betöltéskor
            typewriter("[INFO] A nyertes már látható a betöltéskor.")
            report_winner(page)
        else:
            # 0.5) Minimum-ár ellenőrzés a belépés ELŐTT – CSAK akkor, ha a kör
            #     elején nem lehetett eldönteni (pl. a giveaway akkor még nem
            #     indult, az ár nem volt olvasható). Ha most is < minimum,
            #     nem lépünk be, a kör végéig várunk.
            if min_price is not None and price_val_now is None:
                skin_name, price_txt, price_val = read_current_prize(page)
                if price_val is not None and price_val < min_price:
                    typewriter(
                        f"[PRICE] {skin_name or 'A skin'} – {fmt_eur(price_val)} < minimum {fmt_eur(min_price)}"
                        f" – NEM lépek be, a kör végéig (a nyertesig) várok."
                    )
                    if page.locator(WINNER_AVATAR).count() > 0:
                        report_winner(page)
                    else:
                        found = wait_for_winner(page)
                        if not found:
                            if ABORT_ON_ESC and _esc_pressed():
                                break
                            typewriter("[RETRY] Újrapróbálkozás a következő körben.")
                            page.reload(wait_until="domcontentloaded")
                            time.sleep(2)
                            continue
                        report_winner(page)
                    typewriter("[REFRESH] Oldal frissítése, következő kör...")
                    page.reload(wait_until="domcontentloaded")
                    time.sleep(2)
                    continue
                elif price_val is None:
                    typewriter(
                        f"[WARN] Az ár nem olvasható ki belépéskor ('{price_txt}') – a biztonság "
                        f"kedvéért BELEMEGY."
                    )
                else:
                    typewriter(
                        f"[PRICE] {skin_name or 'A skin'} – {fmt_eur(price_val)} >= minimum {fmt_eur(min_price)}"
                        f" – belemegyek."
                    )

            # 1) Belépés a giveawaybe (elérte a cél hátralévő időt)
            ok = click_join(page)
            if not ok:
                # pl. a giveaway még nem indult el -> várunk és újrapróbáljuk
                if ABORT_ON_ESC and _esc_pressed():
                    break
                typewriter("[RETRY] Nem sikerült csatlakozni – újrapróbálkozás a következő körben.")
                page.reload(wait_until="domcontentloaded")
                time.sleep(10)
                continue

            # 2) Hátralévő idő kiírása a belépéskor
            t0 = read_time_left(page)
            typewriter(f"[TIME] Belépéskor hátralévő idő: {t0 if t0 else '?'}")

            if page.locator(WINNER_AVATAR).count() > 0:
                report_winner(page)
            else:
                # 3) Várakozás a nyertesre (mozgó időzítővel)
                found = wait_for_winner(page)
                if not found:
                    if ABORT_ON_ESC and _esc_pressed():
                        break
                    typewriter("[RETRY] Újrapróbálkozás a következő körben.")
                    page.reload(wait_until="domcontentloaded")
                    time.sleep(2)
                    continue
                report_winner(page)

        # 4) Refresh + újra belépés a következő körben
        typewriter("[REFRESH] Oldal frissítése, újra belépés a következő körben...")
        page.reload(wait_until="domcontentloaded")
        time.sleep(2)


def main():
    _enable_ansi()  # Windows konzolban bekapcsolja a színeket (Win10+)

    if ABORT_ON_ESC:
        try:
            import keyboard  # csak importáljuk, az ESC kezelése itt nem kritikus
        except Exception:
            pass

    typewriter(f"Opera GX (CDP) webscraper indítása – {STARTUP_WAIT} mp várakozás...")
    time.sleep(STARTUP_WAIT)

    join_target = ask_join_target()
    min_price = ask_min_price()
    start_time = datetime.now()

    with sync_playwright() as p:
        browser = None
        owned = False  # True = mi indítottuk a böngészőt, False = futóhoz csatlakoztunk

        # 1) próbálkozás: csatlakozás a futó böngészőhöz
        if ATTACH_TO_RUNNING:
            browser = attach_to_running_browser(p)

        # 2) ha nem sikerült, mi indítjuk az Opera GX-t CDP-vel
        if browser is None:
            browser = launch_opera_with_cdp(p)
            owned = True

        # 3) ha még mindig nincs (pl. Opera GX sincs), tartalék Chromium
        if browser is None:
            typewriter("[INFO] Playwright Chromium indítása (tartalék)...")
            browser = p.chromium.launch(headless=HEADLESS)
            owned = True

        context, page = open_new_tab(browser)
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            open_target_page(page)
            load_win_totals()
            run_scraper_logic(page, join_target, start_time, min_price)
        except PWTimeoutError as e:
            typewriter(f"[ERROR] Időtúllépés az oldal/elem várásakor: {e}")
        except Exception as e:
            typewriter(f"[ERROR] Váratlan hiba: {e}")
        finally:
            if owned:
                if KEEP_BROWSER_OPEN:
                    typewriter("[INFO] Az Opera GX nyitva marad. Bezáráshoz nyomj Entert...")
                    try:
                        input()
                    except (EOFError, KeyboardInterrupt):
                        pass
                typewriter("[INFO] Böngésző bezárása.")
                browser.close()
            else:
                typewriter("[INFO] Leválasztás a futó Opera GX-ről (a böngésző nyitva marad).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ESC] Ctrl+C – kilépés.")
