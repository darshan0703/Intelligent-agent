import {
  getMicrophone,
  releaseMicrophone,
} from "./microphoneService";

import {
  setupAnalyser,
  cleanupAnalyser,
} from "./audioAnalyser";

import {
  startRecording,
  stopRecording,
  isRecording,
  cleanupRecorder,
} from "./recorderService";

import {
  initializeSileroVAD,
  startSileroVAD,
  pauseSileroVAD,
  destroySileroVAD,
} from "./sileroVadService";

import {
  sendAudioToWhisper,
} from "./whisperService";

import {
  isValidTranscript,
} from "./transcriptFilter";

import {
  speakText,
  stopSpeaking,
  isSpeaking,
} from "./ttsService";

import {
  startInterruptionDetection,
  stopInterruptionDetection,
  setInterruptionHandler as
    setInterruptionHandlerInternal,
} from "./interruptionService";

let stopping = false;
let transcriptCallback = null;
let speechTriggered = false;
let sileroInitialized = false;

export async function startListening(callback) {
  if (isRecording()) {
    return;
  }

  if (isSpeaking()) {
    return;
  }

  if (callback) {
    transcriptCallback = callback;
  }

  if (!transcriptCallback) {
    console.error(
      "startListening requires a callback"
    );

    return;
  }

  stopping = false;
  speechTriggered = false;

  try {
    console.log(
      "PREPARING VOICE LISTENER..."
    );

    /*
     * Get the microphone first.
     *
     * This is also used by:
     * - MediaRecorder
     * - audio analyser
     * - existing microphone system
     */

    await getMicrophone();

    /*
     * Keep the analyser setup for now.
     *
     * Other services such as
     * interruption detection may
     * still depend on it.
     */

    await setupAnalyser();

    /*
     * Initialize Silero once.
     *
     * The AI model loads here.
     */

    if (!sileroInitialized) {
      await initializeSileroVAD({
        onSpeechStart:
          handleSileroSpeechStart,

        onSpeechEnd:
          handleSileroSpeechEnd,
      });

      sileroInitialized = true;
    }

    if (
      stopping ||
      isSpeaking()
    ) {
      return;
    }

    console.log(
      "VOICE LISTENER READY"
    );

    /*
     * Start recording BEFORE
     * speech detection.
     *
     * This prevents short words
     * from being cut off.
     */

    await startRecording({
      onComplete:
        async (recording) => {
          if (stopping) {
            return;
          }

          /*
           * Stop Silero while
           * processing this turn.
           */

          pauseSileroVAD();

          /*
           * If Silero never
           * confirmed human speech,
           * ignore the recording.
           */

          if (!speechTriggered) {
            console.log(
              "NO HUMAN SPEECH DETECTED"
            );

            restartListening();

            return;
          }

          if (!recording) {
            console.log(
              "EMPTY RECORDING"
            );

            restartListening();

            return;
          }

          await processRecording(
            recording
          );
        },

      onError: () => {
        pauseSileroVAD();

        if (!stopping) {
          restartListening();
        }
      },
    });

    /*
     * Start AI-based voice
     * activity detection.
     */

    startSileroVAD();

    console.log(
      "SILERO LISTENING FOR CUSTOMER"
    );

  } catch (error) {
    console.error(
      "VOICE LISTENER ERROR:",
      error
    );

    pauseSileroVAD();

    if (!stopping) {
      setTimeout(
        restartListening,
        500
      );
    }
  }
}

function handleSileroSpeechStart() {
  if (
    stopping ||
    isSpeaking() ||
    !isRecording()
  ) {
    return;
  }

  /*
   * Ignore duplicate speech
   * start events.
   */

  if (speechTriggered) {
    return;
  }

  speechTriggered = true;

  console.log(
    "SILERO: CUSTOMER TURN STARTED"
  );
}

function handleSileroSpeechEnd() {
  if (
    stopping ||
    !isRecording()
  ) {
    return;
  }

  /*
   * Ignore speech-end events
   * if Silero never confirmed
   * speech in this turn.
   */

  if (!speechTriggered) {
    return;
  }

  console.log(
    "SILERO: CUSTOMER TURN ENDED"
  );

  /*
   * Stop AI detection first
   * so no duplicate events
   * are generated while
   * MediaRecorder finishes.
   */

  pauseSileroVAD();

  /*
   * Silero decides when the
   * customer has finished
   * speaking.
   */

  stopRecording();
}

async function processRecording(
  recording
) {
  if (stopping) {
    return;
  }

  try {
    console.log(
      "SENDING AUDIO TO WHISPER..."
    );

    const result =
      await sendAudioToWhisper(
        recording.blob,
        recording.mimeType
      );

    if (stopping) {
      return;
    }

    const transcript =
      result?.transcript;

    console.log(
      "WHISPER TRANSCRIPT:",
      transcript
    );

    if (
      !isValidTranscript(
        transcript
      )
    ) {
      console.log(
        "IGNORING INVALID TRANSCRIPT"
      );

      restartListening();

      return;
    }

    console.log(
      "VALID CUSTOMER TRANSCRIPT:",
      transcript
    );

    /*
     * Send transcript to
     * VoiceConversationProvider.
     */

    transcriptCallback?.(
      transcript
    );

  } catch (error) {
    console.error(
      "WHISPER ERROR:",
      error
    );

    if (!stopping) {
      restartListening();
    }
  }
}

function restartListening() {
  if (stopping) {
    return;
  }

  if (isSpeaking()) {
    return;
  }

  if (isRecording()) {
    return;
  }

  speechTriggered = false;

  pauseSileroVAD();

  console.log(
    "RESTARTING CUSTOMER LISTENER"
  );

  setTimeout(() => {
    if (
      !stopping &&
      !isSpeaking() &&
      !isRecording()
    ) {
      startListening();
    }
  }, 400);
}

export function stopListening() {
  /*
   * Stop only the current
   * listening cycle.
   *
   * The voice conversation
   * itself remains active.
   */

  speechTriggered = false;

  pauseSileroVAD();

  stopRecording();

  cleanupRecorder();
}

export function speak(
  text,
  onComplete
) {
  /*
   * Stop customer listening
   * before the kiosk speaks.
   */

  pauseSileroVAD();

  stopRecording();

  cleanupRecorder();

  speechTriggered = false;

  speakText(
    text,
    {
      onStart: () => {
        /*
         * Existing interruption
         * detection remains active.
         *
         * We will improve this
         * later using Silero too.
         */

        if (!stopping) {
          startInterruptionDetection();
        }
      },

      onComplete: () => {
        stopInterruptionDetection();

        if (onComplete) {
          onComplete();
        }
      },
    }
  );
}

export function stopVoiceSession() {
  console.log(
    "STOPPING ENTIRE VOICE SESSION"
  );

  stopping = true;

  speechTriggered = false;

  pauseSileroVAD();

  stopInterruptionDetection();

  stopRecording();

  cleanupRecorder();

  stopSpeaking();

  cleanupAnalyser();

  releaseMicrophone();

  /*
   * Destroy Silero only when
   * the entire voice session
   * ends.
   */

  destroySileroVAD();

  sileroInitialized = false;

  transcriptCallback = null;

  console.log(
    "VOICE SESSION STOPPED"
  );
}

export function setInterruptionHandler(
  handler
) {
  setInterruptionHandlerInternal(
    () => {
      if (!isSpeaking()) {
        return;
      }

      console.log(
        "INTERRUPTION DETECTED"
      );

      stopSpeaking();

      handler?.();
    }
  );
}