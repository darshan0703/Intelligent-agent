import "./ProductPage.css";

import { useState, useEffect } from "react";
import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";
import { useLocation, useNavigate } from "react-router-dom";

import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";
import MealPopup from "../components/MealPopup";
import FooterDecoration from "../components/FooterDecoration";

import { syncScreen } from "../services/screenService";   // NEW

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

function ProductPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const origin = location.state?.origin || "/";

  const {
    productData,
    mealData,
    setMealData,
    mealPopupOpen,
    setMealPopupOpen,
  } = useKiosk();

  const { syncCart } = useCart();

  const product = productData?.data?.product;
  const recommendations =
    productData?.data?.recommendations || [];

  const [quantity, setQuantity] = useState(1);

  const isBurger =
    product?.category?.toLowerCase() === "burger" ||
    product?.category?.toLowerCase() === "burgers";

  /* =========================================
     PRODUCT SCREEN ACTIVE
  ========================================= */

  useEffect(() => {
    if (product) {
      syncScreen("product");
    }
  }, [product]);

  /* =========================================
     DISMISS MEMORY
  ========================================= */

  const getDismissedKey = () => {
    const sessionId =
      localStorage.getItem("session_id") || "default";

    return `dismissed_meals_${sessionId}`;
  };

  const isProductDismissed = (productId) => {
    try {
      const dismissed = JSON.parse(
        sessionStorage.getItem(getDismissedKey()) || "[]"
      );

      return dismissed.includes(productId);
    } catch {
      return false;
    }
  };

  const dismissProduct = (productId) => {
    try {
      const dismissed = JSON.parse(
        sessionStorage.getItem(getDismissedKey()) || "[]"
      );

      if (!dismissed.includes(productId)) {
        sessionStorage.setItem(
          getDismissedKey(),
          JSON.stringify([...dismissed, productId])
        );
      }
    } catch {}
  };

  /* =========================================
     MEAL OFFER
  ========================================= */

  const checkMealOffer = async ({
    automatic = false,
    productId = product?.id,
    signal,
  } = {}) => {
    if (!product || !isBurger) return;

    const requestedProductId = productId;

    try {
      const response = await fetch("/meal/options", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_id: requestedProductId,
        }),
        signal,
      });

      const data = await response.json();

      if (
        signal?.aborted ||
        product?.id !== requestedProductId
      ) {
        return;
      }

      if (data.success && data.is_meal_available) {

        if (
          automatic &&
          isProductDismissed(requestedProductId)
        ) {
          setMealPopupOpen(false);
          return;
        }

        setMealData(data);
        setMealPopupOpen(true);

        // NEW
        syncScreen("meal_popup");

      } else {
        setMealPopupOpen(false);
      }

    } catch (error) {

      if (error.name === "AbortError") return;

      console.error(error);

      if (product?.id === requestedProductId) {
        setMealPopupOpen(false);
      }
    }
  };

  /* =========================================
     AUTO CHECK
  ========================================= */

  useEffect(() => {

    if (!product) return;

    if (!isBurger) {
      setMealPopupOpen(false);
      setMealData(null);
      return;
    }

    const controller = new AbortController();

    const currentProductId = product.id;

    setMealPopupOpen(false);
    setMealData(null);

    if (!isProductDismissed(currentProductId)) {

      checkMealOffer({
        automatic: true,
        productId: currentProductId,
        signal: controller.signal,
      });

    }

    return () => controller.abort();

  }, [product?.id, isBurger]);

  /* =========================================
     MANUAL MEAL BUTTON
  ========================================= */

  const handleMealButtonClick = () => {

    if (!isBurger) return;

    if (
      mealData?.success &&
      mealData?.is_meal_available
    ) {
      setMealPopupOpen(true);
      syncScreen("meal_popup");          // NEW
      return;
    }

    checkMealOffer({
      automatic: false,
      productId: product.id,
    });
  };

  /* =========================================
     CONTINUE TO MEAL
  ========================================= */

  const handleContinue = (mealSize) => {

    setMealPopupOpen(false);

    syncScreen("product");              // NEW

    navigate("/mealpage", {
      state: {
        meal: mealData.meals[mealSize],
        origin,
      },
    });

  };

  /* =========================================
     EMPTY STATE
  ========================================= */

  if (!product) {
    return (
      <div className="product-page">
        <Header title="Product Details" />
        <PreviousButton />

        <h2
          style={{
            textAlign: "center",
            marginTop: "200px",
          }}
        >
          No product selected.
        </h2>

      </div>
    );
  }

  /* =========================================
     ADD TO CART
  ========================================= */

  const handleAddToCart = async () => {

    try {

      const response = await fetch("/cart/add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_name: product.name,
          quantity,
        }),
      });

      const data = await response.json();

      if (data.success) {
        syncCart(data);
        navigate(origin);
      }

    } catch (error) {
      console.error(error);
    }
  };

  /* =========================================
     UI
  ========================================= */

  return (
    <div className="product-page">

      <Header title="Product Details" />

      <PreviousButton />

      <img
        src={product.image}
        alt={product.name}
        className="product-image"
      />

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

        </h1>

      </div>

      <p className="product-short-description">
        {product.shortDescription}
      </p>

      <div className="product-price-row">

        <p className="product-price">
          ₹ {product.price}
        </p>

        {isBurger && (
          <button
            className="meal-upgrade-btn"
            onClick={handleMealButtonClick}
          >
            Upgrade to a Meal
          </button>
        )}

      </div>

      <h2 className="section-title about-title">
        About This Item
      </h2>

      <p className="product-description">
        {product.longDescription}
      </p>

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

      <div className="quantity-selector">

        <button
          className="qty-btn"
          onClick={() =>
            setQuantity((prev) =>
              prev > 1 ? prev - 1 : 1
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
            setQuantity((prev) => prev + 1)
          }
        >
          +
        </button>

      </div>

      <button
        className="add-cart-btn"
        onClick={handleAddToCart}
      >
        {`Add To Cart • ₹ ${
          product.price * quantity
        }`}
      </button>

      <CartContainer />

      {isBurger && (
        <MealPopup
          open={mealPopupOpen}
          meals={mealData}
          onClose={() => {

            dismissProduct(product.id);

            setMealPopupOpen(false);

            syncScreen("product");      // NEW

          }}
          onContinue={handleContinue}
        />
      )}

      <FooterDecoration />

    </div>
  );
}

export default ProductPage;