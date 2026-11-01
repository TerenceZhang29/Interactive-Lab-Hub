# Synthetic sample day: 2026-10-28

A fictional second test day for Yesterday Together. Images are synthetic, generated using the first test day as visual reference; they are not records of real people or events. This folder supplies seven planned video opening frames and two timestamped still photographs. **No video has been generated.**

- `keyframes/clipNN_start.png`: starting images for future videos, not direct pipeline input.
- `20261028-HHMMSS.jpg`: two timestamped photo inputs.
- `shotlist.json`: planned clips, filenames, durations, motion prompts and purposes. The 10:15 walk comprises five consecutive 12-second segments; generate each after the first from the previous segment’s last frame and stitch into the one timestamped MP4.
- `caregiver_notes.json`: fictional notes for the pipeline. Anna’s name and relationship come from the note; the delivery visitor has no identifying note.
- `ground_truth.json`: evaluation-only scene labels and expected filtering; never feed this file to the pipeline.
- `prompts.md`: image generation prompts and references.

For a future run put the two JPEGs, the generated timestamp-named MP4s, and caregiver notes in a selected input folder. The script scans only the top level, reads timestamps from names, samples video every 5 seconds by default, and groups retained frames when the gap is at most 30 minutes. Its defaults drop grayscale mean below 45, Laplacian variance below 40, and perceptual hash differences at most 6 against a retained frame within 10 minutes. Segment seams, dark-frame filtering and near-duplicates must be measured on the actual generated videos; they are not verified by these stills. Synthetic data cannot establish real-world performance.
