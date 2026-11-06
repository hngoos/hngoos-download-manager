"""Export app and extension icons from the approved HDM logo SVG.

Requires Pillow and Playwright with Chromium installed. Generated assets are
committed so normal application builds do not need a browser to render icons.
"""

import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/assets/hdm-logo-square.svg"
BRANDING = ROOT / "src/hngoos_dm/assets/branding"
EXTENSION = ROOT / "browser-extension/assets/icons"


def main():
    BRANDING.mkdir(parents=True, exist_ok=True)
    EXTENSION.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 1024, "height": 1024},
                device_scale_factor=1,
                color_scheme="dark",
            )
            page.goto(SOURCE.as_uri())
            page.locator("svg").evaluate(
                "e => { e.style.width = '1024px'; e.style.height = '1024px'; }"
            )
            rendered = page.locator("svg").screenshot(omit_background=True)
        finally:
            browser.close()
    with Image.open(io.BytesIO(rendered)) as source:
        image = source.convert("RGBA")
    assert image.size == (1024, 1024)
    image.resize((512, 512), Image.Resampling.LANCZOS).save(BRANDING / "hdm.png")
    image.save(BRANDING / "hdm.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    image.save(BRANDING / "hdm.icns")
    for size in (16, 32, 48, 128):
        image.resize((size, size), Image.Resampling.LANCZOS).save(EXTENSION / f"hdm-{size}.png")
    print("Exported HDM window, tray, Windows, macOS, Linux and Chromium icons.")


if __name__ == "__main__":
    main()
