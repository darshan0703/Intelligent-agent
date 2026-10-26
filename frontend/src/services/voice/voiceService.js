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

import {
  createPerfTracker,
  setActiveVoiceTracker,
  getActiveVoiceTracker,
} from "../perf";


let stopping = false;
let transcriptCallback = null;
let speechTriggered = false;
let sileroInitialized = false;


// ======================================================
// PREPARE VOICE INPUT
// ======================================================
// Used only before the FIRST greeting.
//
// It prepares the microphone and analyser so that the
// existing interruption mechanism can hear the customer
// while the greeting is playing.
//
// It does NOT start recording.
// ======================================================

export async function prepareVoiceInput() {
  try {
    console.log(
      "PREPARING VOICE INPUT FOR GREETING..."
    );

    await getMicrophone();

    await setupAnalyser();

    console.log(
      "VOICE INPUT READY FOR GREETING"
    );

  } catch (error) {
    console.error(
      "VOICE INPUT PREPARATION ERROR:",
      error
    );

    throw error;
  }
}


// ======================================================
// START LISTENING
// ======================================================

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

    await getMicrophone();

    await setupAnalyser();


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


// ======================================================
// SILERO SPEECH START
// ======================================================

function handleSileroSpeechStart() {

  if (
    stopping ||
    isSpeaking() ||
    !isRecording()
  ) {
    return;
  }


  if (speechTriggered) {
    return;
  }


  speechTriggered = true;


  console.log(
    "SILERO: CUSTOMER TURN STARTED"
  );
}


// ======================================================
// SILERO SPEECH END
// ======================================================

function handleSileroSpeechEnd() {

  if (
    stopping ||
    !isRecording()
  ) {
    return;
  }


  if (!speechTriggered) {
    return;
  }


  console.log(
    "SILERO: CUSTOMER TURN ENDED"
  );

  const tracker = createPerfTracker("voice");
  setActiveVoiceTracker(tracker);
  tracker.log("speech_ended");

  pauseSileroVAD();

  stopRecording();
}


// ======================================================
// PROCESS RECORDING
// ======================================================

async function processRecording(recording) {

  if (stopping) {
    return;
  }

  const tracker = getActiveVoiceTracker() || createPerfTracker("voice");
  setActiveVoiceTracker(tracker);

  try {
    tracker.log("final_audio_capture", {
      bytes: recording?.blob?.size,
    });

    console.log(
      "SENDING AUDIO TO WHISPER..."
    );

    tracker.log("stt_request_started", { endpoint: "/stt" });
    const endStt = tracker.startStage("stt_request");

    const result =
      await sendAudioToWhisper(
        recording.blob,
        recording.mimeType,
        tracker.id
      );

    endStt();
    tracker.log("stt_request_completed");

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

    tracker.log("transcript_ready", {
      length: transcript?.length,
    });

    console.log(
      "VALID CUSTOMER TRANSCRIPT:",
      transcript
    );


    transcriptCallback?.(
      transcript,
      tracker
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


// ======================================================
// RESTART LISTENING
// ======================================================

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


// ======================================================
// STOP LISTENING
// ======================================================

export function stopListening() {

  speechTriggered = false;

  pauseSileroVAD();

  stopRecording();

  cleanupRecorder();
}


// ======================================================
// SPEAK
// ======================================================
// IMPORTANT:
//
// This is the SAME speak() function for:
// 1. Initial greeting
// 2. Menu responses
// 3. Category responses
// 4. Cart responses
// 5. Every later Kokoro response
//
// The existing interruption mechanism remains here.
// ======================================================

export function speak(
  text,
  onComplete,
  options = {}
) {

  pauseSileroVAD();

  stopRecording();

  cleanupRecorder();

  speechTriggered = false;

  const tracker = options?.tracker || getActiveVoiceTracker();

  speakText(
    text,
    {
      tracker,
      onStart: () => {

        if (!stopping) {

          console.log(
            "STARTING INTERRUPTION DETECTION"
          );

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


// ======================================================
// STOP ENTIRE VOICE SESSION
// ======================================================

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


  console.log(
    "VOICE SESSION STOPPED"
  );
}


// ======================================================
// INTERRUPTION HANDLER
// ======================================================

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


      // Stop Kokoro.

      stopSpeaking();


      // Continue existing conversation flow.

      handler?.();

    }
  );
}

export { stopSpeaking };