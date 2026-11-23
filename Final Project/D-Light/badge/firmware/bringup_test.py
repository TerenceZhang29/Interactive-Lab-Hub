# D-Light badge bring-up test (CircuitPython 10.x, ESP32-S3 Reverse TFT Feather).
# Copy to CIRCUITPY/code.py. Prints brightness, UV and battery once a second
# to the USB serial console and the built-in screen.
# Libraries in CIRCUITPY/lib: adafruit_ltr390, adafruit_max1704x (+ dependencies).
import time

import board

SETTLE_S = 0.25  # wait after switching between light and UV mode

i2c = board.I2C()

while not i2c.try_lock():
    pass
found = [hex(a) for a in i2c.scan()]
i2c.unlock()
print("I2C devices:", found)  # LTR390 is 0x53, battery gauge is 0x36

sensor = None
try:
    from adafruit_ltr390 import LTR390, Gain, Resolution

    sensor = LTR390(i2c)
    # Gain 1 so direct sun (about 100,000 lux) does not saturate the sensor.
    sensor.gain = Gain.GAIN_1X
    sensor.resolution = Resolution.RESOLUTION_18BIT
    print("LTR390 ready")
except Exception as e:  # sensor unplugged, or library API differs
    print("LTR390 not available:", repr(e))

gauge = None
try:
    from adafruit_max1704x import MAX17048

    gauge = MAX17048(i2c)
except Exception as e:
    print("Battery gauge not available:", repr(e))

while True:
    line = []
    if sensor is not None:
        try:
            # The sensor measures one thing at a time. The first value after a
            # mode switch is stale (it read 0 in testing), so switch, wait for
            # one full conversion (100 ms at 18-bit) and read again.
            sensor.light
            time.sleep(SETTLE_S)
            line.append("lux=%.1f" % sensor.lux)
            sensor.uvs
            time.sleep(SETTLE_S)
            line.append("uvs=%d" % sensor.uvs)
            line.append("uvi=%.2f" % sensor.uvi)
        except Exception as e:
            line.append("sensor error %r" % e)
    else:
        line.append("no sensor")
    if gauge is not None:
        try:
            line.append("bat=%.2fV %.0f%%" % (gauge.cell_voltage, gauge.cell_percent))
        except Exception as e:
            line.append("gauge error %r" % e)
    print(" ".join(line))
    time.sleep(1)
