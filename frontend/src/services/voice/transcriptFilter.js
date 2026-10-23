export function isNonSpeechTranscript(transcript) {
  if (typeof transcript !== "string") return true;

  const normalized = transcript
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");

  if (!normalized) return true;

  // Reject common audio-event labels.
  if (
    /^\s*[\[(].*[\])]\s*$/.test(normalized) &&
    /^(?:\[|\().*(?:\]|\))$/.test(normalized)
  ) {
    return true;
  }

  const soundEventPattern =
    /^(?:(?:a|an) )?(?:bell|beep|beeping|alarm|siren|engine|car|horn|music|background noise|noise|indistinct chatter|chatter|laughter|laughing|coughing|cough|sneezing|breathing|applause|clapping|clicking|typing|door|phone|ringing|ringtone)(?: .*)?$/;

  return soundEventPattern.test(normalized);
}

export function isValidTranscript(transcript) {
  if (typeof transcript !== "string") return false;

  const normalized = transcript.trim();

  if (!normalized) return false;

  if (normalized.toLowerCase() === "[blank_audio]") {
    return false;
  }

  if (isNonSpeechTranscript(normalized)) {
    return false;
  }

  return true;
}