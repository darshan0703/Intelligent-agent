import "./ProductPage.css";

import { useLocation } from "react-router-dom";
import { useState } from "react";

import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

function ProductPage() {

  const { state } = useLocation();

  const product = state?.product || {
    name: "Chicken Whopper",
    shortDescription: "Flame Grilled Chicken Burger",
    longDescription:
      "A juicy flame grilled chicken patty topped with fresh lettuce, tomato and creamy mayo.",
    price: 179,
    foodType: "nonveg",
    image: "/src/assets/images/Burgers/Chicken Whopper Deluxe.png"
  };

  const [quantity, setQuantity] = useState(1);

  return (

    <div className="product-page">

      <Header
        title="Product Details"
      />

      <PreviousButton />

      {/* PRODUCT IMAGE */}

      <img
        src={product.image}
        alt={product.name}
        className="product-image"
      />

      {/* PRODUCT TITLE + FOOD TYPE */}

      <div className="product-title-container">

     <h1 className="product-name">
      {(() => {
      const words = product.name.split(" ");

     const midpoint = Math.ceil(words.length / 2);

      return (
      <>
        {words.slice(0, midpoint).join(" ")}
        <br />
        {words.slice(midpoint).join(" ")}
         </>
         );
        })()}
        </h1>

        {product.foodType && (

          <img
            src={
              product.foodType === "veg"
                ? vegIcon
                : nonVegIcon
            }
            alt={product.foodType}
            className="product-type-icon"
          />

        )}

      </div>

      {/* SHORT DESCRIPTION */}

      <p className="product-short-description">
        {product.shortDescription}
      </p>

      {/* PRICE */}

      <p className="product-price">
        ₹ {product.price}
      </p>

      {/* ABOUT */}

      <h2 className="section-title about-title">
        About This Item
      </h2>

      <p className="product-description">
        {product.longDescription}
      </p>

      {/* RECOMMENDED */}

      <h2 className="section-title recommended-title">
        Recommended With
      </h2>

      <div className="recommendations">

        <div className="recommend-card">
          Fries
        </div>

        <div className="recommend-card">
          Coke
        </div>

        <div className="recommend-card">
          Nuggets
        </div>

      </div>

      {/* QUANTITY */}

      <div className="quantity-selector">

        <button
          className="qty-btn"
          onClick={() =>
            setQuantity(prev =>
              prev > 1
                ? prev - 1
                : 1
            )
          }
        >
          −
        </button>

        <span className="qty-value">
          {quantity}
        </span>

        <button
          className="qty-btn"
          onClick={() =>
            setQuantity(prev => prev + 1)
          }
        >
          +
        </button>

      </div>

      {/* ADD TO CART */}

      <button
        className="add-cart-btn"
      >
        Add To Cart • ₹{" "}
        {product.price * quantity}
      </button>

      {/* CART */}

       <CartContainer
        itemCount={0}
        total={0}
      /> 

    </div>

  );

}

export default ProductPage;