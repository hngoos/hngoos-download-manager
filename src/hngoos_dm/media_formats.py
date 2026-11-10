"""Export presets supported by the compact, bundled FFmpeg runtime."""

# codec, selectable bitrates; lossless/PCM exports retain the source sample rate.
AUDIO_EXPORTS = {
    "mp3": ("libmp3lame", (320, 256, 192, 128)),
    "m4a": ("aac", (320, 256, 192, 128, 96)),
    "wav": ("pcm_s16le", ()),
    "aac": ("aac", (320, 256, 192, 128, 96)),
    "flac": ("flac", ()),
    "aiff": ("pcm_s16be", ()),
    "wma": ("wmav2", (320, 256, 192, 128, 96)),
    "ac3": ("ac3", (320, 256, 192, 128, 96)),
}
VIDEO_CONTAINERS = ("mp4", "mov", "mkv", "webm", "m4v")
