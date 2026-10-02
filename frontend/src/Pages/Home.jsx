import "./Home.css";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useVoiceConversation } from "../context/VoiceConversationProvider";
import { startSession } from "../services/api";

import mealHome from "../assets/images/Meals/mealhome5.png";

function Home() {
  const navigate = useNavigate();
  const { startVoiceConversation } = useVoiceConversation();

  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    if (starting) return;

    setStarting(true);

    try {
      const session = await startSession();

      localStorage.setItem("session_id", session.session_id);

      startVoiceConversation();

      navigate("/Categories");
    } catch (err) {
      console.error("START SESSION ERROR:", err);

      alert(`Could not start session: ${err.message}`);

      setStarting(false);
    }
  };

  return (
    <div className="home">
      <img
        src={mealHome}
        alt="Burger King welcome"
        className="meal-home-image"
      />

      <div
        className="touch-bar"
        onClick={handleStart}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            handleStart();
          }
        }}
      >
        {starting ? "STARTING..." : "TOUCH TO START"}
      </div>
    </div>
  );
}

export default Home;
