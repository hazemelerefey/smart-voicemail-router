/* In-browser Web Audio PCM to 16 kHz mono 16-bit WAV encoder (FR2) */

const TARGET_SAMPLE_RATE = 16000;
export const MAX_RECORDING_SECONDS = 60;
const WORKLET_MODULE_PATH = "/svr-pcm-recorder-worklet.js";

export type MicrophoneErrorCode =
  | "insecure_context"
  | "unsupported"
  | "permission_denied"
  | "no_device"
  | "device_in_use"
  | "audio_graph_error";

export class MicrophoneError extends Error {
  readonly code: MicrophoneErrorCode;

  constructor(code: MicrophoneErrorCode, message: string) {
    super(message);
    this.name = "MicrophoneError";
    this.code = code;
  }
}

export interface RecorderOptions {
  onLevel?: (rms: number) => void;
}

export interface RecordingResult {
  blob: Blob;
  file: File;
  durationSeconds: number;
}

function computeRms(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  let sumSq = 0;
  for (let i = 0; i < samples.length; i += 1) {
    sumSq += samples[i] * samples[i];
  }
  return Math.sqrt(sumSq / samples.length);
}

function downsampleBuffer(
  input: Float32Array,
  sourceRate: number,
  targetRate: number
): Float32Array {
  if (sourceRate === targetRate || input.length === 0) {
    return input;
  }
  const ratio = sourceRate / targetRate;
  const newLength = Math.max(1, Math.round(input.length / ratio));
  const result = new Float32Array(newLength);
  // Anti-aliased Hann-windowed sinc resampling to avoid high-frequency foldback
  const halfTaps = 16;
  const cutoff = Math.min(0.45, 0.45 * (targetRate / sourceRate));
  for (let outIdx = 0; outIdx < newLength; outIdx += 1) {
    const center = outIdx * ratio;
    const start = Math.max(0, Math.floor(center) - halfTaps + 1);
    const end = Math.min(input.length - 1, Math.floor(center) + halfTaps);
    let weightedSum = 0;
    let weightTotal = 0;
    for (let i = start; i <= end; i += 1) {
      const dist = i - center;
      const sinc =
        Math.abs(dist) < 1e-6
          ? 2 * cutoff
          : Math.sin(2 * Math.PI * cutoff * dist) / (Math.PI * dist);
      const winPos = (dist + halfTaps) / (2 * halfTaps);
      const hann =
        winPos >= 0 && winPos <= 1 ? 0.5 * (1 - Math.cos(2 * Math.PI * winPos)) : 0;
      const w = sinc * hann;
      weightedSum += input[i] * w;
      weightTotal += w;
    }
    result[outIdx] = weightTotal > 1e-8 ? weightedSum / weightTotal : 0;
  }
  return result;
}

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}

export function encodeMonoWav16k(
  chunks: Float32Array[],
  sourceSampleRate: number
): { blob: Blob; durationSeconds: number } {
  const totalLen = chunks.reduce((sum, c) => sum + c.length, 0);
  const merged = new Float32Array(totalLen);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }

  const samples = downsampleBuffer(merged, sourceSampleRate, TARGET_SAMPLE_RATE);
  const byteLength = 44 + samples.length * 2;
  const buffer = new ArrayBuffer(byteLength);
  const view = new DataView(buffer);

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // Linear PCM
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, TARGET_SAMPLE_RATE, true);
  view.setUint32(28, TARGET_SAMPLE_RATE * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);

  let pos = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    const pcm = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(pos, pcm, true);
    pos += 2;
  }

  const blob = new Blob([buffer], { type: "audio/wav" });
  const durationSeconds = samples.length / TARGET_SAMPLE_RATE;
  return { blob, durationSeconds };
}

function mapMediaError(err: unknown): MicrophoneError {
  if (err instanceof MicrophoneError) return err;
  const name = err && typeof err === "object" && "name" in err ? String((err as { name: string }).name) : "";
  const msg = err && typeof err === "object" && "message" in err ? String((err as { message: string }).message) : "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError" || name === "SecurityError") {
    return new MicrophoneError("permission_denied", msg || "Microphone permission denied.");
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return new MicrophoneError("no_device", msg || "No microphone input device found.");
  }
  if (name === "NotReadableError" || name === "TrackStartError" || name === "AbortError") {
    return new MicrophoneError("device_in_use", msg || "Microphone device is busy or unreadable.");
  }
  return new MicrophoneError("audio_graph_error", msg || "Could not initialize browser audio capture.");
}

export class BrowserWavRecorder {
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private silentGain: GainNode | null = null;
  private chunks: Float32Array[] = [];
  private sampleRate = 48000;
  private active = false;
  private onLevel?: (rms: number) => void;

  private cleanupAudioGraph(): void {
    if (this.workletNode) {
      this.workletNode.port.onmessage = null;
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode.onaudioprocess = null;
      this.processorNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.silentGain) {
      this.silentGain.disconnect();
      this.silentGain = null;
    }
    if (this.stream) {
      for (const track of this.stream.getTracks()) {
        track.stop();
      }
      this.stream = null;
    }
  }

  private setupScriptProcessorFallback(): void {
    if (!this.audioCtx || !this.sourceNode || !this.silentGain) {
      throw new MicrophoneError("audio_graph_error", "Audio graph unavailable.");
    }
    this.processorNode = this.audioCtx.createScriptProcessor(4096, 1, 1);
    this.processorNode.onaudioprocess = (ev: AudioProcessingEvent) => {
      if (!this.active) return;
      const channel = ev.inputBuffer.getChannelData(0);
      const copy = new Float32Array(channel);
      this.chunks.push(copy);
      this.onLevel?.(computeRms(copy));
    };
    this.sourceNode.connect(this.processorNode);
    this.processorNode.connect(this.silentGain);
  }

  async start(options?: RecorderOptions): Promise<void> {
    if (this.active) return;
    if (typeof window !== "undefined" && window.isSecureContext === false) {
      throw new MicrophoneError(
        "insecure_context",
        "Microphone recording requires localhost or HTTPS."
      );
    }
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      throw new MicrophoneError(
        "unsupported",
        "Microphone recording is not supported in this browser."
      );
    }

    this.chunks = [];
    this.onLevel = options?.onLevel;

    try {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
      } catch (constraintErr) {
        const errName =
          constraintErr && typeof constraintErr === "object" && "name" in constraintErr
            ? String((constraintErr as { name: string }).name)
            : "";
        if (errName === "OverconstrainedError" || errName === "TypeError") {
          this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } else {
          throw constraintErr;
        }
      }
    } catch (err) {
      this.abort();
      throw mapMediaError(err);
    }

    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioCtx = new AudioCtx();
      if (this.audioCtx.state === "suspended") {
        await this.audioCtx.resume();
      }
      this.sampleRate = this.audioCtx.sampleRate;
      this.sourceNode = this.audioCtx.createMediaStreamSource(this.stream);
      this.silentGain = this.audioCtx.createGain();
      this.silentGain.gain.value = 0;
      this.silentGain.connect(this.audioCtx.destination);

      let usingWorklet = false;
      if (typeof AudioWorkletNode !== "undefined" && this.audioCtx.audioWorklet) {
        try {
          await this.audioCtx.audioWorklet.addModule(WORKLET_MODULE_PATH);
          this.workletNode = new AudioWorkletNode(this.audioCtx, "svr-pcm-recorder", {
            numberOfInputs: 1,
            numberOfOutputs: 1,
            channelCount: 1,
          });
          this.workletNode.port.onmessage = (ev: MessageEvent<Float32Array>) => {
            if (!this.active) return;
            if (ev.data instanceof Float32Array) {
              const copy = new Float32Array(ev.data);
              this.chunks.push(copy);
              this.onLevel?.(computeRms(copy));
            }
          };
          this.sourceNode.connect(this.workletNode);
          this.workletNode.connect(this.silentGain);
          usingWorklet = true;
        } catch {
          // Strict CSP or worklet initialization error: fall back cleanly to ScriptProcessorNode
          if (this.workletNode) {
            this.workletNode.disconnect();
            this.workletNode = null;
          }
        }
      }

      if (!usingWorklet) {
        this.setupScriptProcessorFallback();
      }
      this.active = true;
    } catch (err) {
      this.abort();
      throw mapMediaError(err);
    }
  }

  async stop(): Promise<RecordingResult> {
    this.active = false;
    this.onLevel = undefined;
    this.cleanupAudioGraph();
    if (this.audioCtx) {
      await this.audioCtx.close();
      this.audioCtx = null;
    }

    if (this.chunks.length === 0) {
      throw new MicrophoneError("audio_graph_error", "No audio frames captured from microphone.");
    }

    const { blob, durationSeconds } = encodeMonoWav16k(this.chunks, this.sampleRate);
    this.chunks = [];
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const file = new File([blob], `voicemail-recording-${stamp}.wav`, {
      type: "audio/wav",
    });
    return { blob, file, durationSeconds };
  }

  abort(): void {
    this.active = false;
    this.onLevel = undefined;
    this.chunks = [];
    this.cleanupAudioGraph();
    if (this.audioCtx) {
      void this.audioCtx.close();
      this.audioCtx = null;
    }
  }
}
