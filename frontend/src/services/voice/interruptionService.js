import {
  getVolume,
} from "./audioAnalyser";

import {
  getInterruptionThreshold,
} from "./vadService";

import {
  isSpeaking,
} from "./ttsService";

const SPEECH_CONFIRMATION_MS = 220;

let interruptionAnimationFrame =
  null;

let interruptionHandler =
  null;

export function setInterruptionHandler(
  handler
) {
  interruptionHandler = handler;
}

export function startInterruptionDetection() {
  stopInterruptionDetection();

  let speechStartTime = null;

  const check = () => {
    if (!isSpeaking()) {
      return;
    }

    const volume = getVolume();

    const threshold =
      getInterruptionThreshold();

    if (volume > threshold) {
      if (speechStartTime === null) {
        speechStartTime =
          performance.now();
      }

      const duration =
        performance.now() -
        speechStartTime;

      if (
        duration >=
        SPEECH_CONFIRMATION_MS
      ) {
        console.log(
          "CUSTOMER INTERRUPTED CASHIER"
        );

        stopInterruptionDetection();

        interruptionHandler?.();

        return;
      }
    } else {
      speechStartTime = null;
    }

    interruptionAnimationFrame =
      requestAnimationFrame(check);
  };

  interruptionAnimationFrame =
    requestAnimationFrame(check);
}

export function stopInterruptionDetection() {
  if (!interruptionAnimationFrame) return;

  cancelAnimationFrame(
    interruptionAnimationFrame
  );

  interruptionAnimationFrame = null;
}