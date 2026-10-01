import { isSpeaking } from "./ttsService";

let interruptionHandler = null;

export function setInterruptionHandler(handler) {
  interruptionHandler = handler;
}

export function startInterruptionDetection() {
  console.log("INTERRUPTION DETECTION READY");
}

export function stopInterruptionDetection() {
  console.log("INTERRUPTION DETECTION STOPPED");
}

export function handleSileroInterruption() {
  if (!isSpeaking()) {
    return;
  }

  console.log("CUSTOMER INTERRUPTED CASHIER");

  interruptionHandler?.();
}