"""Window-relative sizes with readable and clickable lower bounds."""

from math import ceil


class WindowScale:
    def __init__(self, window):
        self.factor = max(.65, min(1.25, window.winfo_width()/1280, window.winfo_height()/800))
        # Tk fonts use points while layout and artwork use pixels. Normalize
        # larger display scaling so text cannot outgrow a compact pixel window.
        self.font_factor = min(1, (4/3)/float(window.tk.call("tk", "scaling")))

    def size(self, original, minimum=1):
        return max(minimum, round(original*self.factor))

    def font_size(self, original, minimum=1):
        return max(1, ceil(self.size(original, minimum)*self.font_factor))
