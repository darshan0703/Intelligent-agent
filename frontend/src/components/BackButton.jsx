import "./BackButton.css";

import { useNavigate } from "react-router-dom";

function BackButton() {

  const navigate = useNavigate();

  return (

    <button
      className="back-button"
      onClick={() => navigate("/Categories")}
    >

      <span className="back-icon">
        ←
      </span>

      <span className="back-text">
        Category
      </span>

    </button>

  );

}

export default BackButton;