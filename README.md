# ignitron-preset-tools-v1.1.1
application to unlock your ignitron pedal for spark amps.

<img width="1024" height="1024" alt="IPT" src="https://github.com/mpkottawa/ignitron-preset-tools/blob/main/Ignitron%20preset%20tools%20logo.png" />

# Ignitron Preset Tools release v 1.1.1 #
## v1.1.1 — July, 2026

*Shoutout to stangreg for this great project `https://github.com/stangreg/Ignitron` *

This application will allow you to do 3 things:


---

this program was coded 100% with chatgpt and codex. I wanted a way to backup presets with ignitron, and struggled with pulling data back from the esp32 and converting it.  i simply asked chatgpt if it could
convert extracted raw preset data into usable .json files .  Then I just kept asking for more iterations. 
Included is a preset library folder with 700+ presets I automatically scraped from the spark app 

INSTALLATION
---
Extract IGNITRON PRESET TOOLS to anywhere on your computer. Run Ignitron Preset Tools.exe.  
---
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



