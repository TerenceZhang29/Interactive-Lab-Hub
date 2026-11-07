# Distributed Interaction

> Team progress and documentation are in blockquotes.
>
> **Team** · Jiesen Huang, Serena Tsai, Yuge Xu, Youzhu Jin, Zijii Zhang, and Terence Zhang

[Course instructions](https://github.com/IRL-CT/Interactive-Lab-Hub/blob/Fall2026/Lab%206/README.md)

## Part A: MQTT Messaging

> **Completed.** Orange and a teammate’s Pi each published a test message and received the other Pi’s message through the course MQTT broker.
>
> The team brainstorm covered five ideas: a creature whose senses are distributed across Pis, a shared campfire, a maze with split controls, a story that each Pi rewrites, and a rhythm game that responds when players synchronize. [Teammate’s Part A notes](https://github.com/ht534-ui/Interactive-Lab-Hub/blob/00e3eb18c5acbe4632c5d23da6edfc337f6d1f6d/Lab%206/README.md#brainstorm-five-ideas-for-messaging-between-devices)

## Part B: Collaborative Pixel Grid

> The team documented the browser pixel grid and the Raspberry Pi with its APDS-9960 sensor. Both images are from the [teammate’s Part B record](https://github.com/ht534-ui/Interactive-Lab-Hub/blob/00e3eb18c5acbe4632c5d23da6edfc337f6d1f6d/Lab%206/README.md#part-b-collaborative-pixel-grid).
>
> ![Browser screenshot of the collaborative pixel grid](assets/pixel-grid.png)
>
> ![Raspberry Pi and APDS-9960 sensor setup during the pixel grid demo](assets/pi-setup.png)

## Part C: Make Your Own

> ### Digital Campfire
>
> Four players tend one virtual fire from separate Raspberry Pi stations. The heat and wood players keep their hands near their sensors while the wind player adjusts their distance to give the fire enough air. After the fire has stayed steady for three seconds, the storyteller moves a hand toward a fourth sensor to reveal the next line. The shared screen shows the flame, each station’s reading, and when the next line is ready. [Original team concept](https://github.com/ht534-ui/Interactive-Lab-Hub/blob/00e3eb18c5acbe4632c5d23da6edfc337f6d1f6d/Lab%206/README.md#deliverables)
>
> ### Architecture
>
> ```mermaid
> flowchart LR
>     heat["Heat · Pi + APDS-9960"]
>     wood["Wood · Pi + APDS-9960"]
>     wind["Wind · Pi + APDS-9960"]
>     story["Story · Pi + APDS-9960"]
>     broker["Course MQTT broker"]
>     server["Laptop · Flask fire and story state"]
>     screen["Shared browser · flame and story"]
>     heat --> broker
>     wood --> broker
>     wind --> broker
>     story --> broker
>     broker -->|"Normalized proximity readings"| server
>     server -->|"/api/state"| screen
> ```
>
> The Pis normalize their own sensor readings. The laptop combines all four inputs so the fire, timer, and story use the same state. The browser reads that state and draws the feedback.
>
> ### Build and run
>
> The prototype is in [`campfire/`](campfire/). Use separate virtual environments for this prototype and the Part B pixel grid. In a Bash shell on the laptop, run the following from `Lab 6/campfire`. Enter the course broker password when prompted.
>
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> python -m pip install -r requirements-server.txt
> export MQTT_USERNAME=idd
> read -rsp 'Course MQTT password: ' MQTT_PASSWORD
> export MQTT_PASSWORD
> echo
> python app.py
> ```
>
> Open [the shared display](http://127.0.0.1:5000/) on the laptop. On each Pi, create a virtual environment in its copy of `campfire/`, install `requirements-pi.txt`, and set the same MQTT variables. Run one role per Pi.
>
> | Station | Command | MQTT topic |
> | --- | --- | --- |
> | Heat | `python publish.py heat` | `IDD/jiesen-lab6/campfire/heat` |
> | Wood | `python publish.py fuel` | `IDD/jiesen-lab6/campfire/fuel` |
> | Wind | `python publish.py wind` | `IDD/jiesen-lab6/campfire/wind` |
> | Story | `python publish.py story` | `IDD/jiesen-lab6/campfire/story` |
>
> [The publisher](campfire/publish.py) sends a reading such as `{"level": 0.62}` five times per second. Use `--show-raw` to check the range from a hand away to a hand close, then set `--low` and `--high` to those raw readings. Set `MQTT_PREFIX` to the same value on the laptop and all Pis if you need a separate session.
>
> [The server](campfire/app.py) marks a station offline after two seconds without a reading. Heat and wood must each reach 55%, and wind must stay between 30% and 70% for the fire to count as steady. The storyteller withdraws below 35% before approaching to at least 55%. This lets the same player reveal one line per gesture.
>
> On the TV display, the sound button starts a crackling loop that gets louder as the fire grows. The fullscreen button expands the display for the TV. Reset clears the story and starts the steady-fire timer over while all four Pis keep sending data. [Display controls and sound credit](campfire/README.md)
>
> ### Key code excerpts
>
> Each Pi reads the APDS-9960, maps the calibrated raw range to 0–1, and sends the result on that station's MQTT topic. The message is sent every 0.2 seconds so that a held hand still registers and the server can tell when a station stops reporting. [Publisher source](campfire/publish.py)
>
> ```python
> raw = sensor.proximity
> level = max(0.0, min(1.0, (raw - args.low) / (args.high - args.low)))
> if client.is_connected():
>     client.publish(args.topic, json.dumps({"level": round(level, 3)}), qos=0, retain=False)
> stop.wait(0.2)
> ```
>
> On the laptop, a low Story reading arms one gesture. The next high reading consumes it and reveals a line only if the fire has stayed steady for three seconds. Starting the timer again after a reveal gives the three fire stations another round to hold together. [Server source](campfire/app.py)
>
> ```python
> def _read_story_gesture(self, level, now):
>     if level < 0.35:
>         self.story_armed = True
>     elif level >= 0.55 and self.story_armed:
>         self.story_armed = False
>         if self._stable_progress(now) == 1.0 and self.lines_unlocked < len(STORY):
>             self.lines_unlocked += 1
>             self.steady_since = now
> ```
>
> ### Build photos
>
> Each station has its own Raspberry Pi and a wired APDS-9960 proximity sensor. The four photos below show the hardware used in the playthrough.
>
> ![Overhead view of the table with four Raspberry Pis, sensors, and power cables](assets/campfire/table-overview.jpg)
>
> All four stations shared one table. Players could pick up their sensors while looking at the same screen.
>
> | Station hardware 1 | Station hardware 2 |
> | --- | --- |
> | ![First Raspberry Pi and its wired APDS-9960 on the tabletop](assets/campfire/station-01.jpg) | ![Second Raspberry Pi and its wired APDS-9960 on the tabletop](assets/campfire/station-02.jpg) |
> | **Station hardware 3** | **Station hardware 4** |
> | ![Third Raspberry Pi and its wired APDS-9960 among the tabletop cables](assets/campfire/station-03.jpg) | ![Fourth Raspberry Pi and its wired APDS-9960 beside a black case](assets/campfire/station-04.jpg) |
>
> ### Shared play display
>
> ![Complete widescreen Digital Campfire interface with the flame, all three story lines, and four station meters](assets/campfire/playthrough-panel.png)
>
> The full 16:9 interface with the story complete and simulated station readings.
>
> ![Shared TV showing the campfire and several station meters](assets/campfire/shared-display.jpg)
>
> The TV shows the fire and the live station readings together.
>
> ![Players standing beside the shared TV and the station table](assets/campfire/player-scene.jpg)
>
> Players at the installation with the display waiting for a steady fire.
>
> ### Playthrough video

https://github.com/user-attachments/assets/0d5c3d09-5f16-465e-9bd8-5cbc02dbe43e

> [Download the Digital Campfire MP4](assets/campfire/digital-campfire-demo.mp4) · 57 seconds
>
> The opening shows a proximity sensor up close. Synchronized views then show the players and the shared display as they reveal all three story lines.
>
> ### Hardware check
>
> Four simulated publishers drove the shared display through a local MQTT broker. The test checked a fresh story gesture, a held hand, excess wind, and an offline station. In the hardware playthrough, all four Pis sent readings through the course broker at the same time, and the team unlocked all three story lines on the shared display.
>
> ### Outside-team user testing
>
> Two people outside our team tried Digital Campfire. We grouped their comments below.
>
> - **Controlling the fire.** They found that small changes in hand distance mattered. Wind was the hardest station to hold in range, and even a slight movement could push it out of the target band.
> - **Following the story.** They described the story as very linear. They also felt that it formed a complete sequence and that the campfire setting fit what they expected from the story.
> - **Being part of the scene.** They found the experience playful and engaging. Helping keep the fire going made it feel as though they were there telling the story together.
>
> ### Reflection
>
> The shared display gave everyone the same place to look. In the recorded playthrough, the fire grew as the players brought their stations into range. The group then revealed three lines with separate Story gestures, and the text stayed on screen after the fire died down. Keeping the story visible gave the group time to read the ending after releasing the sensors.
>
> The Wind station exposed two distinct failure modes during setup. At first the Pi could not read the APDS-9960. It started reporting after we swapped both the sensor and the cable. Later it stopped publishing even though the Pi could still read the sensor. Restarting its publisher brought the meter back. The two-second timeout made the missing stream visible on the TV, while checking the sensor and the MQTT process separately showed where to look next.
>
> Each Pi normalizes its own proximity reading because calibration belongs to the individual sensor. The laptop combines the four MQTT streams, runs the fire and timer, and decides when a story gesture counts. This keeps one shared notion of when the fire is steady. The browser displays that state and changes the flame and sound together.
>
> The outside-team feedback gave us two concrete things to try next. We would start with a short practice round and test whether a wider Wind band lets players find and hold the target more comfortably. We would also try giving the storyteller a choice between two endings so the group can influence where the story goes as well as when the next line appears.

## AI Disclosure

> OpenAI Codex helped configure and verify the MQTT test, summarize the team’s notes, implement and document the prototype, edit the team’s photos and playthrough footage, and organize the tester feedback reported by the team.
