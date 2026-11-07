"""Rasterize rounded checkbox states; reuse the bundled Morphicons check geometry."""

from pathlib import Path

from PIL import Image, ImageDraw

folder = Path(__file__).resolve().parents[1]/"src/hngoos_dm/assets/icons"
scale = 4
for theme, panel, border, accent, tick in (
    ("dark", "#181818", "#555555", "#67d1f4", "#10252f"),
    ("light", "#ffffff", "#999999", "#087a9f", "#ffffff"),
):
    for selected in (False, True):
        for disabled in (False, True):
            image = Image.new("RGBA", (27*scale, 22*scale))
            draw = ImageDraw.Draw(image)
            fill = border if disabled and selected else accent if selected else panel
            draw.rounded_rectangle((scale, scale, 20*scale, 20*scale), radius=4*scale,
                                   fill=fill, outline=fill if selected else border, width=scale)
            if selected:
                points = [(int((3+x*0.7)*scale), int((2+y*0.7)*scale)) for x, y in ((4, 12), (9, 17), (20, 6))]
                draw.line(points, fill=panel if disabled else tick, width=2*scale, joint="curve")
                for x, y in points:
                    draw.ellipse((x-scale, y-scale, x+scale, y+scale), fill=panel if disabled else tick)
            image.resize((27, 22), Image.Resampling.LANCZOS).save(
                folder/f"checkbox-{theme}-{'on' if selected else 'off'}{'-disabled' if disabled else ''}.png")
