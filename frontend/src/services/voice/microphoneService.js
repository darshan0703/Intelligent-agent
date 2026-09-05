let mediaStream = null;

export async function getMicrophone() {
  if (mediaStream) {
    const hasLiveTrack = mediaStream
      .getAudioTracks()
      .some((track) => track.readyState === "live");

    if (hasLiveTrack) return mediaStream;

    mediaStream = null;
  }

  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    },
  });

  return mediaStream;
}

export function releaseMicrophone() {
  if (!mediaStream) return;

  mediaStream.getTracks().forEach((track) => track.stop());

  mediaStream = null;
}