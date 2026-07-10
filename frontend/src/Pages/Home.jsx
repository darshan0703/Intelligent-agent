import "./Home.css";
import { useNavigate } from "react-router-dom";

import { startSession } from "../services/api";

import burger from "../assets/images/burgerking.png";
import rc from "../assets/images/red curve.png";
import oc from "../assets/images/orange curve.png";

function Home() {
  const navigate = useNavigate();

  const handleStart = async () => {
    try {
      const session = await startSession();

      console.log("Session Started:", session);

      localStorage.setItem(
        "session_id",
        session.session_id
      );

      navigate("/Categories");
    } catch (err) {
      console.error(err);
      alert("Backend is not running.");
    }
  };

  return (
    <div className="home">
      <h1>Welcome to</h1>

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