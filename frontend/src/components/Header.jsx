import "./Header.css";

import ai from "../assets/images/ai cash.png";
import logo from "../assets/images/logo.png";
import lang from "../assets/images/English.png";

function Header({ title }) {
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
      <div className="wave-container">
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
        Listening<span className="dots"></span>
      </p>

      {/* ==========================================
          LINE
          ========================================== */}
      <div className="thin-line"></div>

    </div>
  );
}

export default Header;