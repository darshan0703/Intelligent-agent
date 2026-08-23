import "./MealCard.css";

function MealCard({

  title,
  image,
  price,
  selected,
  onClick,

}) {

  return (

    <div
      className={`meal-card ${
        selected ? "selected" : ""
      }`}
      onClick={onClick}
    >

      {/* IMAGE */}

      {image ? (

        <img
          src={image}
          alt={title}
          className="meal-card-image"
        />

      ) : (

        <div className="meal-card-placeholder">

          Meal Image

        </div>

      )}

      {/* TITLE */}

      <h2 className="meal-card-title">

        {title}

      </h2>

      {/* PRICE */}

      <p className="meal-card-price">

        ₹ {price}

      </p>

    </div>

  );

}

export default MealCard;