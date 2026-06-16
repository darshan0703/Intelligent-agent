import "./ProductCard.css";

import { useNavigate } from "react-router-dom";

function ProductCard({
  product,
  variant,
  className
}) {

  const navigate = useNavigate();

  return (

    <div
      className={`burger-card ${variant} ${className}`}
      onClick={() =>
        navigate("/product", {
          state: {
            product
          }
        })
      }
    >

      {/* IMAGE */}

      <img
        src={product.image}
        alt={product.name}
        className={`burger-card-image ${variant}-image`}
      />

      {/* NAME */}

      <h2
        className={`burger-card-name ${variant}-name`}
      >
        {product.name}
      </h2>

      {/* DESCRIPTION */}

      <p
        className={`burger-card-description ${variant}-description`}
      >
        {product.shortDescription}
      </p>

      {/* PRICE */}

      <p
        className={`burger-card-price ${variant}-price`}
      >
        ₹ {product.price}
      </p>

      {/* BUTTON */}

      <button
        className={`burger-add-btn ${variant}-button`}
        onClick={(e) => {
          e.stopPropagation();
        }}
      >
        +
      </button>

    </div>

  );

}

export default ProductCard;