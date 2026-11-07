import json
import math
import os
from threading import Event, Lock, Thread
from time import monotonic

from flask import Flask, render_template
from paho.mqtt import client as mqtt


ROLES = ("heat", "fuel", "wind", "story")
OFFLINE_AFTER = 2.0
SECONDS_PER_LINE = 3.0
STORY = (
    "At dusk, three travelers stopped beneath a cedar and struck a light.",
    "Beyond the fire, a pair of eyes blinked. A fox had come to watch.",
    "By morning the fox was gone, but its tracks led them back to the road.",
)


class Campfire:
    def __init__(self):
        self.lock = Lock()
        self.samples = {}
        self.fire = 0.0
        self.last_tick = monotonic()
        self.steady_since = None
        self.lines_unlocked = 0
        self.story_armed = False

    def record(self, role, level):
        with self.lock:
            now = monotonic()
            self._advance(now)
            self.samples[role] = (level, now)
            self._advance(now)
            if role == "story":
                self._read_story_gesture(level, now)

    def run(self, stop):
        while not stop.wait(0.05):
            with self.lock:
                self._advance(monotonic())

    def reset_story(self):
        with self.lock:
            self.lines_unlocked = 0
            self.steady_since = None
            self.story_armed = False
            self._advance(monotonic())

    def _stations(self, now):
        stations = {}
        for role in ROLES:
            level, last_seen = self.samples.get(role, (0.0, -math.inf))
            online = now - last_seen < OFFLINE_AFTER
            stations[role] = {"level": level if online else 0.0, "online": online}
        return stations

    def _advance(self, now):
        stations = self._stations(now)
        heat, fuel, wind = (stations[role]["level"] for role in ("heat", "fuel", "wind"))

        draft = 0.65 + 0.35 * min(wind / 0.3, 1.0)
        if wind > 0.7:
            draft = 1.0 - 0.8 * (wind - 0.7) / 0.3
        target = (0.55 * heat + 0.45 * fuel) * draft
        blend = 1.0 - math.exp(-(now - self.last_tick) / 0.45)
        self.fire += (target - self.fire) * blend
        self.last_tick = now

        steady = heat >= 0.55 and fuel >= 0.55 and 0.3 <= wind <= 0.7
        if not steady:
            self.steady_since = None
        elif self.steady_since is None:
            self.steady_since = now
        if not stations["story"]["online"]:
            self.story_armed = False

    def _read_story_gesture(self, level, now):
        if level < 0.35:
            self.story_armed = True
        elif level >= 0.55 and self.story_armed:
            self.story_armed = False
            if self._stable_progress(now) == 1.0 and self.lines_unlocked < len(STORY):
                self.lines_unlocked += 1
                self.steady_since = now

    def _stable_progress(self, now):
        if self.lines_unlocked == len(STORY):
            return 1.0
        if self.steady_since is None:
            return 0.0
        return min((now - self.steady_since) / SECONDS_PER_LINE, 1.0)

    def snapshot(self):
        with self.lock:
            now = monotonic()
            self._advance(now)
            return {
                "stations": self._stations(now),
                "fire": self.fire,
                "stable_progress": self._stable_progress(now),
                "story": STORY[: self.lines_unlocked],
            }


app = Flask(__name__)
campfire = Campfire()


@app.get("/")
def index():
    return render_template("index.html", story_length=len(STORY))


@app.get("/api/state")
def api_state():
    return campfire.snapshot(), {"Cache-Control": "no-store"}


@app.post("/api/story/reset")
def reset_story():
    campfire.reset_story()
    return "", 204


def parse_level(payload):
    try:
        message = json.loads(payload)
    except (ValueError, RecursionError):
        return None
    if isinstance(message, dict):
        level = message.get("level")
        if type(level) in (int, float) and 0 <= level <= 1:
            return float(level)
    return None


def start_mqtt():
    host = os.environ.get("MQTT_HOST", "farlab.infosci.cornell.edu")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    username = os.environ.get("MQTT_USERNAME")
    password = os.environ.get("MQTT_PASSWORD")
    prefix = os.environ.get("MQTT_PREFIX", "IDD/jiesen-lab6/campfire").rstrip("/")
    if bool(username) != bool(password):
        raise ValueError("Set both MQTT_USERNAME and MQTT_PASSWORD, or leave both unset.")
    if not prefix or any(char in prefix for char in "+#\0"):
        raise ValueError("MQTT_PREFIX must be a nonempty topic prefix without wildcards.")

    topics = {f"{prefix}/{role}": role for role in ROLES}
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if username:
        client.username_pw_set(username, password)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            app.logger.warning("MQTT connection refused: %s", reason_code)
            return
        client.subscribe([(topic, 0) for topic in topics])

    def on_message(client, userdata, message):
        if message.retain or message.topic not in topics:
            return
        level = parse_level(message.payload)
        if level is not None:
            campfire.record(topics[message.topic], level)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(host, port)
    client.loop_start()
    return client


if __name__ == "__main__":
    port = int(os.environ.get("CAMPFIRE_PORT", "5000"))
    client = start_mqtt()
    stop = Event()
    simulation = Thread(target=campfire.run, args=(stop,), daemon=True)
    simulation.start()
    try:
        app.run(host="127.0.0.1", port=port, use_reloader=False)
    finally:
        stop.set()
        simulation.join()
        client.disconnect()
        client.loop_stop()
