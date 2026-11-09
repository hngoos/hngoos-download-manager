#!/usr/bin/env bash
# Compact Windows FFmpeg. Run in a MinGW-w64 shell after prepare-ffmpeg.py.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$root/tools/ffmpeg-build"
jobs="${HDM_BUILD_JOBS:-4}"
prefix="$(cygpath -m "$work/prefix")"
mkdir -p "$prefix"
command -v gcc >/dev/null
command -v nasm >/dev/null
make_tool="$(command -v make || command -v mingw32-make)"

cd "$work/x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55"
./configure --prefix="$prefix" --host=x86_64-w64-mingw32 --enable-static --disable-cli --disable-opencl --enable-strip
"$make_tool" -j"$jobs" MAKE="$make_tool"
"$make_tool" install MAKE="$make_tool"

cd "$work/lame-3.100"
./configure --prefix="$prefix" --host=x86_64-w64-mingw32 --enable-static --disable-shared --disable-frontend --disable-analyzer-hooks --disable-decoder CFLAGS='-O2 -std=gnu17'
"$make_tool" -j"$jobs" MAKE="$make_tool"
"$make_tool" install MAKE="$make_tool"

cmake -S "$work/zlib-1.4" -B "$work/zlib-build" -G Ninja -DCMAKE_C_COMPILER=gcc \
    -DCMAKE_BUILD_TYPE=Release "-DCMAKE_INSTALL_PREFIX=$prefix" -DZLIB_BUILD_SHARED=OFF -DZLIB_BUILD_TESTING=OFF
cmake --build "$work/zlib-build" -j"$jobs"
cmake --install "$work/zlib-build"
# zlib uses an 's' suffix for its Windows static archive; pkg-config expects -lz.
cp "$prefix/lib/libzs.a" "$prefix/lib/libz.a"

meson setup "$work/dav1d-build" "$work/dav1d-1.5.4" --prefix="$prefix" \
    --default-library=static --buildtype=release -Denable_tools=false -Denable_tests=false
meson compile -C "$work/dav1d-build" -j"$jobs"
meson install -C "$work/dav1d-build"

cd "$work/ffmpeg-9.0.2"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
./configure --prefix="$prefix" --target-os=mingw32 --arch=x86_64 --cc=gcc \
    --pkg-config=pkgconf --pkg-config-flags=--static \
    --extra-cflags="-I$prefix/include" --extra-ldflags="-L$prefix/lib -static" \
    --enable-static --disable-shared --disable-autodetect --enable-gpl \
    --enable-libx264 --enable-libmp3lame --enable-libdav1d --enable-zlib \
    --enable-schannel --enable-mediafoundation --enable-d3d11va --disable-ffplay --disable-ffprobe \
    --disable-doc --disable-debug --enable-small --disable-indevs --enable-indev=lavfi --disable-outdevs
"$make_tool" -j"$jobs" MAKE="$make_tool"
"$make_tool" install MAKE="$make_tool"
destination="$root/src/hngoos_dm/assets/runtime"
mkdir -p "$destination"
cp "$prefix/bin/ffmpeg.exe" "$destination/ffmpeg.exe"
"$destination/ffmpeg.exe" -hide_banner -version
