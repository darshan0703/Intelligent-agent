import "./ProductPage.css";

import { useState, useEffect } from "react";
import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";
import { useLocation, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";
import MealPopup from "../components/MealPopup";

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";
import { getCategoryFallbackImage } from "../utils/imageFallback";
import { getSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function ProductPage() {

  const navigate = useNavigate();
  const location = useLocation();

  const origin = location.state?.origin || "/";        
  const handleContinue = (mealSize) => {
    navigate("/mealpage", {
      state: {
        meal: mealData?.meals?.[mealSize] || {},
        origin: origin,
      },
    });
  };

  const {
    productData,
    mealData,
    setMealData,
    mealPopupOpen,
    setMealPopupOpen,
    sessionContext,
    foodPreference,
  } = useKiosk();

  const { addItemOptimistic, cart } = useCart();

  const product = productData?.data?.product;
  const initialRecs = productData?.data?.recommendations || [];
  const [productRecs, setProductRecs] = useState(initialRecs);
  const [recHeadline, setRecHeadline] = useState(product?.name ? `Pairs Best with ${product.name}` : "Pairs Best With");

  const [quantity, setQuantity] = useState(1);

  useEffect(() => {
    if (!product) return;

    const loadRecommendations = async () => {
      try {
        const sid = getSessionId();
        const ctxParam = sessionContext ? `&session_context=${encodeURIComponent(JSON.stringify(sessionContext))}` : "";
        const cartParam = cart && cart.length > 0 ? `&cart_payload=${encodeURIComponent(JSON.stringify(cart))}` : "";
        const prefParam = foodPreference && foodPreference !== "both" ? `&preference=${encodeURIComponent(foodPreference)}` : "";
        const res = await fetch(`${API_BASE_URL}/recommendations/product/${product.id}?session_id=${sid}${ctxParam}${cartParam}${prefParam}`);
        const data = await res.json();
        if (data.success && data.recommendations && data.recommendations.length > 0) {
          let recs = data.recommendations;
          if (foodPreference === "veg") {
            recs = recs.filter((i) => {
              const ft = (i.foodType || i.type || i.food_type || "").toLowerCase();
              return ft === "veg" || (!ft.includes("non") && !/chicken|wings|nugget/i.test(i.name || ""));
            });
          } else if (foodPreference === "non veg" || foodPreference === "non_veg") {
            recs = recs.filter((i) => {
              const ft = (i.foodType || i.type || i.food_type || "").toLowerCase();
              return ft.includes("non") || /chicken|wings|nugget/i.test(i.name || "");
            });
          }
          setProductRecs(recs);
          if (data.headline) setRecHeadline(data.headline);
        }
      } catch (err) {
        console.error("Failed to load product recommendations:", err);
      }
    };

    loadRecommendations();

    const checkMealOffer = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/meal/options`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              item_id: product.id,
              session_id: getSessionId(),
              preference: foodPreference,
            }),
          }
        );

        const data = await response.json();
        if (data.success && data.is_meal_available) {
          setMealData(data);
          setMealPopupOpen(true);
        } else {
          setMealPopupOpen(false);
        }
      } catch (error) {
        console.error("Failed to load meal offer:", error);
        setMealPopupOpen(false);
      }
    };

    checkMealOffer();
  }, [product, cart, sessionContext, foodPreference]);

  if (!product) {
    return (
      <div className="product-page">
        <Header title="Product Details" />
        <PreviousButton />
        <h2 style={{ textAlign: "center", marginTop: "200px" }}>
          No product selected.
        </h2>
      </div>
    );
  }

  const handleAddToCart = () => {
    try {
      addItemOptimistic(product, quantity);
      navigate(origin);
    } catch (error) {
      console.error("Failed to add to cart:", error);
    }
  };

  return (
    <div className="product-page">
      <Header title="Product Details" />
      <PreviousButton />

      {/* PRODUCT IMAGE */}
      <img
        src={product.image || "/src/assets/images/Burgers/Crispy Veg.png"}
        alt={product.name}
        className="product-image"
        onError={(e) => { e.currentTarget.src = "/src/assets/images/Burgers/Crispy Veg.png"; }}
      />

      {/* PRODUCT TITLE */}
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
              src={product.foodType === "veg" ? vegIcon : nonVegIcon}
              alt={product.foodType}
              className="product-type-icon"
            />
          )}
        </h1>
      </div>

      {/* SHORT DESCRIPTION */}
      <p className="product-short-description">
        {product.shortDescription || product.short_description || product.description || "Freshly made to order with premium ingredients."}
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
        {product.longDescription || product.long_description || product.description || product.shortDescription || product.short_description || "Flame-grilled Burger King favorite prepared fresh daily with authentic flavors."}
      </p>

      {/* RECOMMENDED WITH PAIRINGS */}
      <h2 className="section-title recommended-title">
        {recHeadline}
      </h2>

      <div className="recommendations">
        {productRecs.map((item) => (
          <div
            key={item.id}
            className="recommend-card"
            onClick={() => addItemOptimistic(item, 1)}
            title={`Add ${item.name} to cart`}
            style={{
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "10px 18px",
              background: item.has_micro_deal ? "#fffaf5" : "white",
              border: item.has_micro_deal ? "1.5px solid #f97316" : "none",
              borderRadius: "16px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.06)",
              transition: "transform 0.15s ease",
              position: "relative",
            }}
          >
            {item.badge && (
              <span style={{
                position: "absolute",
                top: "-8px",
                left: "12px",
                fontSize: "9px",
                fontWeight: "700",
                background: "#502314",
                color: "#ffffff",
                padding: "2px 8px",
                borderRadius: "10px",
              }}>
                {item.badge}
              </span>
            )}
            {item.image && (
              <img
                src={item.image}
                alt={item.name}
                style={{ width: "52px", height: "52px", objectFit: "contain", borderRadius: "10px", marginTop: item.badge ? "6px" : "0" }}
                onError={(e) => {
                  e.currentTarget.onerror = null;
                  e.currentTarget.src = getCategoryFallbackImage(item.category, item.name);
                }}
              />
            )}
            <div style={{ display: "flex", flexDirection: "column", textAlign: "left" }}>
              <span style={{ fontSize: "15px", fontWeight: "700", color: "var(--bk-brown)" }}>
                {item.name}
              </span>
              {item.synergy_reason && (
                <span style={{ fontSize: "11px", color: "#854d0e", fontWeight: "500", marginTop: "2px" }}>
                  {item.synergy_reason}
                </span>
              )}
              {item.has_micro_deal ? (
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px" }}>
                  <span style={{ fontSize: "14px", color: "#dc2626", fontWeight: "800" }}>
                    +₹{item.offer_price}
                  </span>
                  <span style={{ fontSize: "11px", color: "#9ca3af", textDecoration: "line-through" }}>
                    ₹{item.original_price}
                  </span>
                  <span style={{ fontSize: "10px", background: "#fee2e2", color: "#dc2626", padding: "1px 4px", borderRadius: "4px", fontWeight: "700" }}>
                    {item.deal_tag || `SAVE ${item.discount_pct}%`}
                  </span>
                </div>
              ) : (
                <span style={{ fontSize: "14px", color: "#e35205", fontWeight: "700", marginTop: "4px" }}>
                  +₹{item.price} • Add +
                </span>
              )}
            </div>
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
      >
        {`Add To Cart • ₹ ${product.price * quantity}`}
      </button>

      {/* CART */}
      <CartContainer />

      {/* MEAL POPUP */}
      <MealPopup
        open={mealPopupOpen}
        meals={mealData}
        onClose={() => {
          setMealPopupOpen(false);
        }}
        onContinue={handleContinue}
      />
    </div>
  );
}

export default ProductPage;