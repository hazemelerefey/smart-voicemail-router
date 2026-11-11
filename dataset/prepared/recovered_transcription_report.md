# SVR recovered-files transcription + re-transcription experiment — report

Date: 2026-11-11. No model was trained. No source CSVs or recovered audio were modified. Nothing pushed to GitHub.

## Model and settings (no fallback needed)

- Engine: faster-whisper 1.2.1, model **Systran/faster-whisper-large-v3**, `compute_type=int8`, CPU, `cpu_threads=4`, `language="ar"`, `beam_size=5`, `temperature=0.0`, no VAD filter, no prompt.
- The requested large-v3 fit in memory (peak RSS ~3.1 GB on a 7.7 GB machine), so no fallback model was used.
- Two environment fixes were needed to get there (both local, both documented here): the HF Hub single-connection download of the 3.1 GB `model.bin` stalled at 268 MB, so the file was fetched in 8 parallel ranged parts and verified by SHA-256 (`69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1`, exact match) before being placed in the HF cache; and PyAV 19 broke faster-whisper's audio decoding, so `av` was pinned to 13.1.0 in `.venv-eda`. The model now sits in the local HF cache, so reruns are offline.
- `text_norm` replicates the existing `transcripts_clean.csv` normalization (alef forms to ا, ة to ه, ى to ي, diacritics/tatweel dropped, punctuation dropped, lowercased). Review flags reuse the original pipeline's verified thresholds: `low_confidence` = min_avg_logprob < -0.5 (exactly the cutoff in the original 6,024 rows), `too_short` = 2 words or fewer, plus `hallucination_suspect` (YouTube-outro phrases), `prompt_leak` ("بالعاميه المصريه"), `repetition` (repeated 4-word gram).

## Long-file chunks

Source `الكل ان شاء الله\1757.mp4` (125.922 s) was split from `dataset/extracted/` into `dataset/prepared/recovered_audio/chunks/`: `1757_seg0.wav` 0-60 s (verified 60.000 s), `1757_seg1.wav` 60-120 s (verified 60.000 s), `1757_seg2.wav` 120-125.922 s (verified 5.922 s). All 16 kHz mono WAV.

## Recovered transcripts — 25 of 28 usable

Output: `dataset/prepared/recovered_transcripts.csv` (28 rows, one per audio unit).

- **25 single files: all clean, no review flags.** min_avg_logprob -0.068 to -0.436 (mean -0.23), 13-20 words each, coherent Egyptian-dialect complaints and thanks. These can go to labeling as-is.
- **Weakest clean row:** `WhatsApp Audio 2025-11-22 at 2.07.14 PM (5).mp4` (lp -0.436) has a garbled middle ("بوكا بميديني... 10 صيام بادري"); it stays unflagged under the original -0.5 cutoff, but the labeler should watch it.
- **All 3 long-file segments need review (needs_review = true):**
  - Seg 0 (0-60 s, lp -0.411): praise for the support agent, but ends with a hallucinated YouTube outro ("اشتركوا في القناة").
  - Seg 1 (60-120 s, lp -0.276): the same ~20-word praise phrase loops about 6 times (152 words) — classic repetition hallucination; do not use as-is.
  - Seg 2 (120-125.9 s, lp -0.629): transcript is only "اشتركوا في القناة" — pure hallucination; the tail is probably silence/music. Not usable.
  - The long file is a thanks/praise message, not a complaint. Its three segments need human listening before any of them joins training; seg 2 should be dropped, seg 1 re-transcribed in smaller pieces or by hand.

## Re-transcription experiment — does NOT help

Output: `dataset/prepared/retranscription_experiment.json` (30 rows).

- Population: the 219 rows from `labeled_full_v1.csv` with `confidence == low` AND (`complaint_category == other` OR `customer_state == unclear`) — the rows the labeling report says "could not be labeled confidently at all". Sample: random 30, `random_state=42`. Each was re-transcribed with the exact same Whisper setup as above, from `dataset/preprocessed/audio_16k/`.
- Result after hand-reviewing every old/new pair: **improved 0, same 30, worse 0.**
- 9 of 30 new transcripts are byte-identical to the original; median similarity 0.976; mean min_avg_logprob -0.247 (old) vs -0.245 (new), a change of +0.002 — nothing.
- The still-garbled rows came back as *different* word salad, equally unlabelable. The two rows that first looked "improved" only changed dialect register (MSA wording to Egyptian dialect) with a logprob gain; the complaint was equally clear in both versions.
- **Conclusion: exclude the 219 from training.** Re-running the same model on all 219 would reproduce the same transcripts for ~2.5 hours of CPU. The garbling lives in the audio (dialect + noise + short clips), not in the decoder. If the team wants to rescue any of them, the next test must be a genuinely different approach (VAD filtering, different decoding settings, or human listening) — not a same-model rerun.

## Process notes

- A VM reboot mid-run (07:43 EET) killed the first transcription pass at 27/58 and wiped /tmp, including its checkpoint. The run was restarted from scratch with the checkpoint and scripts moved to `~/workspace/svr_work/` (persistent). The second pass reproduced the first pass's results exactly (identical logprobs and texts on overlapping files), confirming the decoding is deterministic.
- Total transcription time for 58 units: ~55 minutes of CPU on this machine.
- Work files (script, sample list, checkpoint, log): `~/workspace/svr_work/`. Model backup copy: `~/workspace/svr_model_dl/model.bin`.
