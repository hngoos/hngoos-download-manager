"""Download filters classify original filenames, including quarantined outputs."""

from pathlib import Path

from .files import category

FILTERS = (("all", "All", "list"), ("file", "File", "file"), ("app", "App", "app"),
           ("video", "Video", "video"), ("music", "Music", "music"),
           ("image", "Image", "image"), ("archive", "Archive", "archive"), ("other", "Other", "folder"))
APPLICATIONS = {".exe", ".msi", ".msix", ".msixbundle", ".appx", ".appxbundle", ".dmg", ".pkg", ".app",
                ".deb", ".rpm", ".appimage", ".apk", ".aab", ".ipa", ".com", ".bat", ".cmd", ".ps1", ".sh"}


def job_category(job):
    name = job["filename"].removesuffix(".chuakiemtra")
    suffix = Path(name).suffix.lower()
    if suffix in APPLICATIONS:
        return "app"
    group = category(name)
    return {"Video": "video", "Music": "music", "Images": "image", "Documents": "file",
            "Archives": "archive"}.get(group, "other")
