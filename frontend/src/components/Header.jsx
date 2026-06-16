import "./Header.css";

import ai from "../assets/images/ai cash.png";
import logo from "../assets/images/logo.png";
import lang from "../assets/images/English.png";

function Header({ title }) {

  return (

    <>

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

      {/* WAVE */}
      <div className="wave-container">

        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>

      </div>

      {/* LISTENING */}
      <p className="listening-text">
        Listening<span className="dots"></span>
      </p>

      {/* LINE */}
      <div className="thin-line"></div>

    </>
  );
}

export default Header;