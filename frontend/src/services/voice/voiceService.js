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
  setInterruptionHandler as setInterruptionHandlerInternal,
} from "./interruptionService";


let stopping = false;

let transcriptCallback = null;

let speechTriggered = false;

let sileroInitialized = false;

let voiceStateHandler = null;


/*
 * =====================================================
 * VOICE STATE HANDLER
 * =====================================================
 *
 * Provider uses this to update the UI.
 */
export function setVoiceStateHandler(handler) {
  voiceStateHandler = handler;
}

function updateVoiceState(state) {
  console.log(
    "VOICE SERVICE STATE:",
    state
  );

  voiceStateHandler?.(state);
}


/*
 * =====================================================
 * START LISTENING
 * =====================================================
 */
export async function startListening(callback) {

  if (callback) {
    transcriptCallback = callback;
  }

  if (!transcriptCallback) {
    console.error(
      "startListening requires a callback"
    );

    return;
  }

  /*
   * Don't create another recorder.
   */
  if (isRecording()) {
    return;
  }

  stopping = false;

  speechTriggered = false;

  try {

    console.log(
      "PREPARING VOICE LISTENER..."
    );

    await getMicrophone();

    await setupAnalyser();

    /*
     * Initialize Silero once.
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

    if (stopping) {
      return;
    }

    console.log(
      "VOICE LISTENER READY"
    );

    /*
     * Recorder starts in the background.
     *
     * UI does NOT say Listening yet.
     */
    await startRecording({

      onComplete:
        async (recording) => {

          if (stopping) {
            return;
          }

          pauseSileroVAD();

          if (!speechTriggered) {

            console.log(
              "NO HUMAN SPEECH DETECTED"
            );

            updateVoiceState("idle");

            restartListening();

            return;
          }

          if (!recording) {

            console.log(
              "EMPTY RECORDING"
            );

            updateVoiceState("idle");

            restartListening();

            return;
          }

          /*
           * Process customer audio.
           */
          await processRecording(
            recording
          );
        },

      onError: () => {

        pauseSileroVAD();

        updateVoiceState("idle");

        if (!stopping) {
          restartListening();
        }
      },

    });

    /*
     * Start Silero.
     */
    startSileroVAD();

    console.log(
      "SILERO LISTENING IN BACKGROUND"
    );

    /*
     * IMPORTANT:
     *
     * Do NOT set UI to listening here.
     *
     * Listening UI appears only when
     * Silero actually detects customer speech.
     */

  } catch (error) {

    console.error(
      "VOICE LISTENER ERROR:",
      error
    );

    pauseSileroVAD();

    updateVoiceState("idle");

    if (!stopping) {

      setTimeout(() => {

        if (!stopping) {
          startListening();
        }

      }, 500);
    }
  }
}


/*
 * =====================================================
 * CUSTOMER STARTS SPEAKING
 * =====================================================
 */
function handleSileroSpeechStart() {

  if (stopping) {
    return;
  }

  if (!isRecording()) {
    return;
  }

  if (speechTriggered) {
    return;
  }

  speechTriggered = true;

  console.log(
    "SILERO: CUSTOMER SPEECH DETECTED"
  );

  /*
   * THIS CONTROLS THE WAVES.
   */
  updateVoiceState("listening");

  /*
   * If Kokoro is currently speaking,
   * this is a BARGE-IN.
   */
  if (isSpeaking()) {

    console.log(
      "BARGE-IN DETECTED"
    );

    console.log(
      "STOPPING KOKORO NOW"
    );

    stopInterruptionDetection();

    stopSpeaking();

    console.log(
      "KOKORO STOPPED"
    );

    console.log(
      "CUSTOMER HAS THE TURN"
    );
  }
}


/*
 * =====================================================
 * CUSTOMER STOPS SPEAKING
 * =====================================================
 */
function handleSileroSpeechEnd() {

  if (stopping) {
    return;
  }

  if (!isRecording()) {
    return;
  }

  if (!speechTriggered) {
    return;
  }

  console.log(
    "SILERO: CUSTOMER TURN ENDED"
  );

  /*
   * Customer has stopped talking.
   */
  pauseSileroVAD();

  /*
   * Change UI from waves to processing.
   */
  updateVoiceState("processing");

  /*
   * Stop recorder.
   */
  stopRecording();
}


/*
 * =====================================================
 * WHISPER
 * =====================================================
 */
async function processRecording(recording) {

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

      updateVoiceState("idle");

      restartListening();

      return;
    }

    console.log(
      "VALID CUSTOMER TRANSCRIPT:",
      transcript
    );

    /*
     * Provider now sends it to Groq.
     */
    transcriptCallback?.(
      transcript
    );

  } catch (error) {

    console.error(
      "WHISPER ERROR:",
      error
    );

    updateVoiceState("idle");

    if (!stopping) {
      restartListening();
    }
  }
}


/*
 * =====================================================
 * RESTART LISTENING
 * =====================================================
 */
function restartListening() {

  if (stopping) {
    return;
  }

  if (isRecording()) {
    return;
  }

  speechTriggered = false;

  pauseSileroVAD();

  setTimeout(() => {

    if (
      !stopping &&
      !isRecording()
    ) {

      startListening();

    }

  }, 400);
}


/*
 * =====================================================
 * STOP LISTENING
 * =====================================================
 */
export function stopListening() {

  speechTriggered = false;

  pauseSileroVAD();

  stopRecording();

  cleanupRecorder();

  updateVoiceState("idle");
}


/*
 * =====================================================
 * KOKORO SPEAK
 * =====================================================
 */
export function speak(
  text,
  onComplete
) {

  if (!text) {

    onComplete?.();

    return;
  }

  console.log(
    "STARTING KOKORO SPEECH"
  );

  /*
   * UI = Speaking.
   */
  updateVoiceState("speaking");

  speakText(
    text,
    {

      /*
       * Kokoro starts.
       */
      onStart: () => {

        if (stopping) {
          return;
        }

        console.log(
          "KOKORO SPEAKING"
        );

        updateVoiceState(
          "speaking"
        );

        /*
         * Keep interruption detector running.
         */
        startInterruptionDetection();
      },

      /*
       * Kokoro finishes.
       */
      onComplete: () => {

        stopInterruptionDetection();

        console.log(
          "KOKORO SPEECH COMPLETE"
        );

        /*
         * Don't automatically say Listening.
         *
         * Microphone is ready in background.
         *
         * When customer actually speaks,
         * Silero will change state to listening.
         */
        updateVoiceState("idle");

        onComplete?.();
      },

    }
  );
}


/*
 * =====================================================
 * INTERRUPTION HANDLER
 * =====================================================
 */
export function setInterruptionHandler(
  handler
) {

  setInterruptionHandlerInternal(() => {

    if (!isSpeaking()) {
      return;
    }

    console.log(
      "CUSTOMER INTERRUPTED KOKORO"
    );

    stopInterruptionDetection();

    stopSpeaking();

    updateVoiceState(
      "listening"
    );

    /*
     * DO NOT stop recorder.
     *
     * Customer's question is still being recorded.
     */
    handler?.();

  });
}


/*
 * =====================================================
 * STOP EVERYTHING
 * =====================================================
 */
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

  destroySileroVAD();

  sileroInitialized = false;

  transcriptCallback = null;

  voiceStateHandler = null;

  console.log(
    "VOICE SESSION STOPPED"
  );
}