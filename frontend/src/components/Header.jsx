import "./Header.css";

import ai from "../assets/images/ai cash.png";
import logo from "../assets/images/logo.png";
import lang from "../assets/images/English.png";
import { useVoiceConversation } from "../context/VoiceConversationProvider";

function Header({ title }) {
  const {
    isMicMuted,
    toggleMicMute,
    isSoundMuted,
    toggleSoundMute,
  } = useVoiceConversation();

  return (
    <div className="header-container">

      {/* ==========================================
          ORANGE HEADER BACKGROUND
          ========================================== */}
      <div className="header-orange-bg">
        <div className="orange-oval oval-left"></div>
        <div className="orange-oval oval-right"></div>
      </div>

      {/* ==========================================
          AI
          ========================================== */}
      <img
        src={ai}
        alt="ai"
        className="ai-image"
      />

      {/* ==========================================
          AUDIO CONTROLS (MIC & SOUND)
          ========================================== */}
      <div className="header-audio-controls">
        <button
          type="button"
          className={`audio-btn mic-btn ${isMicMuted ? "muted" : "active"}`}
          onClick={toggleMicMute}
          title={isMicMuted ? "Unmute Microphone" : "Mute Microphone"}
          aria-label={isMicMuted ? "Unmute Microphone" : "Mute Microphone"}
        >
          <span className="btn-icon">{isMicMuted ? "🔇" : "🎙️"}</span>
          <span className="btn-label">{isMicMuted ? "Mic Off" : "Mic On"}</span>
        </button>

        <button
          type="button"
          className={`audio-btn sound-btn ${isSoundMuted ? "muted" : "active"}`}
          onClick={toggleSoundMute}
          title={isSoundMuted ? "Unmute Sound" : "Mute Sound"}
          aria-label={isSoundMuted ? "Unmute Sound" : "Mute Sound"}
        >
          <span className="btn-icon">{isSoundMuted ? "🔇" : "🔊"}</span>
          <span className="btn-label">{isSoundMuted ? "Sound Off" : "Sound On"}</span>
        </button>
      </div>

      {/* ==========================================
          LOGO
          ========================================== */}
      <img
        src={logo}
        alt="logo"
        className="logo-image"
      />

      {/* ==========================================
          LANGUAGE
          ========================================== */}
      <img
        src={lang}
        alt="lang"
        className="lang-image"
      />

      {/* ==========================================
          TITLE
          ========================================== */}
      <h1 className="page-title">
        {title}
      </h1>

      {/* ==========================================
          WAVE
          ========================================== */}
      <div className={`wave-container ${isMicMuted ? "muted-wave" : ""}`}>
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
      </div>

      {/* ==========================================
          LISTENING
          ========================================== */}
      <p className="listening-text">
        {isMicMuted ? "Mic Off" : <>Listening<span className="dots"></span></>}
      </p>

      {/* ==========================================
          LINE
          ========================================== */}
      <div className="thin-line"></div>

    </div>
  );
}

export default Header;