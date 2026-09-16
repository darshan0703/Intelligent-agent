import "./Home.css";
import { useNavigate } from "react-router-dom";

import { useVoiceConversation } from "../context/VoiceConversationProvider";

import { startSession } from "../services/api";

import burger from "../assets/images/burgerking.png";
import rc from "../assets/images/red curve.png";
import oc from "../assets/images/orange curve.png";

function Home() {
  const navigate = useNavigate();

  const { startVoiceConversation } = useVoiceConversation();

  const handleStart = async () => {
    try {
      const session = await startSession();

      console.log("Session Started:", session);

      localStorage.setItem(
        "session_id",
        session.session_id
      );

      startVoiceConversation();

      navigate("/Categories");

    } catch (err) {
      console.error(
        "START SESSION ERROR:",
        err
      );

      alert(
        `Could not start session: ${err.message}`
      );
    }
  };

  return (
    <div className="home">
      <h1 className="home-title">
        Welcome to
      </h1>

      <img
        src={rc}
        alt="red curve"
        className="rc"
      />

      <img
        src={oc}
        alt="orange curve"
        className="oc"
      />

      <img
        src={burger}
        alt="burger"
        className="burger-image"
      />

      <div
        className="touch-bar"
        onClick={handleStart}
      >
        TOUCH TO START
      </div>
    </div>
  );
}

export default Home;