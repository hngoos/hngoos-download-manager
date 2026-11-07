"""Render generated Morphicons SVGs for Tk, using an isolated browser at asset generation time."""
from pathlib import Path

from playwright.sync_api import sync_playwright

folder = Path(__file__).resolve().parents[1]/"src/hngoos_dm/assets/icons"
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    try:
        page = browser.new_page(viewport={"width": 24, "height": 24}, device_scale_factor=1)
        for source in folder.glob("*.svg"):
            page.set_content('<style>body{margin:0;background:transparent}</style>'+source.read_text())
            page.screenshot(path=str(source.with_suffix(".png")), omit_background=True)
    finally:
        browser.close()
