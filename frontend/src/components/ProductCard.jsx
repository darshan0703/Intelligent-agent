import "./ProductCard.css";

import { useNavigate } from "react-router-dom";
import { useKiosk } from "../context/KioskContext";
import { getRoute } from "../utils/navigation";import { sendMessage } from "../services/api";


function ProductCard({
  product,
  variant,
  className
}) {

  const navigate = useNavigate();
  const { setProductData } = useKiosk();
  return (

    <div
      className={`burger-card ${variant} ${className}`}
      onClick={async () => {
        const data = await sendMessage(product.name);
        setProductData(data);
        navigate(getRoute(data.screen));
      }}
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
  onClick={async (e) => {
    e.stopPropagation();

    const data = await sendMessage(product.name);
    console.log("PRODUCT RESPONSE:", data);
    console.log("SCREEN:", data.screen);
    console.log("ROUTE:", getRoute(data.screen));
    setProductData(data);

    navigate(getRoute(data.screen));
  }}
 >
  +
 </button>

    </div>

  );

}

export default ProductCard;