# Ignitron Preset Tools v1.1.1

Windows desktop tools for building Ignitron preset banks, uploading the ESP32
LittleFS data folder, backing up presets from the pedal, capturing presets from
the Spark app, and adjusting common Ignitron firmware options.

Credit and thanks to stangreg for the original Ignitron project:
https://github.com/stangreg/Ignitron

## Download

Download the packaged app zip from this repo:

`releases/Ignitron Preset Tools v1.1.1.zip`

Extract the whole zip, then run:

`Ignitron Preset Tools v1.1.1.exe`

Do not move the `.exe` away from the `_internal` folder. If you want it on your
desktop, create a shortcut to the exe instead.

## What Is Included

- Ignitron Preset Tools v1.1.1 Windows app
- Bundled Python/Tkinter runtime
- Serial port support
- PDF chart generation support
- Helper scripts used by the app
- ESP32/Ignitron reference PDFs

The Ignitron firmware project is not bundled. Download it separately and choose
that folder from the app dashboard.

## Requirements

- Windows 10 or Windows 11
- PlatformIO Core
- Ignitron firmware project downloaded separately
- ESP32 connected with a USB data cable
- ESP32 USB serial driver if Windows does not detect the board
  - CH340/CH341 for many generic ESP32 boards
  - CP210x for Silicon Labs USB-to-serial boards

The first PlatformIO build/upload may require internet access so PlatformIO can
download ESP32 tools and libraries.

## App Setup

1. Open `Ignitron Preset Tools v1.1.1.exe`.
2. On the dashboard, choose your Ignitron firmware folder.
3. Confirm the selected folder contains:
   - `platformio.ini`
   - `data`
   - `src`
   - `Ignitron.ino`
4. Use Preset Builder to arrange banks.
5. Click `Export + select port`.
6. Choose the ESP32 COM port.
7. Click `Upload filesystem` or `Build + upload`.

Filesystem upload updates the Ignitron `data` folder and preset list on the
pedal. It does not reflash firmware unless you use the Firmware Upload tab.

## Notes

- Default PlatformIO environment is usually `esp32dev`.
- Default upload speed is usually `921600`.
- The app can use a different PlatformIO path if your install is not detected.
- The Reference tab includes the ESP32/Ignitron pin map and schematic files.
