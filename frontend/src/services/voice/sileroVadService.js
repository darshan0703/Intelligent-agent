import { MicVAD } from "@ricky0123/vad-web";

let vad = null;
let initializing = false;
let initialized = false;

export async function initializeSileroVAD({
  onSpeechStart,
  onSpeechEnd,
}) {
  // Already initialized
  if (initialized && vad) {
    console.log("SILERO VAD ALREADY READY");
    return vad;
  }

  // Prevent duplicate initialization
  if (initializing) {
    console.log("SILERO VAD INITIALIZATION ALREADY IN PROGRESS");
    return vad;
  }

  initializing = true;

  try {
    console.log("=================================");
    console.log("INITIALIZING SILERO VAD...");
    console.log("=================================");

    vad = await MicVAD.new({
      baseAssetPath:
        "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.30/dist/",

      onnxWASMBasePath:
        "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/",

      /*
       * Slightly more sensitive than the previous settings.
       * This helps detect normal microphone speech.
       */
      positiveSpeechThreshold: 0.5,
      negativeSpeechThreshold: 0.3,

      /*
       * Keep speech detection responsive.
       */
      redemptionMs: 500,
      minSpeechMs: 150,

      onSpeechStart: () => {
        console.log("SILERO: SPEECH STARTED");

        if (onSpeechStart) {
          onSpeechStart();
        }
      },

      onSpeechEnd: (audio) => {
        console.log("SILERO: SPEECH ENDED");

        if (onSpeechEnd) {
          onSpeechEnd(audio);
        }
      },

      onVADMisfire: () => {
        console.log("SILERO: VAD MISFIRE");
      },
    });

    initialized = true;

    console.log("=================================");
    console.log("SILERO VAD READY");
    console.log("=================================");

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

  console.log("STARTING SILERO VAD");

  try {
    await vad.start();

    console.log(
      "SILERO VAD LISTENING"
    );
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

  console.log("PAUSING SILERO VAD");

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

  console.log("DESTROYING SILERO VAD");

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