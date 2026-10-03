import "./Header.css";

import ai from "../assets/images/ai cash.png";
import logo from "../assets/images/logo.png";
import lang from "../assets/images/English.png";

import { useVoiceConversation } from "../context/VoiceConversationProvider";

function Header({ title }) {
  const { voiceStatus } = useVoiceConversation();

  const isSpeaking = voiceStatus === "speaking";
  const isListening = voiceStatus === "listening";
  const isProcessing = voiceStatus === "processing";

  return (
    <div className="header-container">

      {/* ORANGE HEADER BACKGROUND */}
      <div className="header-orange-bg">
        <div className="orange-oval oval-left"></div>
        <div className="orange-oval oval-right"></div>
      </div>

      {/* AI */}
      <img
        src={ai}
        alt="ai"
        className="ai-image"
      />

      {/* LOGO */}
      <img
        src={logo}
        alt="logo"
        className="logo-image"
      />

      {/* LANGUAGE */}
      <img
        src={lang}
        alt="lang"
        className="lang-image"
      />

      {/* TITLE */}
      <h1 className="page-title">
        {title}
      </h1>

      {/* VOICE STATUS */}
      <div className="voice-status">

        {/* CUSTOMER IS ACTUALLY SPEAKING */}
        {isListening && (
          <div className="wave-container">
            <div className="bar"></div>
            <div className="bar"></div>
            <div className="bar"></div>
            <div className="bar"></div>
            <div className="bar"></div>
          </div>
        )}

        {/* KOKORO IS ACTUALLY SPEAKING */}
        {isSpeaking && (
          <div className="speaking-icon">
            🔊
          </div>
        )}

        {/* WHISPER / BACKEND PROCESSING */}
        {isProcessing && (
          <div className="processing-icon">
            ⚙️
          </div>
        )}

        {/* STATUS TEXT */}
        <p className="listening-text">

          {isSpeaking && "Speaking..."}

          {isListening && "Listening..."}

          {isProcessing && "Processing..."}

        </p>

      </div>

      {/* LINE */}
      <div className="thin-line"></div>

    </div>
  );
}

export default Header;