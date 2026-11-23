# D-Light light badge: design decisions and purchase list

Working notes for the badge part of the team project D-Light (the sunflower that "eats" the sunlight you collect). Written on November 11, 2026 from a question-and-answer session with Claude (Claude Code); Jiesen made the decisions. Nothing here has been built or tested yet. Prices and stock are as shown on the vendor pages on November 11, 2026.

## Decisions

| # | Topic | Decision |
| --- | --- | --- |
| 1 | Main measure | Bright-light dose (lux over time) is the main measure. UV is a second channel, used for the "too much sun" reminder and for saying honestly that winter sun at this latitude cannot make enough vitamin D. Needs agreement from the Pi software pair. |
| 2 | Sensor | One Adafruit LTR390. It measures lux and UV, one mode at a time, so the firmware alternates. The kit's APDS9960 is not used on the badge. |
| 3 | Demo | A demo mode with compressed time (a button press starts it; a lamp or UV torch "feeds" the badge), plus replay of real worn data. |
| 4 | Sync | Physical docking: the badge snaps onto a magnetic USB-C cable from the Pi, which charges it and carries the data as USB serial. BLE is a stretch goal. Wi-Fi is dropped. Needs agreement from the team. |
| 5 | Wearing | Clipped to the chest of the outer coat, sensor facing out and uncovered. |
| 6 | Scope | Jiesen builds the whole badge: hardware, firmware, the receiver on the Pi and the enclosure. One set is bought first. Jiesen defines the data format and gives the Pi software pair a fake-data generator. |
| 7 | Build route | No soldering: Feather, STEMMA QT cable, JST battery plug, USB-C. Firmware in CircuitPython. |
| 8 | Board | Adafruit ESP32-S3 Reverse TFT Feather. The plain ESP32-S3 Feather (4 MB flash, 2 MB PSRAM) was out of stock. The screen stays off except in demo mode and debugging; the three built-in buttons cover the demo-mode button. |
| 9 | Battery | 350 mAh LiPo, which fits behind the Feather. |
| 10 | Enclosure | None for the first build. Later: cardboard or felt with an open hole over the sensor, since most plastics block UV. 3D printing comes after the check-off. |
| 11 | Money | Self-funded. |

## Purchase list (one set, all from Adafruit)

| Part | Adafruit ID | Price | Stock | What it does on the badge |
| --- | --- | --- | --- | --- |
| ESP32-S3 Reverse TFT Feather | [5691](https://www.adafruit.com/product/5691) | $24.95 | 38 in stock | The badge's computer. Wakes once a minute, reads the sensor, stores the sample and sleeps. Has the battery charger, battery gauge, sensor port, USB-C, three buttons and a small screen on board. |
| LTR390 UV light sensor | [4831](https://www.adafruit.com/product/4831) | $4.95 | In stock | Measures brightness (lux) and UV. Plugs into the Feather's STEMMA QT port. |
| LiPo battery, 3.7 V 350 mAh | [2750](https://www.adafruit.com/product/2750) | $6.95 | In stock | Powers the badge away from the flower. Plugs into the Feather's battery socket and recharges whenever the badge is docked. Ground shipping only. |
| USB A or C to C cable with magnetic tip, 1 m | [5520](https://www.adafruit.com/product/5520) | $13.95 | In stock | The dock. One end stays in the Pi; the magnetic tip stays in the badge's USB-C port. Snapping them together charges the badge and lets the Pi read its data. |
| Magnetic USB Type-C plug tip | [5524](https://www.adafruit.com/product/5524) | $4.95 | 75 in stock | A spare tip for the cable above. The cable's page does not say clearly whether a tip is in the box, and the tips are small and easy to lose. |

Total: $55.75 before shipping and tax ($50.80 without the spare tip).

Already available: a STEMMA QT / Qwiic cable from the course kit's cable set, and the Raspberry Pi 5.

Not in this order:

- **365 nm UV torch.** Adafruit does not sell one. It is only needed to show the "too much sun" path indoors; the lux path can be driven with a lamp, and UV can be tested in midday sun. Buy it before show week. A 395 nm torch will not work: the sensor barely responds at that wavelength.
- **Badge clip and enclosure materials.** Deferred with the enclosure.
- **4-pin magnetic pogo connector (Adafruit 5358).** It can carry charging and serial data, but both halves must be soldered, and the flower's Servo pHAT is wired to the Pi's serial receive pin.

## To check when the parts arrive

- The Pi sees the badge as a serial device through the magnetic cable. Adafruit says the cable carries data and power; the data speed is not stated.
- Whether the cable includes a tip.
- Real battery life. The estimate is about 1 mA average, or roughly two weeks on 350 mAh; it has not been measured.
- The lux range in direct sun. The driver's default settings saturate near 52,000 lux, so the firmware has to use gain 1.
- Whether a phone torch or desk lamp is bright enough to drive demo mode.

## Bring-up log, November 16, 2026

Done on a Mac, with the test program in [`firmware/bringup_test.py`](firmware/bringup_test.py).

- **Bootloader.** The board shipped with TinyUF2 0.12.3. CircuitPython 10 on 4 MB boards needs 0.33.0 or later, so the bootloader was updated to 0.35.0 with esptool from the chip's ROM bootloader (hold D0, tap Reset, release D0), flashing `tinyuf2-adafruit_feather_esp32s3_reverse_tft-0.35.0-combined.bin` at offset 0x0.
- **CircuitPython.** 10.3.2 installed by copying the UF2 to the `FTHRS3BOOT` drive. Libraries installed with circup: `adafruit_ltr390`, `adafruit_max1704x` and their dependencies.
- **Sensor.** The LTR390 answers at I2C address 0x53 and the battery gauge at 0x36. Indoor readings were about 130 to 490 lux and dropped when the sensor was covered.
- **Stale first reading.** The first value after switching between light and UV mode read 0. The fix is to switch mode, wait one conversion (0.25 s is used) and read again. The real firmware must do the same.
- **UV not yet verified.** UV read 0 indoors at night, which is expected but proves nothing. It needs daylight or a 365 nm torch.
- **Battery and cable.** With the battery connected the board kept running, and the Mac read serial data and wrote to the `CIRCUITPY` drive over the cable in use. Jiesen reports this was the magnetic cable. The Raspberry Pi has not been tried yet, and battery life has not been measured.

## Still open

Firmware and data design: sampling and storage on the badge, the data format, the docking protocol, how demo mode compresses time, and the receiver on the Pi.
