const API_URL = "";

let screenSyncSeq = 0;
let lastKnownSessionId = null;

export function resetScreenSyncSeq() {
  screenSyncSeq = 0;
}

export async function syncScreen(screen, extra = {}) {
  try {
    const sessionId = localStorage.getItem("session_id") || "default";
    if (sessionId !== lastKnownSessionId) {
      lastKnownSessionId = sessionId;
      screenSyncSeq = 0;
    }
    const seq = ++screenSyncSeq;

    console.log(
      "SYNCING CURRENT SCREEN:",
      screen,
      `[seq: ${seq}]`,
      extra
    );

    const response = await fetch(
      `${API_URL}/screen`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          screen,
          seq,
          session_id: sessionId,
          client_timestamp: Date.now(),
          ...extra,
        }),
      }
    );

    if (!response.ok) {
      throw new Error(
        `Screen sync failed: ${response.status}`
      );
    }

    const data = await response.json();

    console.log(
      "SCREEN SYNC RESPONSE:",
      data
    );

    return data;
  } catch (error) {
    console.error(
      "SCREEN SYNC ERROR:",
      error
    );
  }
}