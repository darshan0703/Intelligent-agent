const API_URL = "";

let screenSyncSeq = 0;
let latestAcceptedSeq = 0;
let lastKnownSessionId = null;
const inFlightRequests = new Map();
let syncWaiters = [];

function checkSession(sessionId) {
  if (lastKnownSessionId !== null && sessionId !== lastKnownSessionId) {
    lastKnownSessionId = sessionId;
    screenSyncSeq = 0;
    latestAcceptedSeq = 0;
    inFlightRequests.clear();
    rejectAllWaiters(new Error("Session changed during screen sync"));
  } else if (lastKnownSessionId === null) {
    lastKnownSessionId = sessionId;
  }
}

function rejectAllWaiters(error) {
  const waiters = syncWaiters;
  syncWaiters = [];
  waiters.forEach((w) => {
    clearTimeout(w.timer);
    w.reject(error);
  });
}

function notifyWaiters() {
  const remaining = [];
  for (const w of syncWaiters) {
    if (w.sessionId !== lastKnownSessionId) {
      clearTimeout(w.timer);
      w.reject(new Error("Session expired during screen sync"));
      continue;
    }

    const targetSeq = screenSyncSeq;
    if (latestAcceptedSeq >= targetSeq) {
      clearTimeout(w.timer);
      w.resolve({ success: true, seq: latestAcceptedSeq });
    } else {
      remaining.push(w);
    }
  }
  syncWaiters = remaining;
}

function handleSyncCompletion(seq, reqSessionId, isAccepted, error) {
  inFlightRequests.delete(seq);

  if (reqSessionId !== lastKnownSessionId) {
    return;
  }

  if (isAccepted) {
    latestAcceptedSeq = Math.max(latestAcceptedSeq, seq);
    notifyWaiters();
    return;
  }

  const targetSeq = screenSyncSeq;
  if (latestAcceptedSeq < targetSeq) {
    const hasViableInFlight = Array.from(inFlightRequests.keys()).some(
      (s) => s >= targetSeq
    );

    if (!hasViableInFlight && seq >= targetSeq) {
      const syncErr =
        error ||
        new Error(
          `Screen synchronization could not confirm latest state (sequence ${seq} failed or was ignored)`
        );
      rejectAllWaiters(syncErr);
    }
  }
}

export function resetScreenSyncSeq() {
  screenSyncSeq = 0;
  latestAcceptedSeq = 0;
  inFlightRequests.clear();
  rejectAllWaiters(new Error("Screen synchronization reset"));
}

export function getScreenSyncState() {
  return {
    screenSyncSeq,
    latestAcceptedSeq,
    lastKnownSessionId,
    inFlightCount: inFlightRequests.size,
  };
}

export function setScreenSyncSessionId(sessionId) {
  checkSession(sessionId);
}

export function syncScreen(screen, extra = {}) {
  const sessionId =
    (typeof localStorage !== "undefined" && localStorage.getItem("session_id")) ||
    "default";
  checkSession(sessionId);

  const seq = ++screenSyncSeq;
  const requestSessionId = sessionId;

  console.log(
    "SYNCING CURRENT SCREEN:",
    screen,
    `[seq: ${seq}]`,
    extra
  );

  const syncPromise = (async () => {
    try {
      const response = await fetch(`${API_URL}/screen`, {
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
      });

      if (!response.ok) {
        throw new Error(`Screen sync failed: ${response.status}`);
      }

      const data = await response.json();
      console.log("SCREEN SYNC RESPONSE:", data);

      const isAccepted = Boolean(data && data.success && !data.stale_ignored);
      handleSyncCompletion(seq, requestSessionId, isAccepted, null);
      return data;
    } catch (error) {
      console.error("SCREEN SYNC ERROR:", error);
      handleSyncCompletion(seq, requestSessionId, false, error);
      throw error;
    }
  })();

  // Catch to prevent unhandled rejection when callers don't await syncScreen
  syncPromise.catch(() => {});

  // Expose synchronous sequence on the returned promise
  syncPromise.seq = seq;

  inFlightRequests.set(seq, { sessionId: requestSessionId, promise: syncPromise });
  return syncPromise;
}

export function waitForLatestScreenSync(timeoutMs = 5000) {
  const sessionId =
    (typeof localStorage !== "undefined" && localStorage.getItem("session_id")) ||
    "default";
  checkSession(sessionId);

  const targetSessionId = sessionId;
  const targetSeq = screenSyncSeq;

  if (latestAcceptedSeq >= targetSeq && targetSessionId === lastKnownSessionId) {
    return Promise.resolve({ success: true, seq: latestAcceptedSeq });
  }

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      syncWaiters = syncWaiters.filter((w) => w.timer !== timer);
      reject(
        new Error(
          `Screen synchronization timed out waiting for sequence ${screenSyncSeq}`
        )
      );
    }, timeoutMs);

    syncWaiters.push({
      sessionId: targetSessionId,
      resolve,
      reject,
      timer,
    });
  });
}