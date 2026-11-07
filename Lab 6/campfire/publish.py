"""Publish one Digital Campfire station's proximity readings over MQTT."""

import argparse
import json
import os
import signal
import sys
from threading import Event


def read_options():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("heat", "fuel", "wind", "story"))
    parser.add_argument("--low", type=int, default=0, help="Raw reading for level 0 (default: 0)")
    parser.add_argument("--high", type=int, default=255, help="Raw reading for level 1 (default: 255)")
    parser.add_argument("--simulate", type=float, metavar="LEVEL", help="Send a fixed level between 0 and 1")
    parser.add_argument("--show-raw", action="store_true", help="Print raw readings for calibration")
    args = parser.parse_args()

    if not 0 <= args.low < args.high <= 255:
        parser.error("calibration must satisfy 0 <= --low < --high <= 255")
    if args.simulate is not None and not 0 <= args.simulate <= 1:
        parser.error("--simulate must be between 0 and 1")
    if args.show_raw and args.simulate is not None:
        parser.error("--show-raw requires an actual sensor")

    args.host = os.environ.get("MQTT_HOST", "farlab.infosci.cornell.edu")
    try:
        args.port = int(os.environ.get("MQTT_PORT", "1883"))
    except ValueError:
        parser.error("MQTT_PORT must be an integer between 1 and 65535")
    if not 1 <= args.port <= 65535:
        parser.error("MQTT_PORT must be an integer between 1 and 65535")
    args.username = os.environ.get("MQTT_USERNAME")
    args.password = os.environ.get("MQTT_PASSWORD")
    if bool(args.username) != bool(args.password):
        parser.error("set both MQTT_USERNAME and MQTT_PASSWORD, or leave both unset")

    prefix = os.environ.get("MQTT_PREFIX", "IDD/jiesen-lab6/campfire").rstrip("/")
    if not prefix or any(char in prefix for char in ("#", "+", "\0")):
        parser.error("MQTT_PREFIX must be a nonempty topic prefix without wildcards")
    args.topic = f"{prefix}/{args.role}"
    return args


def open_sensor():
    try:
        import board
        from adafruit_apds9960.apds9960 import APDS9960
    except ImportError as error:
        raise RuntimeError("Install the Pi dependencies from requirements-pi.txt") from error

    try:
        sensor = APDS9960(board.I2C())
        sensor.enable_proximity = True
        return sensor
    except (OSError, ValueError, RuntimeError) as error:
        raise RuntimeError(f"Could not open the APDS-9960. Check the I2C connection. ({error})") from error


def publish(args):
    try:
        from paho.mqtt.client import CallbackAPIVersion, Client
    except ImportError as error:
        raise RuntimeError("Install paho-mqtt 2.x to publish readings") from error

    sensor = open_sensor() if args.simulate is None else None
    client = Client(CallbackAPIVersion.VERSION2)
    client.connect_timeout = 5
    if args.username:
        client.username_pw_set(args.username, args.password)

    stop = Event()
    connection_error = None

    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal connection_error
        if reason_code.is_failure:
            connection_error = f"MQTT broker refused the connection ({reason_code})"
            stop.set()
        else:
            print(f"Publishing {args.role} readings to {args.topic}", flush=True)

    client.on_connect = on_connect
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        client.connect(args.host, args.port)
        client.loop_start()
        while not stop.is_set():
            level = args.simulate
            if sensor is not None:
                try:
                    raw = sensor.proximity
                except OSError as error:
                    raise RuntimeError(f"Lost the APDS-9960 I2C connection ({error})") from error
                level = max(0.0, min(1.0, (raw - args.low) / (args.high - args.low)))
                if args.show_raw:
                    print(f"raw={raw} level={level:.3f}", flush=True)
            if client.is_connected():
                client.publish(args.topic, json.dumps({"level": round(level, 3)}), qos=0, retain=False)
            stop.wait(0.2)
    finally:
        client.disconnect()
        client.loop_stop()

    if connection_error:
        raise RuntimeError(connection_error)


def main():
    try:
        publish(read_options())
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError) as error:
        print(f"Campfire publisher: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
