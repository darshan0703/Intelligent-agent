
import "./Header.css";

import ai from "../assets/images/ai cash.png";
import logo from "../assets/images/logo.png";
import lang from "../assets/images/English.png";

import { useVoiceConversation } from "../context/VoiceConversationProvider";

function Header({ title }) {
  const { voiceActive, voiceStatus } = useVoiceConversation();

  const isSpeaking = voiceActive && voiceStatus === "speaking";
  const isListening = voiceActive && voiceStatus === "listening";
  const isProcessing = voiceActive && voiceStatus === "processing";

  return (
    <div className="header-container">
      <div className="header-orange-bg">
        <div className="orange-oval oval-left"></div>
        <div className="orange-oval oval-right"></div>
      </div>

      <img src={ai} alt="ai" className="ai-image" />
      <img src={logo} alt="logo" className="logo-image" />
      <img src={lang} alt="lang" className="lang-image" />

      <h1 className="page-title">{title}</h1>

      {isListening && (
        <div className="voice-indicator">
          <div className="wave-container">
            {[1, 2, 3, 4, 5].map((number) => (
              <div className="bar" key={number}></div>
            ))}
          </div>

          <p className="voice-status-text">
            Listening<span className="dots"></span>
          </p>
        </div>
      )}

      {isProcessing && (
        <p className="voice-status-text">Processing...</p>
      )}

      {isSpeaking && (
        <p className="voice-status-text speaking-text">
          Speaking<span className="dots"></span>
        </p>
      )}

      <div className="thin-line"></div>
    </div>
  );
}

export default Header;
