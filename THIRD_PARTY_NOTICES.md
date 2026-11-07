# Third-party components

The hngoos-download-manager (HDM) application is proprietary. Included or optionally installed components retain their own licenses; the application license does not restrict rights granted by those upstream licenses. Earlier MIT-licensed versions retain their original license.

| Component | License / notices | Upstream source |
| --- | --- | --- |
| Morphicons | MIT, Copyright (c) 2026 Guillermo | https://www.morphicons.com and https://github.com/guillermolg00/morphicons |
| Lucide icon data used with Morphicons | ISC | https://lucide.dev and https://github.com/lucide-icons/lucide |
| Iconoir trash outline used with Morphicons | MIT; notice in docs/licenses/iconoir.txt | https://github.com/iconoir-icons/iconoir |
| Material Symbols alert outline | Apache-2.0; notice in docs/licenses/material-symbols.txt | https://github.com/google/material-design-icons |
| Phosphor sort outline | MIT; notice in docs/licenses/phosphor.txt | https://github.com/phosphor-icons/core |
| Simple Icons social-brand artwork in README badges | CC0-1.0 | https://github.com/simple-icons/simple-icons |
| Browser logos | Trademarks belong to their respective owners; Browser Logos collection MIT notice in docs/licenses/browser-logos.txt | https://github.com/alrra/browser-logos; Cốc Cốc artwork from https://coccoc.com/assets/images/home/compare/coccoc.png |
| Python | Python Software Foundation License | https://www.python.org/downloads/source/ |
| Tcl/Tk | Tcl/Tk BSD-style licenses | https://www.tcl.tk/software/tcltk/ |
| PyInstaller bootloader | GPL-2.0-or-later with bootloader exception | https://github.com/pyinstaller/pyinstaller |
| yt-dlp | Unlicense, with separately licensed bundled components | https://github.com/yt-dlp/yt-dlp |
| openpyxl | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| imageio-ffmpeg | BSD-2-Clause wrapper; bundled FFmpeg has its own LGPL/GPL notices | https://github.com/imageio/imageio-ffmpeg |
| FFmpeg binary supplied by imageio-ffmpeg | License depends on build configuration; inspect `ffmpeg -L` and `ffmpeg -buildconf` | https://www.ffmpeg.org/download.html and https://github.com/imageio/imageio-ffmpeg/tree/main/binaries |
| pypdfium2 / PDFium | Apache-2.0 / BSD-3-Clause and included third-party notices | https://github.com/pypdfium2-team/pypdfium2 and https://pdfium.googlesource.com/pdfium/ |
| Pillow | HPND and included component notices | https://github.com/python-pillow/Pillow |
| Playwright | Apache-2.0 | https://github.com/microsoft/playwright-python and https://github.com/microsoft/playwright |
| pystray | LGPL-3.0 | https://github.com/moses-palmer/pystray |
| libtorrent | BSD-3-Clause / Boost and included notices | https://github.com/arvidn/libtorrent |
| cryptography | Apache-2.0 or BSD-3-Clause and included component notices | https://github.com/pyca/cryptography |
| 7-Zip 26.05 | LGPL with BSD components and unRAR restrictions; see bundled archive-tools/License.txt | https://github.com/ip7z/7zip/releases/tag/26.05; corresponding source: https://github.com/ip7z/7zip/releases/download/26.05/7z2605-src.7z |
| EasyList / EasyPrivacy | GPL-3.0-or-later or CC-BY-SA-3.0; list headers govern | https://easylist.to/ |
| ABPVN | License and attribution in original list/repository | https://abpvn.com/ |
| uBlock Origin uAssets | GPL-3.0 | https://github.com/uBlockOrigin/uAssets |

Filter lists are fetched from upstream only when the user grants optional host access. They are not embedded in this repository. Runtime notices from installed distributions are collected beside release artifacts by the build scripts. Browser Chromium binaries are not included; website capture uses an installed Edge or a user-installed Playwright Chromium.

Maintainers must preserve each included component's license and corresponding-source obligations when redistributing executables. A package metadata license does not replace the licenses of its native binaries.
