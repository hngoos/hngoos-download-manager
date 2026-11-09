"""Small invoice input boundary shared by the native host and PDF renderer."""

from urllib.parse import urlsplit

from .safety import safe_filename, validate_url

SELLER_HOSTS = {"banhang.shopee.vn": "Shopee", "seller.shopee.vn": "Shopee",
                "sellercenter.lazada.vn": "Lazada", "seller-vn.tiktok.com": "TikTokShop",
                "seller.tiktok.com": "TikTokShop"}


def validate_invoice(url, markup, order_id):
    url = validate_url(url)
    site = SELLER_HOSTS.get(urlsplit(url).hostname)
    if not site or urlsplit(url).scheme != "https":
        raise ValueError("Chỉ lưu phiếu từ trang bán hàng đã hỗ trợ qua HTTPS.")
    if not isinstance(markup, str) or not 1 <= len(markup.encode("utf-8")) <= 90000:
        raise ValueError("Phiếu vượt giới hạn 90 KB; hãy lưu PDF từ hộp In của trình duyệt.")
    return site, safe_filename(str(order_id or "phieu-giao-hang"))[:100]
