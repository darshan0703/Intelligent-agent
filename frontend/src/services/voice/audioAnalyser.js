import { getMicrophone } from "./microphoneService";

let audioContext = null;
let analyser = null;
let analyserSource = null;

export async function setupAnalyser() {
  if (audioContext && analyser && analyserSource) {
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }
    return;
  }

  const stream = await getMicrophone();

  audioContext = new AudioContext();

  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }

  analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.8;

  analyserSource = audioContext.createMediaStreamSource(stream);
  analyserSource.connect(analyser);
}

export function getVolume() {
  if (!analyser) return 0;

  const data = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(data);

  let mean = 0;

  for (let i = 0; i < data.length; i++) {
    mean += data[i];
  }

  mean /= data.length;

  let sum = 0;

  for (let i = 0; i < data.length; i++) {
    const normalized = (data[i] - mean) / 128;
    sum += normalized * normalized;
  }

  return Math.sqrt(sum / data.length);
}

export function hasAnalyser() {
  return Boolean(analyser);
}

export async function cleanupAnalyser() {
  if (analyserSource) {
    try {
      analyserSource.disconnect();
    } catch (error) {}

    analyserSource = null;
  }

  analyser = null;

  if (audioContext) {
    try {
      await audioContext.close();
    } catch (error) {}

    audioContext = null;
  }
}