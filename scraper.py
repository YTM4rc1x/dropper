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
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeoutError

# ----------------------------------------------------------------------
# BEÁLLÍTÁSOK (ezeket nyugodtan átírhatod)
# ----------------------------------------------------------------------

TARGET_URL = "https://keydrop.com/hu/giveaways/amateur"

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

def typewriter(text: str):
    """Konzol kimenet – ugyanaz a stílus, mint a clicker.py-ban."""
    print(text)


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
    "1r4z1": "1r4z1.txt",
}


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


def ask_join_target() -> int:
    """
    Egyszer kérdezi meg indításkor: hány mp hátralévő időnél lépjen be.
    A script figyeli az élő visszaszámlálót, és akkor kattint, amikor a
    hátralévő idő eléri ezt az értéket (pl. 30s -> 30 mp hátralévőkor).
    Üres válasz = azonnali belépés (0s).
    """
    typewriter("=" * 60)
    typewriter(" BEÁLLÍTÁS: mikor lépjen be? (hátralévő idő alapján)")
    typewriter(" Add meg, hány mp hátralévőkor lépjen be:")
    typewriter(" Formátum: 30s, 1m, 1m30s, 90 ... (üres = azonnal)")
    typewriter("=" * 60)
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        secs = parse_duration(raw)
        if secs is not None:
            typewriter(f"[OK] Belépés, amikor ennyi mp van hátra: {secs} s")
            return secs
        typewriter(" Nem értem a formátumot, próbáld újra (pl. 30s).")


def clear_console():
    """Törli a konzolt, hogy csak a legfrissebb nyertes látszódjon."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def print_timer(text: str):
    """Mozgó időzítő: ugyanazon a soron írja át az időt (nem új sorba)."""
    sys.stdout.write("\r" + text.ljust(80))
    sys.stdout.flush()


def save_win(player: str, category: str, name: str, price: str) -> str | None:
    """
    Ha a nyertes figyelt játékos, elmenti a nyerést a saját txt fájljába.
    Visszaadja a fájlnevet, ha mentett; egyébként None.
    """
    fname = WATCHED_WINNERS.get(player.lower())
    if not fname:
        return None
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    # a keydrop kategóriája gyakran tartalmaz záró '|'-t (pl. "Desert Eagle |"),
    # ezért levágjuk, hogy ne legyen dupla elválasztó.
    cat = category.rstrip().rstrip("|").rstrip()
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
    Ha a gomb tiltva van (már benne vagy), nem csinál semmit, de True-val tér
    vissza (hiszen már a giveawayben vagyunk).
    """
    try:
        page.wait_for_selector(JOIN_BTN, state="attached", timeout=20000)
    except Exception as e:
        typewriter(f"[JOIN] A gomb nem található 20s alatt: {e}")
        return False

    btn = page.locator(JOIN_BTN).first
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
    typewriter("[WAIT] Várakozás a nyertes kipörgésére (mozgó időzítő)...")
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


def wait_until_join(page: Page, target: int, poll: int = 1) -> str:
    """
    Figyeli az élő visszaszámlálót, és akkor tér vissza 'join'-nel, amikor a
    hátralévő idő <= target (mp). Ha közben kipörgetik a nyertest, 'winner'-t
    ad vissza; ESC esetén 'esc'-t.
    Mozgó időzítőt ír ki (ugyanazon a soron).
    """
    typewriter(f"[WAIT] Várakozás a belépési időpontra (cél: <= {target}s hátralévő)...")
    last = None
    while True:
        if ABORT_ON_ESC and _esc_pressed():
            sys.stdout.write("\n")
            return "esc"

        if page.locator(WINNER_AVATAR).count() > 0:
            sys.stdout.write("\n")
            return "winner"

        t = read_time_left(page)
        if t:
            secs = _time_to_seconds(t)
            if secs is not None and secs <= target:
                sys.stdout.write("\n")
                return "join"

        if t and t != last:
            print_timer(f"[ENTRY] Hátralévő idő: {t}  (cél: {target}s)")
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

    # --- mentés, ha figyelt nyertes nyert ---
    if winner and winner.lower() in WATCHED_WINNERS:
        fname = save_win(winner, category, name, price)
        if fname:
            typewriter(f"[WIN] {winner} nyert! Elmentve ide: {fname}")


def run_scraper_logic(page: Page, join_target: int = 0, start_time: datetime | None = None):
    """
    FOLYAMATOS AUTOMATA (nem áll le):
      - figyeli a visszaszámlálót, és akkor lép be a giveawaybe, amikor a
        hátralévő idő eléri a join_target értéket (pl. 30s -> 30 mp hátralévőkor),
      - kiírja a hátralévő időt (mozgó időzítővel),
      - amikor kipörgetik a nyertest, kiírja a nyertest + a nyert skin
        kategóriáját/nevét/árát (és elmenti a figyelt nyerteseket),
      - frissíti az oldalt és újra belép (új kör).
    ESC-re leáll (ha ABORT_ON_ESC = True).
    """
    typewriter("=" * 60)
    typewriter(f" KEYDROP AMATEUR – AUTOMATA (belépés, amikor <= {join_target}s van hátra | ESC = kilépés)")
    typewriter("=" * 60)

    round_no = 0
    while True:
        if ABORT_ON_ESC and _esc_pressed():
            typewriter("[ESC] Kilépés a főciklusból.")
            break

        round_no += 1
        typewriter("")
        typewriter("-" * 60)
        typewriter(f" KÖR #{round_no} – belépés a giveawaybe")
        typewriter("-" * 60)

        # futásidő + indítás ideje (HH:MM, nullákkal padded: 09:05, ne 9:5)
        if start_time is None:
            start_time = datetime.now()
        elapsed = datetime.now() - start_time
        total_min = int(elapsed.total_seconds() // 60)
        run_h, run_m = divmod(total_min, 60)
        start_str = start_time.strftime("%H:%M")
        typewriter(f"[INFO] A script {run_h} óra {run_m} perce fut  [indítva: {start_str}]")

        # 0) Várakozás a belépési időpontra: figyeljük a visszaszámlálót
        status = wait_until_join(page, join_target)
        if status == "esc":
            typewriter("[ESC] Kilépés a várakozásból.")
            break

        if status == "winner":
            # már kipörgettek a betöltéskor
            typewriter("[INFO] A nyertes már látható a betöltéskor.")
            report_winner(page)
        else:
            # 1) Belépés a giveawaybe (elérte a cél hátralévő időt)
            click_join(page)

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
    if ABORT_ON_ESC:
        try:
            import keyboard  # csak importáljuk, az ESC kezelése itt nem kritikus
        except Exception:
            pass

    typewriter(f"Opera GX (CDP) webscraper indítása – {STARTUP_WAIT} mp várakozás...")
    time.sleep(STARTUP_WAIT)

    join_target = ask_join_target()
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
            run_scraper_logic(page, join_target, start_time)
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
    main()
