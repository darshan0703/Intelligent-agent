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
  handleSileroInterruption,
} from "./interruptionService";


/* =========================================================
   STATE
========================================================= */

let stopping = false;

let transcriptCallback = null;

let speechTriggered = false;

let sileroInitialized = false;

let startingListening = false;

let restarting = false;


/* =========================================================
   START LISTENING
========================================================= */

export async function startListening(callback) {

  /*
   * IMPORTANT:
   *
   * A previous stopVoiceSession()
   * sets stopping = true.
   *
   * When starting a NEW voice session,
   * we must reset it.
   */

  stopping = false;


  /*
   * Save transcript callback.
   */

  if (callback) {
    transcriptCallback = callback;
  }


  /*
   * Make sure callback exists.
   */

  if (!transcriptCallback) {

    console.error(
      "START LISTENING: NO TRANSCRIPT CALLBACK"
    );

    return;
  }


  /*
   * Prevent duplicate recording.
   */

  if (isRecording()) {

    console.log(
      "START LISTENING: ALREADY RECORDING"
    );

    return;
  }


  /*
   * Prevent duplicate startup.
   */

  if (startingListening) {

    console.log(
      "START LISTENING: ALREADY STARTING"
    );

    return;
  }


  /*
   * Do NOT block because of TTS.
   *
   * Silero must be able to listen
   * during TTS for barge-in.
   */

  if (stopping) {

    console.log(
      "START LISTENING: SESSION STOPPING"
    );

    return;
  }


  startingListening = true;

  restarting = false;

  speechTriggered = false;


  try {

    console.log(
      "================================="
    );

    console.log(
      "PREPARING VOICE LISTENER..."
    );

    console.log(
      "================================="
    );


    /* -----------------------------------------
       MICROPHONE
    ----------------------------------------- */

    await getMicrophone();

    console.log(
      "MICROPHONE READY"
    );


    /* -----------------------------------------
       AUDIO ANALYSER
    ----------------------------------------- */

    await setupAnalyser();

    console.log(
      "ANALYSER READY"
    );


    /* -----------------------------------------
       SILERO VAD
    ----------------------------------------- */

    if (!sileroInitialized) {

      console.log(
        "INITIALIZING SILERO VAD..."
      );


      await initializeSileroVAD({

        onSpeechStart:
          handleSileroSpeechStart,

        onSpeechEnd:
          handleSileroSpeechEnd,

      });


      sileroInitialized = true;


      console.log(
        "SILERO VAD READY"
      );

    }


    /*
     * Check if session was stopped
     * while initialization was running.
     */

    if (stopping) {
      return;
    }


    /* -----------------------------------------
       START MEDIA RECORDER
    ----------------------------------------- */

    console.log(
      "STARTING RECORDING..."
    );


    await startRecording({

      onComplete:
        async (recording) => {

          console.log(
            "RECORDING COMPLETE"
          );


          if (stopping) {
            return;
          }


          /*
           * Stop VAD before processing.
           */

          pauseSileroVAD();


          /*
           * If Silero never detected speech,
           * restart listening.
           */

          if (!speechTriggered) {

            console.log(
              "NO HUMAN SPEECH DETECTED"
            );


            restartListening();

            return;
          }


          /*
           * Check recording.
           */

          if (!recording) {

            console.log(
              "EMPTY RECORDING"
            );


            restartListening();

            return;
          }


          /*
           * Process recording with Whisper.
           */

          await processRecording(
            recording
          );

        },


      onError:
        (error) => {

          console.error(
            "RECORDING ERROR:",
            error
          );


          pauseSileroVAD();


          if (!stopping) {
            restartListening();
          }

        },

    });


    console.log(
      "RECORDING STARTED"
    );


    if (stopping) {
      return;
    }


    /* -----------------------------------------
       START SILERO
    ----------------------------------------- */

    await startSileroVAD();


    console.log(
      "SILERO LISTENING FOR CUSTOMER"
    );


    console.log(
      "VOICE LISTENER READY"
    );


  } catch (error) {

    console.error(
      "VOICE LISTENER ERROR:",
      error
    );


    pauseSileroVAD();


    if (!stopping) {
      restartListening();
    }


  } finally {

    startingListening = false;

  }

}


/* =========================================================
   SILERO SPEECH START
========================================================= */

function handleSileroSpeechStart() {

  if (stopping) {
    return;
  }


  /*
   * BARGE-IN
   *
   * Silero continues monitoring the
   * microphone while Kokoro is speaking.
   */

  if (isSpeaking()) {

    console.log(
      "================================="
    );

    console.log(
      "SILERO: CUSTOMER INTERRUPTED CASHIER"
    );

    console.log(
      "================================="
    );


    handleSileroInterruption();

    return;
  }


  /*
   * Normal customer listening.
   */

  if (!isRecording()) {
    return;
  }


  /*
   * Ignore duplicate speech events.
   */

  if (speechTriggered) {
    return;
  }


  speechTriggered = true;


  console.log(
    "================================="
  );

  console.log(
    "SILERO: CUSTOMER TURN STARTED"
  );

  console.log(
    "================================="
  );

}


/* =========================================================
   SILERO SPEECH END
========================================================= */

function handleSileroSpeechEnd() {

  if (stopping) {
    return;
  }


  /*
   * During TTS there is no MediaRecorder.
   *
   * Therefore speech-end during TTS
   * should not stop anything.
   */

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
   * Stop VAD before processing.
   */

  pauseSileroVAD();


  /*
   * Stop MediaRecorder.
   */

  stopRecording();

}


/* =========================================================
   PROCESS RECORDING
========================================================= */

async function processRecording(
  recording
) {

  const processingStart =
    performance.now();


  if (stopping) {
    return;
  }


  try {

    console.log(
      "================================="
    );

    console.log(
      "SENDING AUDIO TO WHISPER..."
    );

    console.log(
      "================================="
    );


    /* -----------------------------------------
       WHISPER TIMER
    ----------------------------------------- */

    const whisperStart =
      performance.now();


    const result =
      await sendAudioToWhisper(
        recording.blob,
        recording.mimeType
      );


    const whisperTime =
      performance.now() -
      whisperStart;


    console.log(
      `WHISPER TIME: ${(whisperTime / 1000).toFixed(2)} seconds`
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


    /*
     * Validate transcript.
     */

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
      "================================="
    );

    console.log(
      "VALID CUSTOMER TRANSCRIPT:",
      transcript
    );

    console.log(
      "================================="
    );


    /*
     * Send transcript to
     * VoiceConversationProvider.
     */

    if (transcriptCallback) {

      const callbackStart =
        performance.now();


      transcriptCallback(
        transcript
      );


      const callbackTime =
        performance.now() -
        callbackStart;


      console.log(
        `TRANSCRIPT CALLBACK: ${(callbackTime / 1000).toFixed(2)} seconds`
      );


      const totalProcessingTime =
        performance.now() -
        processingStart;


      console.log(
        `TOTAL VOICE PROCESSING: ${(totalProcessingTime / 1000).toFixed(2)} seconds`
      );


    } else {

      console.error(
        "NO TRANSCRIPT CALLBACK AVAILABLE"
      );


      restartListening();

    }


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


/* =========================================================
   RESTART LISTENING
========================================================= */

function restartListening() {

  if (stopping) {
    return;
  }


  if (restarting) {
    return;
  }


  if (startingListening) {
    return;
  }


  if (isRecording()) {
    return;
  }


  restarting = true;

  speechTriggered = false;


  /*
   * Pause VAD.
   */

  pauseSileroVAD();


  /*
   * Clean recorder state.
   */

  cleanupRecorder();


  console.log(
    "RESTARTING CUSTOMER LISTENER..."
  );


  setTimeout(
    async () => {

      restarting = false;


      if (stopping) {
        return;
      }


      if (isRecording()) {
        return;
      }


      console.log(
        "STARTING NEW LISTENING CYCLE"
      );


      await startListening();

    },
    100
  );

}


/* =========================================================
   STOP CURRENT LISTENING CYCLE
========================================================= */

export function stopListening() {

  console.log(
    "STOPPING CURRENT LISTENING CYCLE"
  );


  speechTriggered = false;


  /*
   * Stop VAD for the current
   * recording cycle only.
   */

  pauseSileroVAD();


  /*
   * Stop recorder.
   */

  stopRecording();


  cleanupRecorder();

}


/* =========================================================
   SPEAK
========================================================= */

export function speak(
  text,
  onComplete
) {

  if (!text) {

    console.warn(
      "SPEAK CALLED WITH EMPTY TEXT"
    );


    onComplete?.();

    return;
  }


  console.log(
    "KIOSK SPEAKING:",
    text
  );


  /*
   * Stop customer recording.
   *
   * IMPORTANT:
   * DO NOT pause Silero here.
   *
   * Silero must continue monitoring
   * the microphone for barge-in.
   */

  stopRecording();

  cleanupRecorder();


  speechTriggered = false;


  /*
   * Make sure Silero is running
   * during TTS.
   */

  if (sileroInitialized) {

    startSileroVAD();

  }


  /*
   * Start Kokoro TTS.
   */

  speakText(
    text,
    {

      onStart: () => {

        console.log(
          "TTS STARTED"
        );


        /*
         * Silero is monitoring the
         * microphone while Kokoro speaks.
         */

        if (!stopping) {

          startInterruptionDetection();


          console.log(
            "INTERRUPTION DETECTION ACTIVE"
          );

        }

      },


      onComplete: () => {

        console.log(
          "TTS COMPLETED"
        );


        stopInterruptionDetection();


        if (onComplete) {
          onComplete();
        }

      },

    }
  );

}


/* =========================================================
   STOP ENTIRE VOICE SESSION
========================================================= */

export function stopVoiceSession() {

  console.log(
    "================================="
  );

  console.log(
    "STOPPING ENTIRE VOICE SESSION"
  );

  console.log(
    "================================="
  );


  /*
   * Mark the session as stopping.
   */

  stopping = true;

  restarting = false;

  startingListening = false;

  speechTriggered = false;


  /*
   * Stop VAD.
   */

  pauseSileroVAD();


  /*
   * Stop interruption detection.
   */

  stopInterruptionDetection();


  /*
   * Stop recorder.
   */

  stopRecording();

  cleanupRecorder();


  /*
   * Stop TTS.
   */

  stopSpeaking();


  /*
   * Clean analyser.
   */

  cleanupAnalyser();


  /*
   * Release microphone.
   */

  releaseMicrophone();


  /*
   * Destroy Silero.

   */

  destroySileroVAD();

  sileroInitialized = false;


  /*
   * Remove callback.
   */

  transcriptCallback = null;


  console.log(
    "VOICE SESSION STOPPED"
  );

}


/* =========================================================
   BARGE-IN HANDLER
========================================================= */

export function setInterruptionHandler(
  handler
) {

  setInterruptionHandlerInternal(
    () => {

      /*
       * Only interrupt if TTS
       * is actually speaking.
       */

      if (!isSpeaking()) {
        return;
      }


      console.log(
        "================================="
      );

      console.log(
        "INTERRUPTION DETECTED"
      );

      console.log(
        "CUSTOMER TOOK THE TURN"
      );

      console.log(
        "================================="
      );


      /*
       * Stop Kokoro immediately.
       */

      stopSpeaking();


      /*
       * Tell VoiceConversationProvider
       * to listen to customer.
       */

      if (handler) {
        handler();
      }

    }
  );

}