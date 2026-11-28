/* Same-origin AudioWorklet processor for 16 kHz mono WAV recording under strict CSP. */
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
