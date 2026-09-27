const STT_URL =
  "/stt";

export async function sendAudioToWhisper(
  blob,
  mimeType
) {
  const formData = new FormData();

  let extension = "webm";

  if (mimeType.includes("mp4")) {
    extension = "m4a";
  } else if (
    mimeType.includes("ogg")
  ) {
    extension = "ogg";
  }

  formData.append(
    "file",
    blob,
    `voice.${extension}`
  );

  const response = await fetch(
    STT_URL,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error(
      `STT request failed: ${response.status}`
    );
  }

  const data =
    await response.json();

  return {
    success:
      data?.success !== false,
    transcript:
      data?.text?.trim() || "",
    data,
  };
}