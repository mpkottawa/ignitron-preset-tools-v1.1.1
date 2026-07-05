# Ignitron Preset Tools v1.1.1

Ignitron Preset Tools is a Windows and macOS desktop app for managing
[Ignitron](https://github.com/stangreg/Ignitron) preset banks for Positive Grid
Spark amps. It helps you build pedal-ready preset banks, upload only the ESP32
filesystem, back up presets from the pedal, capture presets from the Spark app,
and adjust common firmware settings from one place.

![Ignitron Preset Tools dashboard](docs/images/dashboard.png)

## Downloads

Download the latest packaged app from the GitHub Release page:

[Ignitron Preset Tools v1.1.1 release](https://github.com/mpkottawa/ignitron-preset-tools-v1.1.1/releases/tag/v1.1.1)

Direct downloads:

- [Windows zip](https://github.com/mpkottawa/ignitron-preset-tools-v1.1.1/releases/download/v1.1.1/Ignitron.Preset.Tools.v1.1.1-windows.zip)
- [macOS zip](https://github.com/mpkottawa/ignitron-preset-tools-v1.1.1/releases/download/v1.1.1/Ignitron.Preset.Tools.v1.1.1-macos.zip)

The Ignitron firmware project is not bundled. Download or clone the firmware
separately, then choose that folder from the app dashboard.

## What The App Does

- Builds `PresetList.txt` and `PresetListUUIDs.txt` from a visual bank layout.
- Generates a printable `PresetList.pdf` setlist chart.
- Uploads only the LittleFS filesystem/data folder to the ESP32.
- Uploads firmware when you intentionally choose the Firmware tab.
- Backs up presets from a connected Ignitron pedal.
- Captures presets streamed from the Spark app.
- Provides firmware option editors for display, battery, LED, and amp rocker settings.
- Includes an interactive ESP32/Ignitron pin reference with schematic files.

## Requirements

Required:

- Windows 10/11 or macOS
- PlatformIO Core
- Ignitron firmware project downloaded separately
- ESP32 connected with a USB data cable

Usually required on Windows:

- CH340/CH341 USB serial driver for many generic ESP32 boards
- CP210x USB serial driver for Silicon Labs USB-to-serial boards

The first PlatformIO build or upload may require internet access so PlatformIO
can download the ESP32 platform, toolchain, and Arduino libraries.


-----------------------------------------------

FIRMWARE SETUP
---
To enable the Ignitron pedal to pull current pedal presets(by responding to the calls: LISTPRESETS and LISTBANKS), as well as stream presets from the app, two firmware files must be modified:

- `ignitron.ino` (main Ignitron folder) → **3 edits**  
- `SparkPresetControl.cpp` (in `/src` folder) → **1 edit**

You can either manually edit these files as described below, or replace them entirely with provided versions and update pedal-specific bits (pins, LEDs, display, etc.).

---

## A. Preset Pulling Configuration(3 edits)  
(edit the file: `/ignitron/ignitron.ino`)

### 1. Add this include at the top with the other libraries (around line 8):
```cpp
#include <LittleFS.h>
```

---

### 2. Add this line right below `void loop()` (around line 100):
```cpp
handleSerialCommands();   // so it will react to LISTPRESETS
```

---

### 3. Add the following block at the **end of the file** (should be around line 142):
```cpp
// === BEGIN: LISTPRESETS serial support =======================================

// Case-insensitive “.json” check
static bool hasJsonExt(const char *name) {
  if (!name) return false;
  size_t len = strlen(name);
  if (len < 5) return false;
  const char *ext = name + (len - 5);
  return ext[0] == '.' &&
         (ext[1] == 'j' || ext[1] == 'J') &&
         (ext[2] == 's' || ext[2] == 'S') &&
         (ext[3] == 'o' || ext[3] == 'O') &&
         (ext[4] == 'n' || ext[4] == 'N');
}

// Dump entire JSON file to a single line (removes CR/LF/TAB)
static void printJsonFileSingleLine(File &f) {
  Serial.print("JSON STRING: ");
  while (f.available()) {
    char c = (char)f.read();
    if (c == '\r' || c == '\n' || c == '\t') continue;
    Serial.write(c);
  }
  Serial.println();
}

// List every *.json at the LittleFS root
static void listAllPresets() {
  Serial.println("LISTPRESETS_START");

  File root = LittleFS.open("/");
  if (!root) {
    Serial.println("⚠️ Could not open LittleFS root");
    Serial.println("LISTPRESETS_DONE");
    return;
  }

  while (true) {
    File f = root.openNextFile();
    if (!f) break;

    if (!f.isDirectory()) {
      const char *name = f.name();
      if (name && hasJsonExt(name)) {
        Serial.print("Reading preset filename: ");
        Serial.println(name);
        printJsonFileSingleLine(f);
      }
    }
    f.close();
  }

  Serial.println("LISTPRESETS_DONE");
}

// Robust line-buffered serial command reader
static void handleSerialCommands() {
  static String buf;

  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;

    if (c == '\n') {
      String cmd = buf;
      buf = "";
      cmd.trim();
      if (cmd.length() == 0) return;

      String u = cmd;
      u.toUpperCase();

      if (u == "LISTPRESETS") {
        listAllPresets();
      }
      if (u == "LISTBANKS") {
        File f = LittleFS.open("/PresetList.txt");
        if (f) {
          Serial.println("LISTBANKS_START");
          while (f.available()) {
            char c = f.read();
            if (c == '\r') continue;
            Serial.write(c);
          }
          Serial.println("LISTBANKS_DONE");
          f.close();
        } else {
          Serial.println("⚠️ PresetList.txt not found");
          Serial.println("LISTBANKS_DONE");
        }
      }
    } else {
      buf += c;
      if (buf.length() > 256) {
        buf.remove(0, buf.length() - 256);
      }
    }
  }
}

// === END: LISTPRESETS serial support =========================================
```

---

## B. Spark App Streaming Configuration(1 edit)  
(edit `/ignitron/src/SparkPresetControl.cpp`)

Add the following lines **after** `DEBUG_PRINTLN(appReceivedPreset_.json.c_str());` (should be around line 400):

```cpp
// 🔧 Added for App Scraper
Serial.println("received from app:");
Serial.println(appReceivedPreset_.json.c_str());
```

### Final snippet should look like:
```cpp
void SparkPresetControl::updateFromSparkResponseAmpPreset(char *presetJson) {
    presetEditMode_ = PRESET_EDIT_STORE;
    appReceivedPreset_ = presetBuilder.getPresetFromJson(presetJson);

    DEBUG_PRINTLN("received from app:");
    DEBUG_PRINTLN(appReceivedPreset_.json.c_str());

    // 🔧 Added for App Scraper
    Serial.println("received from app:");
    Serial.println(appReceivedPreset_.json.c_str());

    presetNumToEdit_ = 0;
}
```


---

## C. optional- AMP Mode Toggle Switch Configuration(2 edits)

I found it a pain to always hold switch 1 to enter AMP mode.  use this mod to automatically handle it.  To add a toggle switch for AMP mode (spst 2 way rocker switch),\:

connect one side of the switch to gpio pin 35 of the esp32. On that same pin, put a 10k ohm resistor in series with a wire to 3.3volts on the board.  the other side of the switch, run to ground.
---

  to enable allowing a rocker switch to activate AMP mode any time it boots up, modify ignitron firmware by modifying one file in 2 spots, ignitron.ino in the root folder (/ignitron/ignitron.ino).  

1.
add this after the first string of includes in ignitron.ino:
---

```
#ifndef AMP_MODE_SWITCH_PIN
#define AMP_MODE_SWITCH_PIN 34    // <- change to the GPIO you wired; SPST to GND
#endif
```
----------------------------------------------------------------

2.
in /ignitron/ignitron.ino, at around line 59, the next line after: 
       
```
operationMode = spark_bh.checkBootOperationMode(); 
```

add the following:

```
    // --- Amp Mode toggle on GPIO35 ---  
     pinMode(AMP_MODE_SWITCH_PIN, INPUT);  // external 10k pull-up to 3.3V, switch to GND

     int _ampToggleState = digitalRead(AMP_MODE_SWITCH_PIN);  // HIGH=open, LOW=closed

     if (_ampToggleState == LOW) {
         operationMode = SPARK_MODE_AMP;   // force Amp Mode
         Serial.println("Amp toggle ON → forcing AMP mode");
     } else {
         Serial.println("Amp toggle OFF → normal boot");
     }
```

---------------------------------------------------------------


## Installation

### Windows

1. Download the Windows zip from the release page.
2. Extract the whole zip.
3. Run `Ignitron Preset Tools v1.1.1.exe`.
4. Keep the `_internal` folder beside the exe. The app needs it.

To put the app on your desktop, create a shortcut to the exe instead of moving
the exe by itself.

### macOS

1. Download the macOS zip from the release page.
2. Extract the zip.
3. Open `Ignitron Preset Tools v1.1.1.app`.

The macOS app is unsigned. If macOS blocks it the first time, right-click the
app, choose **Open**, then confirm.

## First-Time Setup

Open the app and choose your Ignitron firmware folder on the Dashboard.

The selected folder should contain:

```text
Ignitron/
  platformio.ini
  data/
  src/
  Ignitron.ino
```

The app uses the selected firmware folder throughout the project. Presets are
read from and exported to the firmware folder's `data` directory.

![Dashboard folder selector](docs/images/dashboard.png)

## Preset Bank Builder

The Preset Bank Builder is the main workflow for arranging the pedal banks.

![Preset Bank Builder](docs/images/preset-builder.png)

How to use it:

1. Click **Load Ignitron data folder** to use the selected firmware project's
   `data` folder.
2. Search the preset library on the left.
3. Double-click a preset or drag it into a bank slot.
4. Use **BANKS** to choose how many banks to build. The default is 30 banks.
5. Use **Export files** to write:
   - `PresetList.txt`
   - `PresetListUUIDs.txt`
   - `PresetList.pdf`
6. Use **Export + select port** when you are ready to upload the new bank list
   to the pedal.

Notes:

- Each bank has four slots.
- If a bank has fewer than four assigned presets, the export fills remaining
  slots using the last assigned preset in that bank.
- Right-click or double-click a filled slot to clear it.
- The generated PDF opens after export so you can review or print it.

## Upload Filesystem

The Upload FS page builds and uploads only the Ignitron `data` folder. This is
the normal way to update preset banks without reflashing firmware.

![Filesystem uploader](docs/images/upload-filesystem.png)

Typical workflow:

1. Build your bank layout in Preset Builder.
2. Click **Export + select port**.
3. Choose the ESP32 COM port.
4. Click **Upload filesystem** or **Build + upload**.

The app validates the data folder first. It checks for missing referenced JSON
files in `PresetList.txt` and warns before upload if needed.

Important:

- Filesystem upload does not reflash firmware.
- The pedal must already have compatible Ignitron firmware installed.
- The firmware project should use LittleFS, for example:

```ini
board_build.filesystem = littlefs
```

## Firmware Upload And Settings

The Firmware page is for intentionally building or uploading firmware and for
editing common options in the firmware source.

![Firmware upload and settings](docs/images/firmware-upload.png)

Firmware upload options include:

- PlatformIO environment
- COM port
- Upload speed
- Clean build
- Build only
- Upload filesystem after firmware
- Erase flash before upload

Firmware settings include:

- Firmware version text
- OLED driver selection
- Battery display settings
- Battery ADC pin and voltage divider values
- FX blink setting
- Dedicated preset LED option
- Amp mode rocker switch option and GPIO pin

Use the Firmware tab carefully. Firmware upload changes the code running on the
ESP32. For normal preset-bank changes, use Upload FS instead.

## Pedal Preset Puller

Pedal Puller backs up presets from a connected Ignitron pedal over serial.

Basic workflow:

1. Connect the Ignitron pedal by USB.
2. Select the COM port.
3. Choose whether to pull the active bank or the full preset library.
4. Start the backup.

Backups are saved under the selected Ignitron folder's backup location. This
feature requires firmware support for serial preset listing commands.

## Spark App Capture

Spark Capture listens for presets sent from the Spark app and saves clean
Ignitron JSON preset files.

Basic workflow:

1. Connect the Ignitron pedal by USB.
2. Select the COM port.
3. Start capture.
4. Send or store presets from the Spark app.
5. Click **End connection** when finished.

Captured presets are saved under the selected Ignitron folder's capture
location.

## Library Tools

Library Tools helps manage a larger preset library separately from a pedal's
active `data` folder.

Use it to:

- Scan a main preset library.
- View preset metadata and raw JSON.
- Find duplicate names.
- Find duplicate UUIDs.
- Send a library into Preset Builder.
- Build live setlists.

## ESP32 Reference

The Reference tab includes an interactive ESP32 Dev pinout, Ignitron wiring
notes, schematic links, and hardware reference material.

![ESP32 reference](docs/images/reference.png)

Clickable pins show the actual Ignitron schematic mapping, including:

| GPIO | Schematic Part | Function |
| --- | --- | --- |
| GPIO25 | SW1 | P1 / Drive switch |
| GPIO26 | SW2 | P2 / Mod switch |
| GPIO32 | SW3 | P3 / Delay switch |
| GPIO33 | SW4 | P4 / Reverb switch |
| GPIO19 | SW5 | Bank Down / Noise Gate switch |
| GPIO18 | SW6 | Bank Up / Comp switch |
| GPIO27 | D1 | P1 / Drive LED |
| GPIO13 | D2 | P2 / Mod LED |
| GPIO16 | D3 | P3 / Delay LED |
| GPIO14 | D4 | P4 / Reverb LED |
| GPIO23 | D5 | Bank Down / Noise Gate LED |
| GPIO17 | D6 | Bank Up / Comp LED |
| GPIO21 | J2 SDA | OLED SDA |
| GPIO22 | J2 SCL | OLED SCL |

Reference files include:

- Ignitron schematic PDF
- Battery indicator schematic PDF
- UV print PDF
- Ignitron cheatsheet PDF
- Hardware README

## Common Settings

Most users will use:

| Setting | Typical Value |
| --- | --- |
| PlatformIO environment | `esp32dev` |
| Upload speed | `921600` |
| Filesystem | `littlefs` |
| Firmware folder | Your downloaded Ignitron project |
| Preset folder | `Ignitron/data` |

## Troubleshooting

### No COM port appears

- Use a USB data cable, not a charge-only cable.
- Install the correct ESP32 USB serial driver.
- Open Windows Device Manager or macOS System Information to confirm the board
  appears.
- Click **Refresh ports** in the app.

### Filesystem upload fails

- Confirm the selected Ignitron folder contains `platformio.ini`.
- Confirm the selected environment matches your board.
- Try a lower upload speed if your board is unstable.
- Make sure no serial monitor is already connected to the same COM port.

### App opens but upload cannot find PlatformIO

Install PlatformIO Core, then set the PlatformIO path in the app. On Windows it
is commonly:

```text
C:\Users\<user>\.platformio\penv\Scripts\platformio.exe
```

### macOS says the app cannot be opened

The app is unsigned. Right-click the app, choose **Open**, then confirm. If
needed, allow it from **System Settings > Privacy & Security**.

## Project Layout

```text
source/
  ignitron_preset_tools_v1.1.1.py
  preset_chart.py
  preset_converter.py
  preset_puller.py
  preset_app_scraper.py
  reference/

docs/images/
  dashboard.png
  preset-builder.png
  upload-filesystem.png
  firmware-upload.png
  reference.png

.github/workflows/
  release.yml
```

## Building From Source

Install build requirements:

```bash
python -m pip install -r requirements-build.txt
```

Build the packaged app:

```bash
python build_release.py
```

Tagged releases are built automatically by GitHub Actions for Windows and macOS.

## Credits

Ignitron Preset Tools builds on the excellent Ignitron pedal project by
stangreg:

https://github.com/stangreg/Ignitron

This tool was created to make preset-bank editing, backup, capture, and
filesystem upload easier for Ignitron users.
