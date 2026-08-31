import os
import time
import sys
import pyautogui
import keyboard

IMAGE_FOLDER = "images"
BELEPES_IMG   = os.path.join(IMAGE_FOLDER, "belepes.png")
NYERTESS_IMG  = os.path.join(IMAGE_FOLDER, "nyertessorsolasa.png")

CONFIDENCE = 0.78

STARTUP_WAIT = 5

ABORT_ON_ESC = True

# ----------------------------------------------------------------------

pyautogui.FAILSAFE = True


def typewriter(text: str):
    """Kicsit szépíthető konzol kimenet, nem kötelező."""
    print(text)


def locate_and_click(image_path, offset=(0, 0), confidence=CONFIDENCE):
    """
    Keres egy képeket a képernyőn és kattint a középre.
    Ha talál -> True, ha nem -> False (de a hívó ciklus soha nem fog leállani,
    mert a wait_for_image addig ismétlődik, amíg talál).
    """
    if not os.path.isfile(image_path):
        typewriter(f"[WARN] A képfájl nem található: {image_path}")
        return False

    try:
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if location is None:
            return False

        centre = pyautogui.center(location)
        click_x = centre.x + offset[0]
        click_y = centre.y + offset[1]
        pyautogui.click(click_x, click_y)
        typewriter(f"[CLICK] Kattintás ({click_x},{click_y}) az '{os.path.basename(image_path)}' képre")
        return True
    except pyautogui.ImageNotFoundException:
        return False


def wait_for_image(image_path, confidence=CONFIDENCE):
    """
    **BLOKKOLÓ** várakozás.
    Folyamatosan pollolja a képernyőt (0,5 másodperc percként),
    amíg a kép megjelenik. Amikor megjelenik, visszatér a True-val,
    és a `locate_and_click`-et meghívja a hívó ciklus.
    Semmikor nem tér el hamisáig (csak addig ciklusozik, amíg talál).
    """
    if not os.path.isfile(image_path):
        typewriter(f"[WARN] A képfájl nem található: {image_path}")
        return False

    typewriter(f"[INFO] Várakozás rá az '{os.path.basename(image_path)}' képre...")
    while True:
        if ABORT_ON_ESC and keyboard.is_pressed('esc'):
            typewriter("[ESC] Felhasználók megszakitta a várakozást.")
            sys.exit(0)

        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if location is not None:
                typewriter(f"[INFO] Kép megjelenött: {os.path.basename(image_path)}")
                return True
        except pyautogui.ImageNotFoundException:
            pass

        time.sleep(0.5)


def press_up_arrow_25x(delay=0.05):
    """
    25 alkalommal nyomja meg a felfele nyilakat.
    * delay*: másodperc, amíg várakozik két nyomás között (alapértelmezett: 0.05 s).
    """
    typewriter("[ARROW] 25x felfele nyil megnyomása...")
    for i in range(25):
        try:
            keyboard.press_and_release('up')
        except Exception as e:
            typewriter(f"[ARROW] Hiba az {i+1}. nyomásnál: {e}")
            break
        if i < 19:
            time.sleep(delay)
    typewriter("[ARROW] kész a 25 nyomás")


def press_f5():
    pyautogui.press('f5')
    typewriter("[KEY] F5 – oldal újratöltése")


def main():
    typewriter(f"Starting script – {STARTUP_WAIT} másodperc várakozás az ablak váltásához...")
    time.sleep(STARTUP_WAIT)

    while True:
        if ABORT_ON_ESC and keyboard.is_pressed('esc'):
            typewriter("[ESC] Kilépés a ciklus elején.")
            break

        press_f5()
        time.sleep(1)

        if ABORT_ON_ESC and keyboard.is_pressed('esc'):
            typewriter("[ESC] Kilépés az újratöltés után.")
            break

        typewriter("[STEP] Várakozás a bejelentkezési képre (belepes.png)...")
        if not wait_for_image(BELEPES_IMG, confidence=CONFIDENCE):
            typewriter("[WARN] a bejelentkezési kép sosem lett volna meg.")
            continue

        typewriter("[STEP] Kattintás a belepes.png-re...")
        if not locate_and_click(BELEPES_IMG):
            typewriter("[WARN] a belepes.png kattintása sikertelen.")

        typewriter("[PAUSE] 3 másodperc várakozás a kattintás után...")
        time.sleep(3)

        press_up_arrow_25x()

        if ABORT_ON_ESC and keyboard.is_pressed('esc'):
            typewriter("[ESC] Kilépés a kattintás után.")
            break

        typewriter("[STEP] Várakozás a nyertés képre (nyertessorsolasa.png)...")
        if not wait_for_image(NYERTESS_IMG, confidence=CONFIDENCE):
            typewriter("[WARN] a nyertés kép sosem lett volna meg.")
            continue

        typewriter("[STEP] Kattintás a nyertessorsolasa.png-re...")
        if not locate_and_click(NYERTESS_IMG):
            typewriter("[WARN] a nyertessorsolasa.png kattintása sikertelen.")

        typewriter("[PAUSE] 0.5 másodperc várakozás a következő ciklus előtt...")
        time.sleep(0.5)

        if ABORT_ON_ESC and keyboard.is_pressed('esc'):
            typewriter("[ESC] Kilépés a ciklus végén.")
            break

    typewriter("Script vége. Viszontlátásra!")


if __name__ == "__main__":
    if not os.path.isdir(IMAGE_FOLDER):
        os.makedirs(IMAGE_FOLDER, exist_ok=True)
        typewriter(f"Created folder '{IMAGE_FOLDER}'. Helyezze el innen a képmetszetek!")

    if not os.path.isfile(BELEPES_IMG):
        typewriter(f"[WARN] '{BELEPES_IMG}' nem található – a 'belepes' lépés sosem fusson, de a script tovább megy.")
    if not os.path.isfile(NYERTESS_IMG):
        typewriter(f"[WARN] '{NYERTESS_IMG}' nem található – a 'nyertessorsolasa' lépés sosem fusson, de a script tovább megy.")

    try:
        keyboard.wait('esc', suppress=False)
    except Exception:
        pass

    main()