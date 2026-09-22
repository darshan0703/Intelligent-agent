import "./ProductCard.css";

import {
  useLocation,
  useNavigate,
} from "react-router-dom";

import { useKiosk } from "../context/KioskContext";
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
      className={`burger-card ${variant} ${className || ""}`}
      onClick={handleProductClick}
    >
      {/* PRODUCT IMAGE */}
      <img
        src={product.image}
        alt={product.name}
        className={`burger-card-image ${variant}-image`}
      />

      {/* PRODUCT NAME */}
      <h2
        className={`burger-card-name ${variant}-name`}
        title={product.name}
      >
        {product.name}
      </h2>

      {/* PRODUCT PRICE */}
      <p className={`burger-card-price ${variant}-price`}>
        ₹ {product.price}
      </p>

      {/* CUSTOMIZE / CONTINUE BUTTON */}
      <button
        className={`burger-add-btn ${variant}-button`}
        onClick={(e) => {
          e.stopPropagation();
          handleProductClick();
        }}
        aria-label={`Customize ${product.name}`}
      >
        →
      </button>
    </div>
  );
}

export default ProductCard;