import "./MealPopup.css";
import { useState, useEffect } from "react";

function MealPopup({

  open,
  meals,
  onClose,
  onContinue,

}) {

  const [selectedMeal, setSelectedMeal] = useState(null);

  useEffect(() => {

    if (open) {
      setSelectedMeal(null);
    }

  }, [open]);

  if (!open) return null;

  if (!meals) return null;

  return (

    <div className="meal-popup-overlay">

      <div className="meal-popup">

        <div className="meal-popup-header">
  <h1 className="meal-popup-title">
    Make it a Meal?
  </h1>

  <p className="meal-popup-subtitle">
    Upgrade your burger with fries and a refreshing drink.
  </p>
</div>

        <div className="meal-options">

          {/* MEDIUM */}

          <div
            className={`meal-card ${
              selectedMeal === "medium"
                ? "selected"
                : ""
            }`}
            onClick={() => setSelectedMeal("medium")}
          >

            <h2 className="meal-size">
              Medium Meal
            </h2>

            <img
              src={meals.meals.medium.burger.image}
              alt="Medium Meal"
              className="meal-image"
            />


            <p className="meal-price">
              +₹{meals.meals.medium.upgrade_price}
            </p>

          </div>

          {/* LARGE */}

          <div
            className={`meal-card ${
              selectedMeal === "large"
                ? "selected"
                : ""
            }`}
            onClick={() => setSelectedMeal("large")}
          >

            <h2 className="meal-size">
              Large Meal
            </h2>

            <img
              src={meals.meals.large.burger.image}
              alt="Large Meal"
              className="meal-image meal-image-large"
            />

            <p className="meal-price">
              +₹{meals.meals.large.upgrade_price}
            </p>

          </div>

        </div>

        {/* FOOTER */}

        <div className="meal-popup-footer">

          <button
            className="meal-secondary-btn"
            onClick={onClose}
          >
            No Thanks
          </button>

          <button
            className="meal-primary-btn"
            disabled={!selectedMeal}
            onClick={() => onContinue(selectedMeal)}
          >
            Continue
          </button>
          

        </div>

      </div>

    </div>

  );

}

export default MealPopup;