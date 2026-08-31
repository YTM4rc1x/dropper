"""
scraper.py – Webscraper stílusú keydrop automatizáló (Google Chrome böngészővel)

A régi clicker.py a KÉPERNYŐT nézte (pyautogui / képfelismerés).
Ez a script ehelyett egy VALÓDI Google Chrome böngészőt nyit meg, és a
böngésző DOM-ját (oldal szerkezetét) olvassa / vezérli közvetlenül – tehát
nem a képernyőt figyeli, hanem "webscraper" módon dolgozik.

Eddig csak ennyi kell:
  - Chrome megnyitása
  - https://keydrop.com/hu/giveaways/amateur megnyitása
A további lépéseket (mit kell csinálni az oldalon) később mondod meg,
azokat a `run_scraper_logic()` függvénybe írom bele.

Futtatás:
  1) pip install playwright
  2) playwright install chromium   (Chrome hiányában ez a tartalék böngésző)
  3) python scraper.py
"""

import os
import sys
import time

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PWTimeoutError

# ----------------------------------------------------------------------
# BEÁLLÍTÁSOK (ezeket nyugodtan átírhatod)
# ----------------------------------------------------------------------

TARGET_URL = "https://keydrop.com/hu/giveaways/amateur"

# True = látható ablakot nyit (Chrome), False = háttérben (headless).
HEADLESS = False

# Az ablak nyitása után ennyi mp-et vár, mielőtt nekiállna (debughoz hasznos).
STARTUP_WAIT = 3

# Oldal betöltésére adott maximális idő (ms).
PAGE_TIMEOUT = 60_000

# ESC-kilépés engedélyezése (mint a régi clicker.py-ban).
ABORT_ON_ESC = True

# Ha True, a script a végén nyitva hagyja a Chrome-ot, amíg Entert nem
# nyomsz. Ha False, azonnal bezárja a böngészőt a logika után.
KEEP_BROWSER_OPEN = True

# Ha meg van adva, ezt a Chrome futtathatót használja (teljes útvonal).
# Üresen hagyva automatikusan keresi az alapértelmezett helyeken.
CHROME_PATH = os.environ.get("CHROME_PATH", "")

# ----------------------------------------------------------------------

def typewriter(text: str):
    """Konzol kimenet – ugyanaz a stílus, mint a clicker.py-ban."""
    print(text)


def find_chrome_executable() -> str | None:
    """
    Megkeresi a Google Chrome futtatható fájlt az alapértelmezett helyeken.
    Ha CHROME_PATH környezeti változó be van állítva, azt használja.
    """
    # 1) Felhasználói felülírás
    if CHROME_PATH and os.path.isfile(CHROME_PATH):
        typewriter(f"[INFO] Chrome útvonal (env): {CHROME_PATH}")
        return CHROME_PATH

    # 2) Operációs rendszer szerinti alapértelmezett útvonalak
    candidates = []

    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        if local:
            candidates.insert(0, os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"))

    elif sys.platform == "darwin":  # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]

    else:  # Linux
        candidates = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/opt/google/chrome/chrome",
            "/snap/bin/chromium",
        ]

    for path in candidates:
        if path and os.path.isfile(path):
            typewriter(f"[INFO] Chrome megtalálva: {path}")
            return path

    typewriter("[WARN] Chrome nem található az alapértelmezett helyeken.")
    return None


def launch_browser(p):
    """
    Elindítja a böngészőt. Először a Google Chrome-ot próbálja (a Te kérésed),
    ha az nincs, akkor a Playwright saját Chromiumát használja tartalékként.
    """
    chrome = find_chrome_executable()

    launch_kwargs = dict(
        headless=HEADLESS,
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
        ],
    )

    if chrome:
        typewriter("[INFO] Chrome indítása...")
        launch_kwargs["executable_path"] = chrome
        try:
            return p.chromium.launch(**launch_kwargs)
        except Exception as e:
            typewriter(f"[WARN] Chrome indítása sikertelen ({e}), váltás Chromiumra.")

    typewriter("[INFO] Playwright Chromium indítása (tartalék)...")
    return p.chromium.launch(**launch_kwargs)


def open_target_page(page: Page):
    """Megnyitja a keydrop amateur giveaway oldalt és vár a betöltésre."""
    typewriter(f"[INFO] Oldal megnyitása: {TARGET_URL}")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    # Egy kis stabilizálódási idő a dinamikus (JS) tartalomnak.
    time.sleep(2)
    title = page.title()
    typewriter(f"[INFO] Oldal címe: {title}")
    typewriter(f"[INFO] Aktuális URL: {page.url}")


def run_scraper_logic(page: Page):
    """
    IDE JÖN A TOVÁBBI LOGIKA – ezt később írom meg, amikor elmondod,
    mit kell csinálni az oldalon (pl. gombok keresése/kattintása,
    adatok kiolvasása, bejelentkezés, stb.).

    Példa (majd kitörlöm, csak illusztráció):
        page.wait_for_selector(".giveaway-card", timeout=10_000)
        cards = page.query_selector_all(".giveaway-card")
        typewriter(f"[SCRAPE] Talált giveaway kártyák: {len(cards)}")
    """
    typewriter("[SCRAPE] (helyőrző) – itt fog majd a tényleges logika futni.")
    # <<< KÖVETKEZŐ LÉPÉSEK IDE >>>
    pass


def main():
    if ABORT_ON_ESC:
        try:
            import keyboard
            # Csak figyelünk, az ESC kezelése a ciklusban történik.
        except Exception:
            pass

    typewriter(f"Chrome webscraper indítása – {STARTUP_WAIT} mp várakozás...")
    time.sleep(STARTUP_WAIT)

    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            open_target_page(page)
            run_scraper_logic(page)
        except PWTimeoutError as e:
            typewriter(f"[ERROR] Időtúllépés az oldal/elem várásakor: {e}")
        except Exception as e:
            typewriter(f"[ERROR] Váratlan hiba: {e}")
        finally:
            if KEEP_BROWSER_OPEN:
                typewriter("[INFO] A Chrome nyitva marad. Bezáráshoz nyomj Entert...")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    pass
            typewriter("[INFO] Böngésző bezárása.")
            browser.close()

    typewriter("Script vége. Viszontlátásra!")


if __name__ == "__main__":
    main()
