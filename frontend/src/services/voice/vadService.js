import { getVolume, hasAnalyser } from "./audioAnalyser";

const SPEECH_CONFIRMATION_MS = 250;

const NORMAL_THRESHOLD_MIN = 0.025;
const NORMAL_THRESHOLD_MAX = 0.12;

const INTERRUPTION_THRESHOLD_MIN = 0.05;
const INTERRUPTION_THRESHOLD_MAX = 0.18;

const NOISE_ADAPTATION_RATE = 0.02;

let noiseFloor = 0;
let calibrating = false;
let vadAnimationFrame = null;

export async function calibrateNoiseFloor() {
  if (!hasAnalyser() || calibrating) return;

  calibrating = true;

  const samples = [];

  console.log("CALIBRATING MICROPHONE...");

  const start = performance.now();

  while (performance.now() - start < 900) {
    samples.push(getVolume());

    await new Promise((resolve) =>
      requestAnimationFrame(resolve)
    );
  }

  if (samples.length > 0) {
    const sorted = [...samples].sort(
      (a, b) => a - b
    );

    /*
     * Use the lower part of the samples.
     *
     * This prevents a random loud sound during
     * calibration from becoming the noise floor.
     */
    const percentileIndex = Math.floor(
      sorted.length * 0.3
    );

    const baseline =
      sorted[percentileIndex] || 0;

    noiseFloor = Math.min(
      Math.max(baseline, 0.005),
      0.08
    );
  } else {
    noiseFloor = 0.01;
  }

  console.log(
    "VAD NOISE FLOOR:",
    noiseFloor
  );

  console.log(
    "SPEECH START THRESHOLD:",
    getNormalSpeechThreshold()
  );

  calibrating = false;
}

export function getNormalSpeechThreshold() {
  /*
   * Speech must be noticeably louder than
   * the current environment.
   */
  const adaptive =
    noiseFloor +
    Math.max(
      noiseFloor * 2,
      0.02
    );

  return Math.min(
    Math.max(
      adaptive,
      NORMAL_THRESHOLD_MIN
    ),
    NORMAL_THRESHOLD_MAX
  );
}

export function getSpeechStopThreshold() {
  /*
   * Lower threshold for maintaining speech.
   *
   * This hysteresis prevents speech detection
   * from rapidly switching on/off when volume
   * fluctuates around one threshold.
   */
  const startThreshold =
    getNormalSpeechThreshold();

  return Math.max(
    noiseFloor +
      Math.max(
        noiseFloor * 1.1,
        0.012
      ),
    startThreshold * 0.65
  );
}

export function getInterruptionThreshold() {
  const adaptive =
    noiseFloor +
    Math.max(
      noiseFloor * 2.5,
      0.04
    );

  return Math.min(
    Math.max(
      adaptive,
      INTERRUPTION_THRESHOLD_MIN
    ),
    INTERRUPTION_THRESHOLD_MAX
  );
}

/*
 * Slowly adapt the noise floor.
 *
 * IMPORTANT:
 * We only adapt upward/downward gradually.
 * Otherwise actual customer speech could
 * become part of the noise floor.
 */
function adaptNoiseFloor(volume) {
  const currentSpeechThreshold =
    getNormalSpeechThreshold();

  /*
   * Only learn environmental noise when
   * the sound is below the speech threshold.
   */
  if (volume < currentSpeechThreshold) {
    noiseFloor =
      noiseFloor *
        (1 - NOISE_ADAPTATION_RATE) +
      volume *
        NOISE_ADAPTATION_RATE;

    noiseFloor = Math.min(
      Math.max(noiseFloor, 0.005),
      0.08
    );
  }
}

export function startVoiceDetection({
  shouldDetect,
  onSpeechDetected,
}) {
  stopVoiceDetection();

  let speechStartTime = null;

  const check = () => {
    if (!shouldDetect()) {
      vadAnimationFrame =
        requestAnimationFrame(check);

      return;
    }

    const volume = getVolume();

    /*
     * Continuously learn the environment.
     *
     * Restaurant noise changes constantly.
     */
    adaptNoiseFloor(volume);

    const speechStartThreshold =
      getNormalSpeechThreshold();

    if (
      volume >
      speechStartThreshold
    ) {
      if (speechStartTime === null) {
        speechStartTime =
          performance.now();

        console.log(
          "POSSIBLE SPEECH:",
          volume,
          "THRESHOLD:",
          speechStartThreshold
        );
      }

      const duration =
        performance.now() -
        speechStartTime;

      /*
       * Sound must remain above threshold
       * for a short period.
       *
       * This rejects clicks, tray sounds,
       * short impacts, etc.
       */
      if (
        duration >=
        SPEECH_CONFIRMATION_MS
      ) {
        console.log(
          "CUSTOMER SPEECH DETECTED:",
          volume,
          "THRESHOLD:",
          speechStartThreshold,
          "NOISE FLOOR:",
          noiseFloor
        );

        speechStartTime = null;

        onSpeechDetected();

        return;
      }
    } else {
      /*
       * Sound dropped below speech-start
       * threshold before confirmation.
       */
      speechStartTime = null;
    }

    vadAnimationFrame =
      requestAnimationFrame(check);
  };

  vadAnimationFrame =
    requestAnimationFrame(check);
}

export function stopVoiceDetection() {
  if (!vadAnimationFrame) return;

  cancelAnimationFrame(
    vadAnimationFrame
  );

  vadAnimationFrame = null;
}

export function getNoiseFloor() {
  return noiseFloor;
}

export function resetVAD() {
  stopVoiceDetection();

  noiseFloor = 0;

  calibrating = false;
}