import "./ProductPage.css";

import { useLocation } from "react-router-dom";
import { useState } from "react";
import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";


import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

function ProductPage() {

  const { productData } = useKiosk();
  const { syncCart } = useCart();
  const { itemCount, total } = useCart();
  const product = productData?.data?.product;
  const recommendations = productData?.data?.recommendations || [];

  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(false);

  if (!product) {

    return (

      <div className="product-page">

        <Header
          title="Product Details"
        />

        <PreviousButton />

        <h2
          style={{
            textAlign: "center",
            marginTop: "200px"
          }}
        >
          No product selected.
        </h2>

      </div>

    );

  }

  const handleAddToCart = async () => {

    if (loading) return;

    setLoading(true);

    try {

      const response = await fetch(
        "http://127.0.0.1:8000/cart/add",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            item_name: product.name,
            quantity: quantity
          })
        }
      );

      const data = await response.json();
      console.log("PRODUCT RESPONSE:", data);
      syncCart(data);

      // Next step:
      // Update global cart
      // Navigate back to menu

    } catch (error) {

      console.error("Failed to add item:", error);

    } finally {

      setLoading(false);

    }

  };

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

      {/* PRODUCT TITLE */}

      <div className="product-title-container">

        <h1 className="product-name">

          {(() => {

            const words = product.name.split(" ");

            const midpoint = Math.ceil(
              words.length / 2
            );

            return (

              <>

                {words
                  .slice(0, midpoint)
                  .join(" ")}

                <br />

                {words
                  .slice(midpoint)
                  .join(" ")}

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

       {recommendations.map((item) => (

        <div
         key={item.id}
         className="recommend-card"
        >
         {item.name}
        </div>

  ))}

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
            setQuantity(prev =>
              prev + 1
            )
          }
        >
          +
        </button>

      </div>

      {/* ADD TO CART */}

      <button
        className="add-cart-btn"
        onClick={handleAddToCart}
        disabled={loading}
      >

        {loading
          ? "Adding..."
          : `Add To Cart • ₹ ${product.price * quantity}`}

      </button>

      {/* CART */}

      <CartContainer />

    </div>
  

  );

}

export default ProductPage;