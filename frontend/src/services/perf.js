/**
 * frontend/src/services/perf.js
 * Lightweight, structured performance timing instrumentation for TheAtom kiosk.
 *
 * Provides:
 * - High-precision monotonic timing via performance.now()
 * - Correlation between frontend voice/touch triggers and backend requests
 * - Milestone duration tracking from interaction start to:
 *   1. Backend response received
 *   2. Screen rendered
 *   3. First audio playback (voice)
 * - Structured log format:
 *   [PERF] interaction=<id> event=<event> duration_ms=<X> elapsed_ms=<Y> ...
 */

const isPerfEnabled = () => {
  if (typeof window !== "undefined" && window.__PERF_LOGGING__ !== undefined) {
    return Boolean(window.__PERF_LOGGING__);
  }
  return true;
};

export class PerfTracker {
  constructor(type = "voice", customId = null, initialStart = null) {
    this.type = type;
    const prefix = type === "voice" ? "v_" : "t_";
    this.id = customId || `${prefix}${Math.random().toString(16).slice(2, 10)}`;
    this.startTime = initialStart !== null ? initialStart : performance.now();
    this.stages = {};
  }

  log(event, { duration_ms, ...extra } = {}) {
    if (!isPerfEnabled()) return;
    const elapsed_ms = (performance.now() - this.startTime).toFixed(2);
    let logStr = `[PERF] interaction=${this.id} event=${event}`;

    if (duration_ms !== undefined && duration_ms !== null) {
      logStr += ` duration_ms=${Number(duration_ms).toFixed(2)}`;
    }

    logStr += ` elapsed_ms=${elapsed_ms}`;

    for (const [k, v] of Object.entries(extra)) {
      if (v !== undefined && v !== null) {
        logStr += ` ${k}=${v}`;
      }
    }

    console.log(logStr);
  }

  startStage(stageName, initialExtra = {}) {
    const t0 = performance.now();
    return (extra = {}) => {
      const t1 = performance.now();
      const duration_ms = t1 - t0;
      this.stages[stageName] = duration_ms;
      this.log(stageName, {
        duration_ms,
        ...initialExtra,
        ...extra,
      });
      return duration_ms;
    };
  }
}

// Module-level pointer to track the current active voice interaction turn
let activeVoiceTracker = null;

export function getActiveVoiceTracker() {
  return activeVoiceTracker;
}

export function setActiveVoiceTracker(tracker) {
  activeVoiceTracker = tracker;
}

export function clearActiveVoiceTracker() {
  activeVoiceTracker = null;
}

export function createPerfTracker(type = "voice", customId = null, initialStart = null) {
  return new PerfTracker(type, customId, initialStart);
}

/**
 * Measure when screen navigation has committed and rendered to the DOM.
 * Uses requestAnimationFrame followed by setTimeout to wait for browser paint.
 */
export function measureScreenRender(tracker, screenName) {
  if (!tracker) return;
  const start = performance.now();

  if (typeof window === "undefined" || typeof window.requestAnimationFrame !== "function") {
    // In non-browser / test environments
    tracker.log("milestone_screen_rendered", {
      duration_ms: (performance.now() - tracker.startTime).toFixed(2),
      screen: screenName,
    });
    return;
  }

  window.requestAnimationFrame(() => {
    setTimeout(() => {
      const renderDuration = performance.now() - start;
      tracker.log("screen_rendered", {
        duration_ms: renderDuration,
        screen: screenName,
      });
      tracker.log("milestone_screen_rendered", {
        duration_ms: (performance.now() - tracker.startTime).toFixed(2),
        screen: screenName,
      });
    }, 0);
  });
}
