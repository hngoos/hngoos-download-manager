"""Flattened PDF redaction: source objects, text and attachments are never copied."""

import math
import tempfile
from pathlib import Path

from .files import mark_internet, publish


def open_pdf(path, password=None):
    import pypdfium2 as pdfium
    return pdfium.PdfDocument(str(Path(path).resolve()), password=password)


def render_bounded(page, scale, pixel_budget=40_000_000):
    width, height = page.get_size()
    if (not math.isfinite(scale) or scale <= 0 or not math.isfinite(width)
            or not math.isfinite(height) or width <= 0 or height <= 0
            or math.ceil(width*scale)*math.ceil(height*scale) > min(40_000_000, pixel_budget)):
        raise ValueError("Trang PDF vượt giới hạn ảnh; hãy giảm độ phân giải hoặc chia nhỏ tài liệu.")
    return page.render(scale=scale)


def preview(path, page=0, scale=1.2, password=None):
    with open_pdf(path, password) as document:
        item = document[page]
        try:
            bitmap = render_bounded(item, scale)
            try:
                return bitmap.to_pil().copy(), len(document)
            finally:
                bitmap.close()
        finally:
            item.close()


def redact(source, destination, rectangles, password=None, scale=2):
    """Rectangles are normalized top-left coordinates (x0,y0,x1,y1) per zero-based page."""
    from PIL import ImageDraw
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError("Chọn tên PDF mới, không ghi đè tệp gốc.")
    if not any(rectangles.values()):
        raise ValueError("Chưa chọn vùng thông tin để xóa.")
    images = []
    try:
        with open_pdf(source, password) as document:
            if len(document) > 200:
                raise ValueError("Tối đa 200 trang mỗi lần để giới hạn bộ nhớ.")
            pixels = 0
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    bitmap = render_bounded(page, scale, 160_000_000-pixels)
                    try:
                        image = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                pixels += image.width * image.height
                if pixels > 160_000_000:
                    image.close()
                    raise ValueError("PDF quá lớn cho lần xử lý này; hãy chia nhỏ trước.")
                draw = ImageDraw.Draw(image)
                for rectangle in rectangles.get(page_index, []):
                    x0, y0, x1, y1 = rectangle
                    if not 0 <= x0 < x1 <= 1 or not 0 <= y0 < y1 <= 1:
                        raise ValueError("Vùng che nằm ngoài trang hoặc có diện tích bằng 0.")
                    # Expand by one output pixel to avoid an anti-aliased edge leaking original ink.
                    draw.rectangle((max(0, int(x0*image.width)-1), max(0, int(y0*image.height)-1),
                                    min(image.width, int(x1*image.width)+1),
                                    min(image.height, int(y1*image.height)+1)), fill="black")
                images.append(image)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".hngoos-redact-", dir=destination.parent) as folder:
            staged = Path(folder) / "redacted.pdf"
            images[0].save(staged, "PDF", save_all=True, append_images=images[1:], resolution=72*scale,
                           title="Redacted document", author="", subject="", keywords="")
            result = publish(staged, destination.parent, destination.name)
            mark_internet(result)
            return result
    finally:
        for image in images:
            image.close()
