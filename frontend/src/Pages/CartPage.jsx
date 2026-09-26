import "./CartPage.css";
import { useState, useEffect } from "react";
import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";
import { useNavigate } from "react-router-dom";

import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import DeleteIcon from "../assets/images/Delete.png";
import FooterDecoration from "../components/FooterDecoration";
import { getCategoryFallbackImage } from "../utils/imageFallback";
import { getSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function CartPage() {
  const { cart, total, syncCart } = useCart();
  const {
    sessionContext,
    setActiveScalarAffinity,
    rejectCategory,
    rejectSubRole,
    unrejectSubRole,
    setVelocityState,
    foodPreference,
  } = useKiosk();
  const navigate = useNavigate();

  const [selectedPayment, setSelectedPayment] = useState(null);
  const [checkoutRecs, setCheckoutRecs] = useState([]);
  const [addedIds, setAddedIds] = useState(new Set());

  // Auto-detect bulk rush if quantity >= 5 of any item
  useEffect(() => {
    if (cart && cart.some((it) => it.quantity >= 5)) {
      setVelocityState("rushed");
    }
  }, [cart, setVelocityState]);

  // Load dynamic checkout recommendations
  const loadCheckoutRecommendations = async () => {
    try {
      const sid = getSessionId();
      const ctx = {
        ...(sessionContext || {
          active_affinities: [],
          rejected_categories: [],
          active_affinity: {},
          rejected_sub_roles: [],
          velocity_state: null,
        }),
        preference: foodPreference && foodPreference !== "both" ? foodPreference : null,
      };
      const res = await fetch(`${API_BASE_URL}/recommendations/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sid,
          cart_lines: cart || [],
          session_context: ctx,
        }),
      });
      const data = await res.json();
      if (data.success && data.recommendations) {
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
        setCheckoutRecs(recs);
      } else {
        setCheckoutRecs([]);
      }
    } catch (err) {
      console.warn("Failed to load checkout recommendations:", err);
    }
  };

  useEffect(() => {
    loadCheckoutRecommendations();
  }, [cart, sessionContext, foodPreference]);

  const handleAddRecommended = async (item) => {
    try {
      setAddedIds((prev) => new Set(prev).add(item.id));
      const res = await fetch(`${API_BASE_URL}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_name: item.name,
          quantity: 1,
        }),
      });
      const data = await res.json();
      if (data.success) {
        syncCart(data);
      }
    } catch (err) {
      console.error("Failed to add recommended item to cart:", err);
    }
  };

  const updateItem = async (itemIndex, action) => {
    try {
      const response = await fetch(`${API_BASE_URL}/cart/item`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_index: itemIndex,
          action,
        }),
      });

      const data = await response.json();
      if (data.success) {
        syncCart(data);
      }
    } catch (error) {
      console.error("Failed to update cart:", error);
    }
  };

  const handleContinue = async () => {
    if (!selectedPayment) return;

    try {
      const response = await fetch(`${API_BASE_URL}/order/complete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const data = await response.json();
      if (data.success) {
        syncCart({
          success: true,
          cart: [],
          itemCount: 0,
          subtotal: 0,
          total: 0,
        });

        navigate("/order-complete", {
          state: {
            paymentMethod: selectedPayment,
          },
        });
      } else {
        alert(data.message || "Unable to complete order.");
      }
    } catch (error) {
      console.error("Failed to complete order:", error);
      alert("Something went wrong while completing the order.");
    }
  };

  return (
    <div className="cart-page">
      <Header title="Review Your Order" />
      <PreviousButton />

      <div className="cart-page-items">
        {cart.map((item, index) => (
          <div className="cart-page-item" key={index}>
            <div className="cart-page-item-info">
              <h2>{item.name}</h2>
              {item.type === "meal" && (
                <p>
                  Includes {item.side?.name} + {item.drink?.name}
                </p>
              )}
            </div>

            <div className="cart-page-item-quantity">
              <button onClick={() => updateItem(index, "decrease")}>−</button>
              <span>{item.quantity}</span>
              <button onClick={() => updateItem(index, "increase")}>+</button>
            </div>

            <div className="cart-page-item-price">₹{item.subtotal}</div>

            <button
              className="cart-page-remove"
              onClick={() => updateItem(index, "remove")}
            >
              <img src={DeleteIcon} alt="Remove" />
            </button>
          </div>
        ))}
      </div>

      {/* PRE-CHECKOUT / REVIEW RECOMMENDATIONS SHELF */}
      {checkoutRecs.length > 0 && (
        <div className="cart-recommendations-container">
          <div className="cart-rec-header">
            <div>
              <h3>Pairs Well With Your Order</h3>
              <span className="cart-rec-sub">Complete your tray with customer favourites</span>
            </div>
          </div>
          <div className="cart-rec-grid">
            {checkoutRecs.map((item) => (
              <div key={item.id} className="cart-rec-card">
                <img
                  src={item.image}
                  alt={item.name}
                  className="cart-rec-image"
                  onError={(e) => {
                    e.currentTarget.onerror = null;
                    e.currentTarget.src = getCategoryFallbackImage(item.category, item.name);
                  }}
                />
                <div className="cart-rec-details">
                  <span className="cart-rec-badge">{item.badge || "⭐ Best Match"}</span>
                  <span className="cart-rec-title" title={item.name}>{item.name}</span>
                  <span className="cart-rec-cost">₹{item.price}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <button
                    className={`cart-rec-add-btn ${addedIds.has(item.id) ? "added" : ""}`}
                    onClick={() => handleAddRecommended(item)}
                  >
                    {addedIds.has(item.id) ? "✓ Added" : "+ Add"}
                  </button>
                  <button
                    type="button"
                    title={`Not interested in ${item.category}s`}
                    style={{
                      border: "none",
                      background: "transparent",
                      color: "#999",
                      cursor: "pointer",
                      fontSize: "14px",
                      padding: "2px 6px",
                      borderRadius: "50%",
                    }}
                    onClick={() => rejectCategory(item.category)}
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="cart-page-total">
        <span>Total</span>
        <span>₹ {total}/-</span>
      </div>

      <div className="payment-section">
        <h2>Choose Payment Method</h2>

        <div className="payment-options">
          <button
            className={`payment-option ${
              selectedPayment === "upi" ? "active" : ""
            }`}
            onClick={() => setSelectedPayment("upi")}
          >
            <span className="payment-icon">📱</span>
            <span>UPI</span>
          </button>

          <button
            className={`payment-option ${
              selectedPayment === "card" ? "active" : ""
            }`}
            onClick={() => setSelectedPayment("card")}
          >
            <span className="payment-icon">💳</span>
            <span>Card</span>
          </button>

          <button
            className={`payment-option ${
              selectedPayment === "cash" ? "active" : ""
            }`}
            onClick={() => setSelectedPayment("cash")}
          >
            <span className="payment-icon">💵</span>
            <span>Cash</span>
          </button>
        </div>

        <button
          className={`continue-payment-btn ${
            !selectedPayment ? "disabled" : ""
          }`}
          disabled={!selectedPayment}
          onClick={handleContinue}
        >
          Continue
        </button>
      </div>

      <FooterDecoration />
    </div>
  );
}

export default CartPage;