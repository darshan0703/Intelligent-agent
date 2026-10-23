
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
let currentStatusCallback = null;

// ======================================================
// VOICE STATUS CALLBACK
// ======================================================

export function setVoiceStatusCallback(callback) {
  currentStatusCallback =
    typeof callback === "function" ? callback : null;
}

function updateVoiceStatus(status) {
  currentStatusCallback?.(status);
}

// ======================================================
// PREPARE VOICE INPUT
// ======================================================

export async function prepareVoiceInput() {
  try {
    console.log("PREPARING VOICE INPUT FOR GREETING...");

    await getMicrophone();
    await setupAnalyser();

    console.log("VOICE INPUT READY FOR GREETING");
  } catch (error) {
    console.error("VOICE INPUT PREPARATION ERROR:", error);
    throw error;
  }
}

// ======================================================
// START LISTENING
// ======================================================

export async function startListening(callback) {
  if (isRecording() || isSpeaking() || stopping) {
    return;
  }

  if (callback) {
    transcriptCallback = callback;
  }

  if (!transcriptCallback) {
    console.error("startListening requires a callback");
    return;
  }

  speechTriggered = false;

  try {
    console.log("PREPARING VOICE LISTENER...");

    await getMicrophone();
    await setupAnalyser();

    if (!sileroInitialized) {
      await initializeSileroVAD({
        onSpeechStart: handleSileroSpeechStart,
        onSpeechEnd: handleSileroSpeechEnd,
      });

      sileroInitialized = true;
    }

    if (stopping || isSpeaking()) {
      return;
    }

    await startRecording({
      onComplete: async (recording) => {
        if (stopping) {
          return;
        }

        pauseSileroVAD();

        if (!speechTriggered) {
          console.log("NO HUMAN SPEECH DETECTED");
          restartListening();
          return;
        }

        if (!recording) {
          console.log("EMPTY RECORDING");
          restartListening();
          return;
        }

        await processRecording(recording);
      },

      onError: () => {
        pauseSileroVAD();

        if (!stopping) {
          restartListening();
        }
      },
    });

    if (stopping || isSpeaking()) {
      stopRecording();
      return;
    }

    startSileroVAD();
    updateVoiceStatus("listening");

    console.log("SILERO LISTENING FOR CUSTOMER");
  } catch (error) {
    console.error("VOICE LISTENER ERROR:", error);

    pauseSileroVAD();

    if (!stopping) {
      setTimeout(restartListening, 500);
    }
  }
}

// ======================================================
// SILERO SPEECH START
// ======================================================

function handleSileroSpeechStart() {
  if (stopping || isSpeaking() || !isRecording()) {
    return;
  }

  if (speechTriggered) {
    return;
  }

  speechTriggered = true;

  console.log("SILERO: CUSTOMER TURN STARTED");
}

// ======================================================
// SILERO SPEECH END
// ======================================================

function handleSileroSpeechEnd() {
  if (stopping || !isRecording() || !speechTriggered) {
    return;
  }

  console.log("SILERO: CUSTOMER TURN ENDED");

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

  try {
    // Show Processing while audio is transcribed.
    updateVoiceStatus("processing");

    console.log("SENDING AUDIO TO WHISPER...");

    const result = await sendAudioToWhisper(
      recording.blob,
      recording.mimeType
    );

    if (stopping) {
      return;
    }

    const transcript = result?.transcript;

    console.log("WHISPER TRANSCRIPT:", transcript);

    if (!isValidTranscript(transcript)) {
      console.log("IGNORING INVALID TRANSCRIPT");
      restartListening();
      return;
    }

    console.log("VALID CUSTOMER TRANSCRIPT:", transcript);

    // The provider continues processing the customer's request.
    updateVoiceStatus("processing");
    transcriptCallback?.(transcript);
  } catch (error) {
    console.error("WHISPER ERROR:", error);

    if (!stopping) {
      restartListening();
    }
  }
}

// ======================================================
// RESTART LISTENING
// ======================================================

function restartListening() {
  if (stopping || isSpeaking() || isRecording()) {
    return;
  }

  speechTriggered = false;
  pauseSileroVAD();

  console.log("RESTARTING CUSTOMER LISTENER");

  setTimeout(() => {
    if (!stopping && !isSpeaking() && !isRecording()) {
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
// SPEAK WITH KOKORO
// ======================================================

export function speak(text, onComplete, onStatusChange) {
  pauseSileroVAD();
  stopRecording();
  cleanupRecorder();

  speechTriggered = false;

  if (onStatusChange) {
    setVoiceStatusCallback(onStatusChange);
  }

  // Show Processing until Kokoro starts speaking.
  updateVoiceStatus("processing");

  speakText(text, {
    onStart: () => {
      if (stopping) {
        return;
      }

      updateVoiceStatus("speaking");

      console.log("STARTING INTERRUPTION DETECTION");
      startInterruptionDetection();
    },

    onComplete: () => {
      stopInterruptionDetection();

      if (!stopping) {
        updateVoiceStatus("ready");
      }

      onComplete?.();
    },
  });
}

// ======================================================
// STOP ENTIRE VOICE SESSION
// ======================================================

export function stopVoiceSession() {
  console.log("STOPPING ENTIRE VOICE SESSION");

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

  updateVoiceStatus("ready");
  currentStatusCallback = null;

  console.log("VOICE SESSION STOPPED");
}

// ======================================================
// INTERRUPTION HANDLER
// ======================================================

export function setInterruptionHandler(handler) {
  setInterruptionHandlerInternal(() => {
    if (!isSpeaking()) {
      return;
    }

    console.log("INTERRUPTION DETECTED");

    stopSpeaking();
    stopInterruptionDetection();

    updateVoiceStatus("listening");

    handler?.();
  });
} 
