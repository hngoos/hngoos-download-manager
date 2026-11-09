"""Generate matching Windows file properties for both HDM executables."""

from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

from hngoos_dm import __version__

version = tuple(int(part) for part in __version__.split("."))+(0,)
folder = Path("dist")
folder.mkdir(exist_ok=True)
for name, description in (("HDM", "Hngoos Download Manager"), ("HDMBridge", "HDM browser bridge")):
    strings = {"CompanyName": "hngoos", "FileDescription": description, "FileVersion": __version__,
               "InternalName": name, "OriginalFilename": name+".exe", "ProductName": "Hngoos Download Manager",
               "ProductVersion": __version__}
    resource = VSVersionInfo(ffi=FixedFileInfo(filevers=version, prodvers=version, mask=0x3f, flags=0,
        OS=0x40004, fileType=1, subtype=0, date=(0, 0)), kids=[
        StringFileInfo([StringTable("040904B0", [StringStruct(key, value) for key, value in strings.items()])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])])])
    (folder/(name+"-version.txt")).write_text(str(resource), encoding="utf-8")
print("Generated HDM Windows file properties for", __version__)
