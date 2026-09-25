let currentAudio = null;
let currentAudioUrl = null;
let speaking = false;

export function isSpeaking() {
  return speaking;
}

function cleanupAudio() {
  if (currentAudio) {
    currentAudio.onended = null;
    currentAudio.onerror = null;

    try {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    } catch (error) {
      console.error(
        "AUDIO CLEANUP ERROR:",
        error
      );
    }

    currentAudio = null;
  }

  if (currentAudioUrl) {
    URL.revokeObjectURL(
      currentAudioUrl
    );

    currentAudioUrl = null;
  }

  speaking = false;
}

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

export async function speakText(
  text,
  {
    onComplete,
    onStart,
  } = {}
) {
  if (!text || localStorage.getItem("kiosk_sound_muted") === "true") {
    onComplete?.();
    return;
  }

  // Stop and clean up any previous TTS.
  cleanupAudio();

  speaking = true;

  try {
    console.log(
      "REQUESTING TTS:",
      text
    );

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    const response = await fetch(
      `${API_BASE_URL}/tts`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          text,
        }),
        signal: controller.signal,
      }
    );

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(
        `TTS request failed: ${response.status}`
      );
    }

    const audioBlob =
      await response.blob();

    const audioUrl =
      URL.createObjectURL(
        audioBlob
      );

    const audio =
      new Audio(audioUrl);

    currentAudio = audio;
    currentAudioUrl = audioUrl;

    let completed = false;

    const finish = () => {
      if (completed) {
        return;
      }

      completed = true;

      speaking = false;

      if (
        currentAudio === audio
      ) {
        currentAudio = null;
      }

      if (
        currentAudioUrl === audioUrl
      ) {
        URL.revokeObjectURL(
          audioUrl
        );

        currentAudioUrl = null;
      }

      console.log(
        "TTS FINISHED"
      );

      onComplete?.();
    };

    audio.onended = () => {
      console.log(
        "TTS AUDIO ENDED"
      );

      finish();
    };

    audio.onerror = (error) => {
      console.error(
        "TTS PLAYBACK ERROR:",
        error
      );

      finish();
    };

    await audio.play();

    console.log(
      "TTS PLAYING"
    );

    onStart?.();

  } catch (error) {
    speaking = false;

    console.error(
      "TTS ERROR:",
      error
    );

    onComplete?.();
  }
}

export function stopSpeaking() {
  if (!currentAudio) {
    speaking = false;
    return;
  }

  console.log(
    "TTS STOPPED"
  );

  cleanupAudio();
}