import "./MealPopup.css";
import { useState } from "react";

function MealPopup({

  open,
  meals,
  onClose,
  onContinue,
  
}) {

  const [selectedMeal, setSelectedMeal] = useState(null);
  const [prevOpen, setPrevOpen] = useState(open);

  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setSelectedMeal(null);
    }
  }

  const mediumMeal = meals?.meals?.medium;
  const largeMeal = meals?.meals?.large;

  const hasMedium = Boolean(mediumMeal);
  const hasLarge = Boolean(largeMeal);

  if (!open) return null;

  if (!hasMedium && !hasLarge) return null;

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
          {hasMedium && (
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

              {mediumMeal?.burger?.image && (
                <img
                  src={mediumMeal.burger.image}
                  alt="Medium Meal"
                  className="meal-image"
                />
              )}

              <p className="meal-price">
                +₹{mediumMeal?.upgrade_price}
              </p>

            </div>
          )}

          {/* LARGE */}
          {hasLarge && (
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

              {largeMeal?.burger?.image && (
                <img
                  src={largeMeal.burger.image}
                  alt="Large Meal"
                  className="meal-image meal-image-large"
                />
              )}

              <p className="meal-price">
                +₹{largeMeal?.upgrade_price}
              </p>

            </div>
          )}

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
            disabled={
              !selectedMeal ||
              (selectedMeal === "medium" && !hasMedium) ||
              (selectedMeal === "large" && !hasLarge)
            }
            onClick={() => {
              if (
                selectedMeal &&
                ((selectedMeal === "medium" && hasMedium) ||
                  (selectedMeal === "large" && hasLarge))
              ) {
                onContinue(selectedMeal);
              }
            }}
          >
            Continue
          </button>
          

        </div>

      </div>

    </div>

  );

}

export default MealPopup;