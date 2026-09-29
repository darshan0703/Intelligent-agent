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
   * Save callback if provided.
   *
   * This is important because restartListening()
   * may call startListening() without a callback.
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
   * Prevent two startListening() calls
   * from running simultaneously.
   */

  if (startingListening) {
    console.log(
      "START LISTENING: ALREADY STARTING"
    );

    return;
  }


  /*
   * Do NOT block listening just because TTS
   * is currently playing.
   *
   * This is required for barge-in.
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
       
       Initialize only once.
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
           * Stop VAD while processing audio.
           */

          pauseSileroVAD();


          /*
           * No confirmed speech.
           */

          if (!speechTriggered) {

            console.log(
              "NO HUMAN SPEECH DETECTED"
            );

            restartListening();

            return;
          }


          /*
           * Empty recording.
           */

          if (!recording) {

            console.log(
              "EMPTY RECORDING"
            );

            restartListening();

            return;
          }


          /*
           * Send audio to Whisper.
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


  if (!isRecording()) {
    return;
  }


  /*
   * If speech was never detected,
   * don't process the recording.
   */

  if (!speechTriggered) {
    return;
  }


  console.log(
    "SILERO: CUSTOMER TURN ENDED"
  );


  /*
   * Stop VAD first.
   */

  pauseSileroVAD();


  /*
   * Stop MediaRecorder.
   *
   * onComplete() will then process
   * the recorded audio.
   */

  stopRecording();
}


/* =========================================================
   PROCESS RECORDING
========================================================= */

async function processRecording(
  recording
) {

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

      transcriptCallback(
        transcript
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


  pauseSileroVAD();


  /*
   * Clean recorder state before starting
   * another recording cycle.
   */

  cleanupRecorder();


  console.log(
    "RESTARTING CUSTOMER LISTENER..."
  );


  /*
   * Give MediaRecorder a very small amount
   * of time to completely release.
   *
   * This is 100 ms instead of the old 400 ms.
   */

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


  pauseSileroVAD();


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
   * Stop customer recording while
   * the kiosk prepares to speak.
   */

  pauseSileroVAD();

  stopRecording();

  cleanupRecorder();


  speechTriggered = false;


  /*
   * Start TTS.
   */

  speakText(
    text,
    {

      onStart: () => {

        console.log(
          "TTS STARTED"
        );


        /*
         * Enable interruption detection
         * while the kiosk is speaking.
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
   * Clean audio analyser.
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
   BARGE-IN
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
       * Stop TTS immediately.
       */

      stopSpeaking();


      /*
       * Tell VoiceConversationProvider
       * to listen to the customer.
       */

      if (handler) {
        handler();
      }

    }
  );
}