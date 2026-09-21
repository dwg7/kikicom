#!/usr/bin/env bash
# Build wiedehopf/readsb with native RTL-SDR support on the RPi and install
# it to /usr/local/bin/readsb.
#
# Why: the Debian trixie `readsb` package (3.14.1630) is built WITHOUT
# rtlsdr support (`--device-type rtlsdr` is rejected). The earlier
# workaround `rtl_sdr | readsb --device-type ifile --ifile -` does decode,
# but ifile mode runs on a sample-count clock meant for offline replay, so
# aircraft.json / stats.json stop reflecting wall-clock time (aircraft.json
# stayed frozen at the service start). A native rtlsdr build fixes that.
#
# This builds a third-party tool under ~/build (on the SD card, not the
# tmpfs /tmp). It is NOT a checkout of this repository: the RPi still only
# captures. Run ON the RPi (or: ssh m329.local 'bash -s' < this script).
set -euo pipefail

BUILD_DIR="${KIKICOM_BUILD_DIR:-$HOME/build}"
REF="${READSB_REF:-dev}"  # wiedehopf/readsb default branch

sudo apt-get install -y --no-install-recommends \
  build-essential pkg-config git \
  libusb-1.0-0-dev librtlsdr-dev libncurses-dev zlib1g-dev libzstd-dev

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
rm -rf readsb
git clone --depth 1 --branch "$REF" https://github.com/wiedehopf/readsb.git
cd readsb
make -j"$(nproc)" RTLSDR=yes OPTIMIZE="-O3"
sudo install -m 0755 readsb /usr/local/bin/readsb
/usr/local/bin/readsb --version
