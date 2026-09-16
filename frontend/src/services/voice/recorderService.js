import { getMicrophone } from "./microphoneService";

const MAX_RECORDING_MS = 15000;

let mediaRecorder = null;
let recordingTimer = null;

let listening = false;

function getSupportedMimeType() {
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];

  for (const type of types) {
    if (
      typeof MediaRecorder !== "undefined" &&
      MediaRecorder.isTypeSupported(type)
    ) {
      return type;
    }
  }

  return "";
}

export function isRecording() {
  return listening;
}

export async function startRecording({
  onComplete,
  onError,
}) {
  if (listening || mediaRecorder) {
    return;
  }

  try {
    const stream =
      await getMicrophone();

    const mimeType =
      getSupportedMimeType();

    mediaRecorder = mimeType
      ? new MediaRecorder(
          stream,
          { mimeType }
        )
      : new MediaRecorder(stream);

    const recorder =
      mediaRecorder;

    const chunks = [];

    recorder.ondataavailable =
      (event) => {
        if (
          event.data &&
          event.data.size > 0
        ) {
          chunks.push(
            event.data
          );
        }
      };

    recorder.onstop = () => {
      listening = false;
      mediaRecorder = null;

      clearTimeout(
        recordingTimer
      );

      recordingTimer = null;

      if (chunks.length === 0) {
        console.log(
          "EMPTY RECORDING"
        );

        onComplete?.(null);

        return;
      }

      const recorderMimeType =
        recorder.mimeType ||
        mimeType ||
        "audio/webm";

      const blob =
        new Blob(
          chunks,
          {
            type:
              recorderMimeType,
          }
        );

      console.log(
        "CUSTOMER RECORDING COMPLETE:",
        blob.size,
        "bytes"
      );

      onComplete?.({
        blob,
        mimeType:
          recorderMimeType,
      });
    };

    recorder.onerror =
      (event) => {
        console.error(
          "MEDIA RECORDER ERROR:",
          event
        );

        listening = false;
        mediaRecorder = null;

        clearTimeout(
          recordingTimer
        );

        recordingTimer = null;

        onError?.(event);
      };

    recorder.start(250);

    listening = true;

    console.log(
      "CUSTOMER RECORDER ARMED"
    );

    /*
     * Safety timeout.
     *
     * Silero VAD should normally
     * stop the recording long
     * before this.
     */

    recordingTimer =
      setTimeout(() => {
        if (
          mediaRecorder &&
          mediaRecorder.state ===
            "recording"
        ) {
          console.log(
            "MAX RECORDING TIME REACHED"
          );

          stopRecording();
        }
      }, MAX_RECORDING_MS);

  } catch (error) {
    console.error(
      "BEGIN RECORDING ERROR:",
      error
    );

    listening = false;
    mediaRecorder = null;

    onError?.(error);
  }
}

export function stopRecording() {
  clearTimeout(
    recordingTimer
  );

  recordingTimer = null;

  if (
    mediaRecorder &&
    mediaRecorder.state ===
      "recording"
  ) {
    console.log(
      "CUSTOMER RECORDING STOPPED"
    );

    try {
      mediaRecorder.stop();
    } catch (error) {
      console.error(
        "RECORDING STOP ERROR:",
        error
      );

      listening = false;
      mediaRecorder = null;
    }
  }
}

export function cleanupRecorder() {
  clearTimeout(
    recordingTimer
  );

  recordingTimer = null;

  if (
    mediaRecorder &&
    mediaRecorder.state ===
      "recording"
  ) {
    try {
      mediaRecorder.stop();
    } catch (error) {
      console.error(
        "RECORDER CLEANUP ERROR:",
        error
      );
    }
  }

  mediaRecorder = null;

  listening = false;
}