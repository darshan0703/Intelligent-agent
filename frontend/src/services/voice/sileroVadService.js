import { MicVAD } from "@ricky0123/vad-web";

let vad = null;
let initializing = false;
let initialized = false;

export async function initializeSileroVAD({
  onSpeechStart,
  onSpeechEnd,
}) {
  if (initialized || initializing) {
    return vad;
  }

  initializing = true;

  try {
    console.log(
      "INITIALIZING SILERO VAD..."
    );

    vad = await MicVAD.new({
      /*
       * IMPORTANT:
       *
       * Load Silero's model and
       * AudioWorklet files directly
       * from the CDN.
       *
       * This avoids Vite trying to
       * dynamically load ONNX files
       * from /node_modules/.vite/deps/
       */

      baseAssetPath:
        "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.30/dist/",

      /*
       * Load ONNX Runtime WASM and
       * .mjs backend files from CDN.
       *
       * This fixes the error:
       *
       * Failed to fetch dynamically
       * imported module
       *
       * ort-wasm-simd-threaded.mjs
       */

      onnxWASMBasePath:
        "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/",

      /*
       * Use the microphone stream
       * already managed by the
       * browser.
       */

      positiveSpeechThreshold: 0.7,

      negativeSpeechThreshold: 0.4,

      /*
       * In version 0.0.30,
       * these values are measured
       * in milliseconds.
       */

      redemptionMs: 800,

      minSpeechMs: 250,

      /*
       * Called when Silero believes
       * human speech has started.
       */

      onSpeechStart: () => {
        console.log(
          "SILERO: SPEECH STARTED"
        );

        onSpeechStart?.();
      },

      /*
       * Called when Silero believes
       * the customer has stopped
       * speaking.
       */

      onSpeechEnd: (audio) => {
        console.log(
          "SILERO: SPEECH ENDED"
        );

        onSpeechEnd?.(audio);
      },

      /*
       * Prevent false speech events
       * from becoming errors.
       */

      onVADMisfire: () => {
        console.log(
          "SILERO: VAD MISFIRE"
        );
      },
    });

    initialized = true;

    console.log(
      "SILERO VAD READY"
    );

    return vad;

  } catch (error) {
    console.error(
      "SILERO VAD INITIALIZATION ERROR:",
      error
    );

    vad = null;

    initialized = false;

    throw error;

  } finally {
    initializing = false;
  }
}

export async function startSileroVAD() {
  if (!vad || !initialized) {
    console.error(
      "SILERO VAD NOT INITIALIZED"
    );

    return;
  }

  console.log(
    "STARTING SILERO VAD"
  );

  try {
    await vad.start();
  } catch (error) {
    console.error(
      "SILERO START ERROR:",
      error
    );
  }
}

export async function pauseSileroVAD() {
  if (!vad) {
    return;
  }

  console.log(
    "PAUSING SILERO VAD"
  );

  try {
    await vad.pause();
  } catch (error) {
    console.error(
      "SILERO PAUSE ERROR:",
      error
    );
  }
}

export async function destroySileroVAD() {
  if (!vad) {
    return;
  }

  console.log(
    "DESTROYING SILERO VAD"
  );

  try {
    await vad.destroy();

  } catch (error) {
    console.error(
      "SILERO VAD CLEANUP ERROR:",
      error
    );
  }

  vad = null;

  initialized = false;

  initializing = false;
}

export function isSileroVADReady() {
  return initialized && vad !== null;
}