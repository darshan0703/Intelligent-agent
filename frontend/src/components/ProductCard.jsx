import "./ProductCard.css";

import { useLocation, useNavigate } from "react-router-dom";import { useKiosk } from "../context/KioskContext";
import { getRoute } from "../utils/navigation";

function ProductCard({
  product,
  variant,
  className,
  returnTo,
}) {

const navigate = useNavigate();
const location = useLocation();
const { setProductData } = useKiosk();
const origin = location.state?.origin || "/";

  const handleProductClick = () => {
    console.log("CLICKED");

    setProductData({
      screen: "product",
      data: {
        product,
        recommendations: [],
      },
    });
    console.log(getRoute("product"));

    navigate(getRoute("product"), {
  state: {
    origin: location.pathname,
  },
  });

  };

  return (

    <div
      className={`burger-card ${variant} ${className}`}
      onClick={handleProductClick}
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

      {/* ADD BUTTON */}

      <button
        className={`burger-add-btn ${variant}-button`}
        onClick={(e) => {
          e.stopPropagation();
          handleProductClick();
        }}
      >
        +
      </button>

    </div>

  );

}

export default ProductCard;