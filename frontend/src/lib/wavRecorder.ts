/* In-browser Web Audio PCM to 16 kHz mono 16-bit WAV encoder (FR2) */

const TARGET_SAMPLE_RATE = 16000;
export const MAX_RECORDING_SECONDS = 60;

export interface RecordingResult {
  blob: Blob;
  file: File;
  durationSeconds: number;
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

const WORKLET_PROCESSOR_SOURCE = `
class SvrPcmRecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0] && input[0].length > 0) {
      this.port.postMessage(new Float32Array(input[0]));
    }
    return true;
  }
}
registerProcessor("svr-pcm-recorder", SvrPcmRecorderProcessor);
`;

export class BrowserWavRecorder {
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private workletBlobUrl: string | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private chunks: Float32Array[] = [];
  private sampleRate = 48000;
  private active = false;

  private cleanupAudioGraph(): void {
    if (this.workletNode) {
      this.workletNode.port.onmessage = null;
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.workletBlobUrl) {
      URL.revokeObjectURL(this.workletBlobUrl);
      this.workletBlobUrl = null;
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
    if (this.stream) {
      for (const track of this.stream.getTracks()) {
        track.stop();
      }
      this.stream = null;
    }
  }

  async start(): Promise<void> {
    if (this.active) return;
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone recording is not supported in this browser.");
    }
    this.chunks = [];
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.audioCtx = new AudioCtx();
    this.sampleRate = this.audioCtx.sampleRate;
    this.sourceNode = this.audioCtx.createMediaStreamSource(this.stream);

    if (typeof AudioWorkletNode !== "undefined" && this.audioCtx.audioWorklet) {
      const blob = new Blob([WORKLET_PROCESSOR_SOURCE], { type: "application/javascript" });
      this.workletBlobUrl = URL.createObjectURL(blob);
      await this.audioCtx.audioWorklet.addModule(this.workletBlobUrl);
      this.workletNode = new AudioWorkletNode(this.audioCtx, "svr-pcm-recorder", {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        channelCount: 1,
      });
      this.workletNode.port.onmessage = (ev: MessageEvent<Float32Array>) => {
        if (!this.active) return;
        if (ev.data instanceof Float32Array) {
          this.chunks.push(new Float32Array(ev.data));
        }
      };
      this.sourceNode.connect(this.workletNode);
      this.workletNode.connect(this.audioCtx.destination);
    } else {
      this.processorNode = this.audioCtx.createScriptProcessor(4096, 1, 1);
      this.processorNode.onaudioprocess = (ev: AudioProcessingEvent) => {
        if (!this.active) return;
        const channel = ev.inputBuffer.getChannelData(0);
        this.chunks.push(new Float32Array(channel));
      };
      this.sourceNode.connect(this.processorNode);
      this.processorNode.connect(this.audioCtx.destination);
    }
    this.active = true;
  }

  async stop(): Promise<RecordingResult> {
    this.active = false;
    this.cleanupAudioGraph();
    if (this.audioCtx) {
      await this.audioCtx.close();
      this.audioCtx = null;
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
    this.chunks = [];
    this.cleanupAudioGraph();
    if (this.audioCtx) {
      void this.audioCtx.close();
      this.audioCtx = null;
    }
  }
}
