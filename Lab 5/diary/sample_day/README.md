# Synthetic sample day: 2026-10-27

Ten AI-generated, fictional smartphone-style images for testing chronological ordering, near-duplicate removal, quality filtering, event grouping, and evidence-bounded narration for Yesterday Together. People, relationships, events and times are synthetic. Generated individually with OpenAI built-in image generation (the tool did not expose a precise model version); the first image was used as a visual reference for the others. JPEGs are resized from generated PNGs.

- `20261027-HHMMSS.jpg`: pipeline image inputs. The filename supplies the fictional local capture time; no timezone is encoded. `exiftool` was not available, so DateTimeOriginal was not written.
- `caregiver_notes.json`: fictional bedtime notes available to the pipeline. Anna’s identity comes from these notes, not from the image.
- `ground_truth.json`: per-image evaluation manifest, expected grouping and test purposes. **Do not feed it to the pipeline.**
- `prompts.md`: actual generation prompts and reference.

The organizer image does not establish that anyone took medication. The 15:30 frame is intentionally underexposed. The two reading images show small background and pose changes; the two breakfast frames are exceptionally similar. Synthetic imagery is useful for controlled tests but does not establish performance on real phone photos. The directory is intentionally flat: select the JPEGs and caregiver notes explicitly rather than globbing all JSON files into model input.
