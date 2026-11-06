# Yesterday Together: revised storyboard — prompts

Freeflow iteration; five independent built-in Imagegen calls, one illustration per call. Images 01–05 were copied unchanged from the generated originals. All people and the device are fictional illustrations; captions, status, numbers and the simplified review interface were added in HTML/CSS. The review UI follows the structure of `../../morning-review-2026-11-01.png`; its thumbnails are illustrative rather than the real test footage. The Lab 1 and Lab 2 storyboard renders were also inspected for linework and information density. No camera operates at night. The review buttons, the bedtime trigger, an actual overnight run and playback remain unverified or unimplemented as explained in the README.

## Caption sequence

1. Choose the day's moments — caregiver selects clips and adds factual notes in the evening.
2. One bedtime handoff — press Prepare My Diary and receive confirmation.
3. The device works overnight — processing selected material and sending frames to cloud vision.
4. Review before playback — timeline, Check first and source images; human review before approval.
5. Listen together — planned playback, pause, replay and next.

## Generation prompts

Reference paths are relative to this file. Each corresponding original is in `/Users/huangjiesen/.codex/generated_images/01a1982e-d7a8-7532-9aaf-c937db095dd7/`.

### 01-select.png
Reference: `../storyboard-audio-diary/01-bedtime-handoff.png` for the caregiver and style. Original: `exec-1b98b33b-cfb9-4ca8-aa0f-fd05e7a22fc8.png`.

> Create ONE standalone landscape 4:3 storyboard illustration. Reference image provides character and visual style: same fictional short dark curly-haired caregiver in gray sweater, restrained graphite and colored pencil, warm ivory paper. Early evening, caregiver seated at table selecting daytime photo and video thumbnails and adding a factual note on a smartphone; show the phone and gesture clearly, screen as blank abstract thumbnail shapes with no lettering. Quiet warm domestic scene. No other people, no brand, no text, no labels, no numbering, no panel border. Keep complete hands and phone inside image.

### 02-handoff.png
Reference: `../storyboard-audio-diary/01-bedtime-handoff.png` for people, device and style. Original: `exec-6bae08a1-3681-48f2-9446-cd38f503d0d7.png`.

> ONE standalone landscape 4:3 storyboard illustration matching reference exactly: fictional white-haired older woman in sage green cardigan, short dark curly-haired caregiver in gray sweater, same off-white tabletop Pi with single large sage button and small separate cube speaker. Bedtime, older woman presses the single button, caregiver alongside. Screen blank, to be overlaid later. Graphite and restrained colored pencil, warm ivory paper. No camera, no text, no symbols or labels, no border, no branding.

### 03-processing.png
Reference: `../storyboard-audio-diary/02-overnight-processing.png` for the device, older adult and scene. Original: `exec-a4a8dca6-fead-4fc1-80f6-e3e58c2b2fb9.png`.

> ONE standalone landscape 4:3 storyboard illustration matching reference: same off-white tabletop Pi with one large sage button, blank screen, small separate cube speaker. At night it works alone in the foreground, older white-haired woman asleep in another room; device faces away from bed, absolutely no camera. Add a very small simple outlined cloud with upward arrow above device to suggest cloud upload, no branding. Warm ivory paper, soft graphite and restrained colored pencil. Screen blank for later overlay. No letters, text, numbering, border.

### 04-review.png
Reference: `../storyboard-audio-diary/01-bedtime-handoff.png` for the caregiver and style. Original: `exec-9e9a5ca4-9f04-4eeb-ae08-9814ea75fc9b.png`.

> ONE standalone landscape 4:3 storyboard illustration matching the first reference's fictional caregiver with short dark curly hair and gray sweater; restrained graphite and colored pencil, warm ivory paper. Morning: caregiver sits at a desk and reviews a large FRONT FACING computer screen. Screen is a blank pale rectangle, no generated UI or text; the page will be overlaid separately in HTML. Clearly visible screen unobstructed by hand, and caregiver seen in profile at left, screen centrally placed on right. No other person, no branding, no lettering, no border.

### 05-listen.png
Reference: `../storyboard-audio-diary/03-morning-reveal.png` for people, device and style. Original: `exec-a7438884-62e0-4756-8279-56a52f240816.png`.

> ONE standalone landscape 4:3 storyboard illustration matching reference characters and device: white-haired older woman in sage cardigan presses the one large sage button on off-white Pi tabletop display, small separate cube speaker with subtle sound marks. Same dark curly-haired caregiver in gray sits beside her, morning sun. Device screen displays a simple breakfast photo matching the reference. Graphite and restrained colored pencil, warm ivory paper. No camera, no branding, no text, labels or panel border.

## Export

`python3 .agents/skills/storyboard/scripts/render_storyboard.py 'Lab 5/storyboard-audio-diary-v2.html' --output 'Lab 5/storyboard-audio-diary-v2-render.png' --expected-frames 5`

Browser-native render, 1280 CSS pixels at 2×: **2560 × 1954 px**. Five images decoded; no horizontal overflow. The PNG was visually inspected for character and device continuity, readable labels, cropping, and states.
