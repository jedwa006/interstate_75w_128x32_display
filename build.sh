#!/bin/bash
set -e

# ============================================================
# Interstate 75W (RP2350) MicroPython Firmware Builder
# ============================================================
# Builds a custom MicroPython UF2 firmware for the i75w_rp2350
# using Pimoroni's build system from their interstate75 repo.
#
# This tracks the latest commits on main (not the v0.0.5 release),
# which includes: MicroPython master, GCC 14.2, PSRAM support,
# PicoVector2, Bluetooth, and all recent fixes.
#
# Prerequisites:
#   macOS:  brew install cmake arm-none-eabi-gcc ccache python3
#   Linux:  sudo apt install cmake gcc-arm-none-eabi build-essential ccache python3 python3-pip
#
# Usage:
#   ./build.sh           # Full build (clone + compile)
#   ./build.sh rebuild   # Rebuild only (skip clone, use existing sources)
#   ./build.sh clean     # Remove build directory
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_ROOT="${SCRIPT_DIR}/.build"
BOARD="i75w_rp2350"
FIRMWARE_DIR="${SCRIPT_DIR}/firmware"

# --- Dependency versions (matching Pimoroni CI as of latest main) ---
MICROPYTHON_REPO="https://github.com/micropython/micropython"
MICROPYTHON_BRANCH="master"

PIMORONI_PICO_REPO="https://github.com/pimoroni/pimoroni-pico"
PIMORONI_PICO_BRANCH="feature/picovector2-and-layers"

INTERSTATE75_REPO="https://github.com/pimoroni/interstate75"
INTERSTATE75_BRANCH="main"

DIR2UF2_VERSION="v0.0.9"
PY_DECL_VERSION="v0.0.3"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# Check prerequisites
# ============================================================
check_prereqs() {
    local missing=0

    for cmd in cmake python3 ccache git; do
        if ! command -v "$cmd" &>/dev/null; then
            err "Missing: $cmd"
            missing=1
        fi
    done

    # Check for ARM toolchain
    if ! command -v arm-none-eabi-gcc &>/dev/null; then
        err "Missing: arm-none-eabi-gcc"
        echo "  macOS:  brew install arm-none-eabi-gcc"
        echo "  Linux:  sudo apt install gcc-arm-none-eabi"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        exit 1
    fi

    ok "All prerequisites found"
}

# ============================================================
# Clone / update repositories
# ============================================================
clone_repos() {
    mkdir -p "$BUILD_ROOT/tools"

    # Interstate 75 (board definitions + build scripts)
    if [ -d "$BUILD_ROOT/interstate75" ]; then
        info "Updating interstate75..."
        cd "$BUILD_ROOT/interstate75" && git pull --ff-only && cd "$BUILD_ROOT"
    else
        info "Cloning interstate75 ($INTERSTATE75_BRANCH)..."
        git clone -b "$INTERSTATE75_BRANCH" "$INTERSTATE75_REPO" "$BUILD_ROOT/interstate75"
    fi

    # MicroPython
    if [ -d "$BUILD_ROOT/micropython" ]; then
        info "Updating micropython..."
        cd "$BUILD_ROOT/micropython" && git pull --ff-only && cd "$BUILD_ROOT"
    else
        info "Cloning micropython ($MICROPYTHON_BRANCH)..."
        git clone -b "$MICROPYTHON_BRANCH" "$MICROPYTHON_REPO" "$BUILD_ROOT/micropython"
    fi
    cd "$BUILD_ROOT/micropython"
    git submodule update --init lib/pico-sdk
    git submodule update --init lib/cyw43-driver
    git submodule update --init lib/lwip
    git submodule update --init lib/mbedtls
    git submodule update --init lib/micropython-lib
    git submodule update --init lib/tinyusb
    git submodule update --init lib/btstack
    cd "$BUILD_ROOT"

    # Pimoroni Pico libraries
    if [ -d "$BUILD_ROOT/pimoroni-pico" ]; then
        info "Updating pimoroni-pico..."
        cd "$BUILD_ROOT/pimoroni-pico" && git pull --ff-only && cd "$BUILD_ROOT"
    else
        info "Cloning pimoroni-pico ($PIMORONI_PICO_BRANCH)..."
        git clone -b "$PIMORONI_PICO_BRANCH" "$PIMORONI_PICO_REPO" "$BUILD_ROOT/pimoroni-pico"
    fi
    cd "$BUILD_ROOT/pimoroni-pico" && git submodule update --init && cd "$BUILD_ROOT"

    # Build tools
    if [ ! -d "$BUILD_ROOT/tools/dir2uf2" ]; then
        info "Cloning dir2uf2 ($DIR2UF2_VERSION)..."
        git clone -b "$DIR2UF2_VERSION" https://github.com/gadgetoid/dir2uf2 "$BUILD_ROOT/tools/dir2uf2"
    fi
    if [ ! -d "$BUILD_ROOT/tools/py_decl" ]; then
        info "Cloning py_decl ($PY_DECL_VERSION)..."
        git clone -b "$PY_DECL_VERSION" https://github.com/gadgetoid/py_decl "$BUILD_ROOT/tools/py_decl"
    fi

    # Python dependency for filesystem builds
    python3 -m pip install --quiet littlefs-python==0.12.0 2>/dev/null || \
    python3 -m pip install --quiet --break-system-packages littlefs-python==0.12.0 2>/dev/null || \
    info "Warning: could not install littlefs-python. With-filesystem build may fail."

    ok "All repositories cloned/updated"
}

# ============================================================
# Build mpy-cross (MicroPython cross-compiler)
# ============================================================
build_mpy_cross() {
    info "Building mpy-cross..."
    cd "$BUILD_ROOT/micropython/mpy-cross"
    CROSS_COMPILE="ccache " make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)" --quiet
    cd "$BUILD_ROOT"
    ok "mpy-cross built"
}

# ============================================================
# CMake configure + build
# ============================================================
cmake_configure() {
    info "Configuring CMake for $BOARD..."
    local BUILD_DIR="$BUILD_ROOT/build-$BOARD"
    local BOARD_DIR="$BUILD_ROOT/interstate75/boards/$BOARD"
    local TOOLS_DIR="$BUILD_ROOT/tools"

    if [ ! -f "$BOARD_DIR/mpconfigboard.h" ]; then
        err "Board directory not found: $BOARD_DIR"
        exit 1
    fi

    cmake -S "$BUILD_ROOT/micropython/ports/rp2" -B "$BUILD_DIR" \
        -DPICOTOOL_FORCE_FETCH_FROM_GIT=1 \
        -DPICO_BUILD_DOCS=0 \
        -DPICO_NO_COPRO_DIS=1 \
        -DPICOTOOL_FETCH_FROM_GIT_PATH="$TOOLS_DIR/picotool" \
        -DPIMORONI_PICO_PATH="$BUILD_ROOT/pimoroni-pico" \
        -DPIMORONI_TOOLS_DIR="$TOOLS_DIR" \
        -DUSER_C_MODULES="$BOARD_DIR/usermodules.cmake" \
        -DMICROPY_BOARD_DIR="$BOARD_DIR" \
        -DMICROPY_BOARD="$BOARD" \
        -DCMAKE_C_COMPILER_LAUNCHER=ccache \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache

    ok "CMake configured"
}

cmake_build() {
    info "Building firmware (this takes a few minutes)..."
    local BUILD_DIR="$BUILD_ROOT/build-$BOARD"
    local JOBS
    JOBS="$(nproc 2>/dev/null || sysctl -n hw.ncpu)"

    ccache --zero-stats 2>/dev/null || true
    cmake --build "$BUILD_DIR" -j "$JOBS"
    ccache --show-stats 2>/dev/null || true

    # Copy outputs
    local OUTPUT_DIR="$SCRIPT_DIR/output"
    mkdir -p "$OUTPUT_DIR"

    if [ -f "$BUILD_DIR/firmware.uf2" ]; then
        cp "$BUILD_DIR/firmware.uf2" "$OUTPUT_DIR/${BOARD}-micropython.uf2"
        ok "Firmware: output/${BOARD}-micropython.uf2"
    fi

    if [ -f "$BUILD_DIR/firmware-with-filesystem.uf2" ]; then
        cp "$BUILD_DIR/firmware-with-filesystem.uf2" "$OUTPUT_DIR/${BOARD}-micropython-with-filesystem.uf2"
        ok "Firmware (with filesystem): output/${BOARD}-micropython-with-filesystem.uf2"
    fi

    echo ""
    ok "Build complete! UF2 files are in output/"
    echo ""
    echo "  To flash:"
    echo "    1. Hold BOOT + tap RST on the Interstate 75W"
    echo "    2. Drag output/${BOARD}-micropython-with-filesystem.uf2 onto the RP2350 drive"
    echo "    3. Board will reboot automatically"
    echo ""
    echo "  Then deploy your clock firmware:"
    echo "    mpremote cp firmware/*.py :"
    echo "    mpremote cp firmware/config.json :"
}

# ============================================================
# Clean
# ============================================================
clean() {
    info "Cleaning build directory..."
    rm -rf "$BUILD_ROOT/build-$BOARD"
    rm -rf "$SCRIPT_DIR/output"
    ok "Cleaned"
}

# ============================================================
# Main
# ============================================================
case "${1:-}" in
    clean)
        clean
        ;;
    rebuild)
        check_prereqs
        cmake_configure
        cmake_build
        ;;
    *)
        check_prereqs
        clone_repos
        build_mpy_cross
        cmake_configure
        cmake_build
        ;;
esac
