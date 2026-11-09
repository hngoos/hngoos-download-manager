"""Rasterize the full-color Contact SVGs without changing their brand artwork."""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/assets"
ICONS = ROOT / "src/hngoos_dm/assets/icons"
BRANDS = ("facebook", "instagram", "gmail", "github")


def build():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 48, "height": 48}, device_scale_factor=2)
            for name in BRANDS:
                page.set_content('<style>body{margin:0;background:transparent}</style>'
                                 + (ASSETS / f"contact-{name}.svg").read_text(encoding="utf-8"))
                page.screenshot(path=str(ICONS / f"contact-{name}.png"), omit_background=True)
        finally:
            browser.close()
    # Supersampling keeps brand edges smooth in Tk at the target size.
    from PIL import Image
    for name in BRANDS:
        path = ICONS / f"contact-{name}.png"
        with Image.open(path) as image:
            image.resize((36, 36), Image.Resampling.LANCZOS).save(path)


if __name__ == "__main__":
    build()
