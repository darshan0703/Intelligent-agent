import "./PreviousButton.css";

import { useNavigate } from "react-router-dom";

function PreviousButton({ onClick }) {

  const navigate = useNavigate();

  const handleBack = () => {

    if (onClick) {
      onClick();
      return;
    }

    navigate(-1);
  };

  return (

    <button
      className="previous-button"
      onClick={handleBack}
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