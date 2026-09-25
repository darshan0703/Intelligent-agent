/**
 * frontend/src/utils/session.js
 * Utility for dynamic session management across kiosk visits & page reloads.
 */

export const getSessionId = () => {
  let sid = sessionStorage.getItem("atom_session_id") || localStorage.getItem("session_id");
  if (!sid) {
    sid = "kiosk-session-" + Date.now() + "-" + Math.random().toString(36).substring(2, 7);
  }
  sessionStorage.setItem("atom_session_id", sid);
  localStorage.setItem("session_id", sid);
  return sid;
};

export const resetSessionId = () => {
  const newSid = "kiosk-session-" + Date.now() + "-" + Math.random().toString(36).substring(2, 7);
  sessionStorage.setItem("atom_session_id", newSid);
  localStorage.setItem("session_id", newSid);
  return newSid;
};
