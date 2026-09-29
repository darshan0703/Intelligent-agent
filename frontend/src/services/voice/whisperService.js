const STT_URL = "/stt";

export async function sendAudioToWhisper(
  blob,
  mimeType
) {
  console.log("=================================");
  console.log("SENDING AUDIO TO WHISPER");
  console.log("=================================");

  console.log("AUDIO BLOB:", blob);
  console.log("AUDIO SIZE:", blob?.size);
  console.log("AUDIO MIME TYPE:", mimeType);

  if (!blob || blob.size === 0) {
    console.error("EMPTY AUDIO BLOB");

    return {
      success: false,
      transcript: "",
      data: null,
    };
  }

  const formData = new FormData();

  let extension = "webm";

  if (mimeType?.includes("mp4")) {
    extension = "m4a";
  } else if (mimeType?.includes("ogg")) {
    extension = "ogg";
  }

  formData.append(
    "file",
    blob,
    `voice.${extension}`
  );

  console.log(
    "SENDING FILE:",
    `voice.${extension}`
  );

  try {
    const response = await fetch(
      STT_URL,
      {
        method: "POST",
        body: formData,
      }
    );

    console.log(
      "WHISPER HTTP STATUS:",
      response.status
    );

    if (!response.ok) {
      throw new Error(
        `STT request failed: ${response.status}`
      );
    }

    const data =
      await response.json();

    console.log(
      "================================="
    );

    console.log(
      "WHISPER RAW RESPONSE:",
      data
    );

    console.log(
      "WHISPER TEXT:",
      data?.text
    );

    console.log(
      "================================="
    );

    const transcript =
      data?.text?.trim() || "";

    if (!transcript) {
      console.warn(
        "WHISPER RETURNED EMPTY TRANSCRIPT"
      );
    } else {
      console.log(
        "FINAL TRANSCRIPT:",
        transcript
      );
    }

    return {
      success:
        data?.success !== false,

      transcript,

      data,
    };

  } catch (error) {

    console.error(
      "WHISPER REQUEST ERROR:",
      error
    );

    return {
      success: false,
      transcript: "",
      data: null,
      error: error.message,
    };
  }
}