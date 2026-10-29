# Yesterday Together: Audio Diary — storyboard prompts

## Scope and method

- Mode: initial ideation, three chronological frames.
- Content source: `Lab 5/README.md`, Part 2 and Parts F/G/H/I, plus the user's explicit visual constraints. No outside project facts or clinical claims were added.
- Generation: built-in Imagegen, one standalone image per call; opaque backgrounds. Selected files were copied unchanged from the tool's output directory. No raster edits or upscaling were used.
- Layout: the Hub HTML storyboard template, with HTML/CSS captions, number badges and screen status text. The source illustrations intentionally contain no lettering.
- People are fictional. Clothing, room, furniture and generic enclosure are visual choices, not evidence of a real participant, finalized hardware or tested interaction.
- The screen faces its users in frames 1 and 3. At night it faces away from the background bed, with no camera present.
- Review before playback, source-record traceability and the mapping of Pause / Replay Chapter / Next Chapter to one physical button or the screen remain design requirements.
- Style references: `../../../Lab 1/storyboard-iteration-2-render.png` (linework and hierarchy), `../../../Lab 2/storyboard-orange-render.png` (information density). These references supplied style only, not subject matter.

## Caption sequence

1. **Bedtime handoff** — Choose photos and clips together, remove unwanted items and add notes. Then press “Prepare My Diary.”
2. **Overnight processing** — Selected daytime records become a draft while the user rests. No interaction needed.
3. **Morning reveal** — Caregiver review first; then the user presses Play. Approved narration accompanies the matching photo. Pause · Replay Chapter · Next Chapter.

The first frame captures the handoff and its immediate confirmation after selection. The third captures user-initiated playback after review; its caption carries that sequence without adding another panel.

## Selected assets and provenance

All three selected illustrations are **1448 × 1086 px**. Tool originals remain under `/Users/huangjiesen/.codex/generated_images/01a18494-b49a-7723-bdb7-36c4ff9c09b4/`.

| File | Selected tool original | Generation path |
|---|---|---|
| `01-bedtime-handoff.png` | `exec-34d818bf-bec3-4e61-8029-51da4d6707e5.png` | Initial bedtime generation → correct screen orientation → widen the screen for legible HTML copy. |
| `02-overnight-processing.png` | `exec-59d30a87-adaf-4913-b94f-94f4a1d1b649.png` | New independent frame using final frame 1 for device continuity and the earlier overnight draft for room composition. |
| `03-morning-reveal.png` | `exec-f6788207-4714-41bb-b840-2c7d77c5e341.png` | New independent morning frame using final frame 1 → restore a clear user-initiated button press. |

Working drafts were not included in the deliverable folder. The exact prompts that produced the selected assets, including their contributing reference drafts, follow.

## Shared prompt for the initial reference drafts

The following shared text was concatenated with each frame-specific prompt below.

```text
Use case: illustration-story.
Create ONE standalone landscape 4:3 storyboard illustration, not a sheet.
Style references: the first two attached images ONLY supply warm ivory paper, restrained graphite pencil linework, minimal crosshatching, gentle grey hierarchy and spacious compositions. Do not reproduce their subjects, panels, text or devices.
Shared characters: a fictional dignified older adult woman, short softly waved silver hair, simple muted sage cardigan over a light blouse; her adult caregiver companion has short dark hair and a plain grey long-sleeve shirt. Natural adult proportions and ordinary relaxed expressions, never infantile or caricatured; no identifiable real people, names, uniforms, medical cues or exaggerated emotion.
Shared device: a generic Raspberry Pi computer hidden inside an unbranded small rectangular tabletop housing, ONE small landscape screen on its front, ONE large round physical button mounted on a low extension to the screen's right, and ONE small separate square speaker with a graphite grille to the screen's left. All off-white/grey, the single button subtly sage. No logos, identifiable board, exposed specific PCB, camera, microphone, extra buttons or extra device screens.
Keep clear silhouettes and the whole device, hands and heads inside the frame. Plain warm ivory paper, subtle grey pencil strokes with only muted sage clothing/button accent. The image contains NO writing, letters, numerals, captions, title, labels, borders or number badge. All text and interface annotations will be typeset in HTML later. No collage, inset panel or split scene.
```

### Initial bedtime reference

Inputs: the two Lab 1/2 style references above, in that order. Output: `exec-54b98de5-cb31-4619-8980-06c636c5ea0d.png`. This reference was revised because the people initially sat behind the screen.

```text
Frame: bedtime handoff, a single shared moment at a table at home. The older adult and caregiver sit next to each other at equal height, both comfortably engaged, with the older adult making her own choice and reaching to press the one large button. The caregiver is a companion, hands relaxed, never directing the older person's hand or standing over her. A sparse evening window in the upper background shows a crescent moon.
The previous selection of the day's photos/clips, removal of unwanted material and adding notes is described in the external caption: do not add a phone, laptop or pile of paper props. Focus the drawing on the user's handoff action and the device receiving it.
Composition: people occupy the upper half, device occupies a generous lower foreground, its screen front-facing and nearly rectangular to the viewer, no steep perspective. Leave the screen completely BLANK pale ivory for a later HTML confirmation message. The usable blank screen interior should be roughly 42 percent of the full image width and 22 percent of its height, centered in the lower middle. The speaker remains on its left and the user's fingertip rests on the large button to its right. It must be easy to place a three-line confirmation on the blank screen without covering hands.
```

### Initial overnight composition reference

Inputs: the two Lab 1/2 style references, then the initial bedtime reference. Output: `exec-988ad19c-eae6-477b-9285-ee976b6134cb.png`. It supplied only room composition for the selected overnight frame; its older enclosure was replaced.

```text
Additional continuity reference: image 3 is the approved bedtime frame. Reuse its exact generic screen housing, single sage button at right and separate square speaker at left, pencil style and fictional older adult identity. This is a new standalone frame, not an edit of that scene.
Frame: overnight processing. The device quietly works alone on the already-selected daytime records. There is NO camera or sensing apparatus anywhere and it is not observing the person. No hand is touching it, no caregiver is present, and there are no sound-wave marks. This is processing, not playback.
Composition: the same complete device sits on a foreground side table facing toward the viewer. Give its blank front-facing screen generous space so HTML can later typeset "Processing". Leave the screen completely blank pale ivory. In the far rear of the room, through a softly sketched open doorway well behind and to the left of the device, the same older adult is asleep under a blanket in bed. The back of the device faces the far background, its screen faces away from the bed. The sleeping person is a small, respectful, low-detail background presence with only head visible above blanket. A little crescent moon outside a window suggests overnight. Prioritize sparse graphite outlines, substantial empty warm ivory paper and minimal environmental detail. The screen and device remain the visual focus; no ominous mood or surveillance cues.
```

## 01-bedtime-handoff.png — targeted edits

### Correct the viewing geometry

Inputs: initial bedtime reference as edit target, then the two Lab 1/2 style references. Output: `exec-eba6f442-f3d2-4a0e-a74a-b4a2412e3bd4.png`.

```text
Edit the attached bedtime frame to correct ONE spatial problem: the people must be able to see the FRONT of the screen they are using. Currently they sit behind the display. Recompose this as a three-quarter SIDE VIEW, with the two people seated together on the LEFT side of the table and the device to their RIGHT, its screen facing diagonally LEFT toward them and also slightly toward the viewer. We should see the older adult and caregiver in gentle side/three-quarter profiles looking RIGHT at the display, not looking at its back. Make this screen/viewing geometry physically plausible.

Preserve all other identities and components: same fictional silver-haired dignified older adult woman in sage cardigan, same short-dark-haired adult caregiver in grey sitting beside her as a companion, same off-white rectangular generic Pi housing with one screen, exactly ONE large sage button on a low extension to the screen's right, and one small square speaker. Older adult presses the button herself; caregiver hands rest naturally. Keep the device accessible within natural arm reach. Keep the screen completely BLANK pale ivory and spacious enough for later HTML text. No new screens, extra controls, cameras, logos, identities or writing.

Preserve warm ivory paper, restrained grey pencil lines, slight muted sage accent and simple evening window. Use substantially less shaded background detail and more negative space, like the accompanying reference images. Landscape 4:3 ONE standalone scene; all heads, device, gesture and speaker completely in frame; no text, border, labels, collage, panel number or captions.
Input image 1 is the edit target. Images 2 and 3 are pencil style references only.
```

### Widen the screen for readable status copy — selected frame

Input: `exec-eba6f442-f3d2-4a0e-a74a-b4a2412e3bd4.png` as edit target. Output: the selected `01-bedtime-handoff.png`.

```text
Edit this ONE standalone landscape storyboard scene. Preserve the corrected physically plausible side view: same fictional older adult woman and caregiver seated on the LEFT, looking toward and able to see the device screen on the RIGHT. The older adult presses the one round sage button herself, companion hands relaxed. Keep the warm ivory pencil drawing and evening context.

Change the generic device's display from the current narrow portrait/square screen to a WIDE LANDSCAPE screen, roughly two times as wide as tall. The blank screen face should occupy approximately 35 percent of the full image width, so later HTML confirmation text is readable. It can extend across the right half of the composition; reduce people's scale slightly if needed while keeping the hand/button gesture clear. Maintain the screen tilted slightly back and facing diagonally LEFT toward both people and the viewer. Keep one large button on a small ledge beneath the screen toward its right edge and ONE separate compact square speaker just to the device's right. These are an unspecified generic Raspberry Pi housing, not a specific product. No other controls, boards, logos or camera.
The screen stays entirely blank pale ivory. Use much lighter, simpler graphite linework with sparse crosshatching, near-white ivory paper and almost no colored fill outside the sage cardigan/button. Reduce furniture/background detail. No written text, border, badge, labels, collage or inset panels. Keep all heads, gesture, speaker and device fully visible.
```

## 02-overnight-processing.png — selected frame

Inputs: final `01-bedtime-handoff.png` for device/character/style continuity, then `exec-988ad19c-eae6-477b-9285-ee976b6134cb.png` for composition only.

```text
Use case: illustration-story. Create ONE standalone landscape 4:3 storyboard illustration of overnight processing.
Image 1 supplies the APPROVED generic device design, fictional older adult identity, and warm ivory pencil style. Image 2 supplies ONLY the desired spatial composition of a quiet device in the foreground facing away from a background bed; replace its old device with the device from image 1.

The SAME complete unbranded Raspberry Pi housing from image 1 is on a side table outside the sleeping room: a wide landscape screen tilted gently backward, one large sage round button on its low base below the screen, and one compact separate square speaker to the RIGHT. No specific visible board, logos, cameras, microphone or additional controls. No one touches the device; no sound waves because it is processing rather than playing audio. Keep the screen completely BLANK pale ivory for "Processing" to be typeset later in HTML. The screen faces the foreground viewer and AWAY from the sleeping person.

The same fictional silver-haired older adult is asleep under a blanket in a distant background doorway on the left, with only head visible. Keep that figure small and respectful. No caregiver is present. A subtle moon beyond a window indicates overnight. The device is working through selected daytime records, not observing or recording at night. Render a quiet, sparse scene with generous warm ivory blank space, restrained graphite linework, minimal crosshatching and only a subtle sage button accent. Keep all of the device and speaker within the image. No text, names, labels, number badges, border, collage or extra panels.
```

## 03-morning-reveal.png

### Morning generation

Input: final `01-bedtime-handoff.png` for continuity. Output: `exec-6cda5fa4-e884-449a-bb74-249ea3681941.png`.

```text
Use case: illustration-story. Create ONE standalone landscape 4:3 storyboard illustration of morning reveal, using the attached approved bedtime scene for exact character, device, perspective and pencil style continuity.

Preserve its physically plausible side view: same fictional silver-haired older adult woman in sage cardigan and same short-dark-haired adult caregiver in grey seated next to each other on the LEFT of the table, able to see the device screen to the RIGHT. The older adult herself has just pressed the one large sage button and now listens at her own pace. Caregiver hands stay relaxed, the caregiver is a companion at the same seated height, not directing the woman's body or operating another device. Natural dignified adult proportions and expressions, no recognizable real person and no name.

Preserve the EXACT device design from the reference: generic off-white Raspberry Pi housing with a wide landscape screen tilted gently back, one big round sage button on the base below its right area, one small separate square speaker at its RIGHT. Keep the screen facing diagonally toward both people and viewer. No branding, specific circuit board, camera, extra controls, extra device or screens. On the screen show a simple monochrome stored photograph of a cup and plate on a breakfast table, recognizable as a past daytime moment, no words or UI controls. Add two tiny graphite sound arcs next to the speaker to indicate the approved narration being played. The caregiver has ALREADY reviewed the draft; do not show simultaneous reviewing and playback, approval seals, check marks or certification. External captions will clarify this is intended behavior.

Change the evening window to soft morning daylight with NO moon. Keep a simple, airy graphite drawing on warm ivory paper, sparse crosshatching, mostly uncolored with subtle sage accents, minimal background detail. All heads, hands, button, device and speaker fully in frame. No written text, names, panel numbers, border, labels, collage or inset panels.
```

### Clarify the user's initiating gesture — selected frame

Input: `exec-6cda5fa4-e884-449a-bb74-249ea3681941.png` as edit target. Output: the selected `03-morning-reveal.png`.

```text
Edit only the older adult woman's hand/arm pose in this standalone morning storyboard illustration. Her near hand should extend naturally across the tabletop, with her index fingertip gently pressing the ONE large sage physical button on the device, clearly showing that SHE initiates playback. Her other hand may rest comfortably by her body; do not prop her chin on her hand. Preserve the exact two fictional people's faces, clothing, companion seated at equal height with relaxed hands, device geometry, single button, right-hand speaker, source-photo vignette of cup and plate on the screen, two small sound arcs, daylight window, perspective, warm ivory graphite style, dimensions and all other elements. Keep the screen visible and do not obstruct its photo. No new controls, texts, names, logos, borders, panels or UI icons.
```

## Export and verification

From the Hub root:

```bash
python3 .agents/skills/storyboard/scripts/render_storyboard.py \
  "Lab 5/storyboard-audio-diary.html" \
  --output "Lab 5/storyboard-audio-diary-render.png" \
  --expected-frames 3
```

The export uses 1280 CSS px at device scale 2. Actual output: **2560 × 1154 px**, with three decoded images and no horizontal overflow. The final PNG was visually checked for legibility, screen-copy placement, cropping, consistent characters and hardware, and the bedtime → overnight → morning sequence. There was no Raspberry Pi connection, device test, clinical evaluation, commit, push or website deployment.
