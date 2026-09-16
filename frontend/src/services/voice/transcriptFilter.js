export function isNonSpeechTranscript(
  transcript
) {
  const normalized =
    transcript
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");

  if (!normalized) return true;

  if (
    /^(\(|\[).*(\)|\])$/.test(
      normalized
    )
  ) {
    return true;
  }

  const soundEventPattern =
    /^(?:a |an )?(?:bell|beep|beeping|alarm|siren|engine|car|horn|music|background noise|noise|indistinct chatter|chatter|laughter|laughing|coughing|cough|sneezing|breathing|applause|clapping|clicking|typing|door|phone|ringing|ringtone)(?: .*)?$/;

  return soundEventPattern.test(
    normalized
  );
}

export function isValidTranscript(
  transcript
) {
  if (!transcript) return false;

  const normalized =
    transcript.trim();

  if (!normalized) return false;

  if (
    normalized ===
    "[BLANK_AUDIO]"
  ) {
    return false;
  }

  if (
    isNonSpeechTranscript(normalized)
  ) {
    return false;
  }

  return true;
}