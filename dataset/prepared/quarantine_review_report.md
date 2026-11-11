# SVR quarantine review and excluded verification

Date: 2026-11-11. Scope: the 143 quarantined rows and the 498 excluded rows of the
6,522-file SVR dataset. No model was trained. No audio was transcribed. No source
file was modified. Per-row decisions are in `quarantine_decisions.csv`; all
verification numbers are in `excluded_verification.json`.

## Quarantine decisions (143 rows)

| Decision | Count |
|---|---|
| include | 62 |
| exclude | 18 |
| pending_retranscription | 63 |

Decision rule used throughout: include only when the transcript is intelligible
enough that a labeler can route it confidently (clear intent/topic despite one or
two garbled words); pending when the transcript is garbled, unintelligible, or too
vague to label but the audio may yield a better transcript; exclude only when the
transcript is confidently not usable customer speech.

By flag group:

- low_confidence only (106): include 51, pending 54, exclude 1. The 51 includes
  are coherent Egyptian-dialect complaints (refunds, deductions, network, bundle,
  router) with isolated misrecognized words. The 54 pending are word salad,
  incoherent, or too vague to route (logprob down to -1.42). The 1 exclude
  (0035.m4a) is a speaker saying they forgot what to say: no routable content
  even if the transcript is perfect.
- hallucination_suspect (15): exclude 15. Nine share the identical hallucinated
  text "اشتركوا في القناة", three share "شكرا للمشاهدة", two share
  "شكرا لكم على المشاهدة", one is a longer video-outro variant. These are
  Whisper video-outro hallucinations, not customer speech.
- prompt_leak (3): pending 3. All three transcripts are leaked prompt text
  ("اتصالات بالعامية المصرية"), not customer speech; the audio may hold a real
  message.
- repetition (2): include 1 (72-word bill-increase complaint, logprob -0.19,
  natural customer rambling), pending 1 (0510.aac, model loop repeats
  "not available" 3x at the tail).
- too_short, non-hallucination (7): exclude 2 (confident 2-word thanks /
  video-caption fragment, nothing to recover), pending 5 (2-word fragments at
  logprob -0.68 to -1.10; audio may contain a real message).
- silence over 50%, no review flag (10): include 10. All have coherent,
  complete transcripts at high confidence (logprob -0.06 to -0.41, 3-17 words);
  the silence is in the audio, not the transcript. Three share wording with a
  train-ready row but are distinct recordings (unique md5).

What the 62 includes still need: human labels before training. What the 63
pending need: the separate re-transcription test; do not train on their current
text. The 18 excludes stay out.

## Excluded verification (498 rows)

- Duplicates (470): confirmed true duplicates 470/470, unclear 0. Every excluded
  duplicate shares its source-file md5 with another file: 449 with a train-ready
  file (the kept copy), 17 with a quarantine file, 4 with only other excluded
  copies. Duplicates stay excluded.
- Duplicate overlap with train-ready: 0 excluded files appear in train-ready by
  filename; 0 internal md5 duplicates inside train-ready; 0 PCM-hash duplicates
  in train-ready (5,881/5,881 unique decoded PCM SHA256). Excluded duplicates
  have no transcript rows, so a text_norm overlap check against them is not
  applicable; the audio-level md5 check above is the executable version. Note:
  242 train-ready rows share text_norm with another train-ready row (104 groups)
  — same wording, distinct recordings — which is natural repetition, not audio
  duplication.
- Recovery coverage (26): exact match to the disposition manifest, 0 mismatches:
  18 low_snr (afftdn denoise), 6 clipped (adeclip), 1 mostly_silence
  (silenceremove trim), 1 too_long (chunked into 3 x 60s segments). All 26
  verified=true and all 26 recovered audio files are on disk. No non-duplicate
  excluded row remains recoverable beyond the 26: the only non-duplicate
  excluded rows not recovered are the 2 too_short rows.
- Too_short (2): 0797.mpeg 0.432s, WhatsApp Audio 2025-11-27 at 2.07.06 PM
  (1).aac 0.725s. Both under 1s; the shortest train-ready file is 1.914s.
  Confirmed unrecoverable; no recovery op applies.
- Recovered files are NOT train-ready yet: they have 0 transcript rows and await
  transcription (including 3 segment transcripts for the 125.9s too_long file).
  Recovery was audio repair only.

## Clipping verification

Correction to the brief: 312 clipped rows sit in train-ready and 8 more in
quarantine, for 320 clipped rows in the transcribed pool. All 320 are under 1%
(clip_pct mean 0.031%, max 0.497%; train-ready clipped mean 0.030%, max 0.473%;
clean rows 0.000%).

| | Clipped (n=312) | Clean (n=5,569) |
|---|---|---|
| mean min_avg_logprob | -0.1933 | -0.1922 |
| median min_avg_logprob | -0.1794 | -0.1764 |
| share logprob < -0.5 | 0.00% (0 rows) | 0.00% (0 rows) |
| share logprob < -0.4 | 2.24% | 3.02% |
| share needs_review | 0.00% | 0.00% |
| mean max_no_speech_prob | 0.00592 | 0.00685 |
| mean words | 19.49 | 15.73 |

Welch t-test on logprob: t = -0.24, p = 0.81. No systematic difference. The
tolerate decision is safe: clipped rows are statistically indistinguishable from
clean rows on transcription confidence, and slightly longer on average.

## Duration drift verification

inventory_corrected.csv durations vs audio_decode.json, train-ready set
(5,881 files checked): 0 mismatches, max absolute difference 0.000000s. The
correction is confirmed. For reference, the pre-correction inventory drift was
82 files over 0.1s (79 .aac, 3 .m4a; max 0.487s, mean 0.014s), matching the
audit summary exactly.

## Open items (not decided here)

- 63 quarantined rows await the re-transcription test; 26 recovered files await
  transcription. Neither group joins training until then.
- The 62 included quarantined rows still need human labels.
- Rights/consent for the dataset remains unconfirmed (audit issue); that is a
  separate blocker, not covered by this review.
