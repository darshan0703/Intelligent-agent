let recognition = null;

export function startListening(onResult) {
  const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    console.error(
      "Speech Recognition is not supported in this browser."
    );
    return;
  }

  recognition = new SpeechRecognition();

  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = "en-IN";

  recognition.onstart = () => {
    console.log("🎤 MICROPHONE LISTENING...");
  };

  recognition.onresult = (event) => {
    const lastResult =
      event.results[event.results.length - 1];

    if (lastResult.isFinal) {
      const transcript =
        lastResult[0].transcript.trim();

      console.log(
        "CUSTOMER SAID:",
        transcript
      );

      onResult(transcript);
    }
  };

  recognition.onerror = (event) => {
    console.error(
      "SPEECH RECOGNITION ERROR:",
      event.error
    );
  };

  recognition.onend = () => {
    console.log("MICROPHONE STOPPED");
  };

  recognition.start();
}

export function stopListening() {
  if (recognition) {
    recognition.stop();
    recognition = null;
  }
}

/*
==========================================
TEXT TO SPEECH
==========================================
*/

export async function speak(text, onComplete) {
  if (!text) {
    onComplete?.();
    return;
  }

  try {
    console.log(
      "🔊 CASHIER SPEAKING:",
      text
    );

    const response = await fetch(
      "http://127.0.0.1:8000/tts",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      }
    );

    if (!response.ok) {
      throw new Error(
        `TTS request failed: ${response.status}`
      );
    }

    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);

    audio.onended = () => {
      URL.revokeObjectURL(audioUrl);

      console.log(
        "🔊 CASHIER FINISHED SPEAKING"
      );

      onComplete?.();
    };

    audio.onerror = () => {
      URL.revokeObjectURL(audioUrl);

      console.error(
        "TEXT TO SPEECH PLAYBACK ERROR"
      );

      onComplete?.();
    };

    await audio.play();

  } catch (error) {
    console.error(
      "TEXT TO SPEECH ERROR:",
      error
    );

    onComplete?.();
  }
}