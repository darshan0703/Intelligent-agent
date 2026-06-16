import "./PreviousButton.css";

import { useNavigate } from "react-router-dom";

function PreviousButton() {

  const navigate = useNavigate();

  return (

    <button
      className="previous-button"
      onClick={() => navigate(-1)}
    >

      <span className="previous-icon">
        ←
      </span>

      <span className="previous-text">
        Back
      </span>

    </button>

  );

}

export default PreviousButton;