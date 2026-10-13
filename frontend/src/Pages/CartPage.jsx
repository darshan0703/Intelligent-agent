import "./CartPage.css";
import { useState, useEffect } from "react";
import { useCart } from "../context/CartContext";
import { useNavigate } from "react-router-dom";

import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import DeleteIcon from "../assets/images/Delete.png";
import FooterDecoration from "../components/FooterDecoration";

function CartPage() {
  const { cart, displayCart, total, syncCart } = useCart();
  const navigate = useNavigate();

  const [isCartUpdating, setIsCartUpdating] = useState(false);

  const [selectedPayment, setSelectedPayment] = useState(null);
  const [checkoutRecs, setCheckoutRecs] = useState([]);
  const [addedIds, setAddedIds] = useState(new Set());

  const resolveImageUrl = (img) => {
    if (!img) return "";
    if (img.startsWith("http://") || img.startsWith("https://") || img.startsWith("/")) {
      return img;
    }
    return `/${img}`;
  };

  // Load dynamic checkout recommendations matching original MLE design
  const loadCheckoutRecommendations = async () => {
    try {
      const res = await fetch("/recommendations/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart_lines: cart }),
      });
      const data = await res.json();
      if (data?.success && data?.recommendations) {
        setCheckoutRecs(data.recommendations);
      } else if (data?.suggestions) {
        setCheckoutRecs(data.suggestions);
      } else {
        setCheckoutRecs([]);
      }
    } catch (err) {
      console.warn("Failed to load checkout recommendations via POST, trying GET:", err);
      try {
        const res = await fetch("/recommendations/checkout");
        const data = await res.json();
        if (data?.success && data?.recommendations) {
          setCheckoutRecs(data.recommendations);
        } else if (data?.suggestions) {
          setCheckoutRecs(data.suggestions);
        }
      } catch (e) {
        console.warn("Checkout recommendations fetch failed:", e);
      }
    }
  };

  const getContextualBadge = (item) => {
    if (!item) return null;
    const cat = (item.category || "").toLowerCase();
    const name = (item.name || "").toLowerCase();
    const rawBadge = (item.badge || "").toLowerCase();

    // Dips and sauces
    if (
      cat === "dip" ||
      cat === "sauce" ||
      rawBadge.includes("dip") ||
      rawBadge.includes("sauce") ||
      name.includes("dip") ||
      name.includes("sauce")
    ) {
      return "Perfect Pairing";
    }

    // Drinks
    if (
      cat === "drink" ||
      cat === "beverage" ||
      rawBadge.includes("drink") ||
      name.includes("shake") ||
      name.includes("smoothie") ||
      name.includes("frappe") ||
      name.includes("coke") ||
      name.includes("sprite") ||
      name.includes("latte") ||
      name.includes("cappuccino")
    ) {
      return "Great With Your Meal";
    }

    // Desserts
    if (
      cat === "dessert" ||
      rawBadge.includes("sweet") ||
      rawBadge.includes("treat") ||
      name.includes("sundae") ||
      name.includes("ice cream") ||
      name.includes("pie") ||
      name.includes("cake") ||
      name.includes("cookie") ||
      name.includes("brownie")
    ) {
      return "Sweet Finish";
    }

    return null;
  };

  useEffect(() => {
    loadCheckoutRecommendations();
  }, [cart]);

  const handleAddRecommended = async (item) => {
    try {
      setAddedIds((prev) => new Set(prev).add(item.id));
      const res = await fetch("/cart/add", {
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
    if (isCartUpdating) return;
    setIsCartUpdating(true);
    try {
      const response = await fetch(
        "/cart/item",
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            item_index: itemIndex,
            action,
          }),
        }
      );

      const data = await response.json();

      console.log("CART UPDATE:", data);

      if (data.success) {
        syncCart(data);
      }
    } catch (error) {
      console.error("Failed to update cart:", error);
    } finally {
      setIsCartUpdating(false);
    }
  };

 const handleContinue = async () => {
  if (!selectedPayment) return;

  try {
    const response = await fetch(
      "/order/complete",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    const data = await response.json();

    console.log("ORDER COMPLETE:", data);

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

      alert(
        data.message || "Unable to complete order."
      );

    }

  } catch (error) {

    console.error(
      "Failed to complete order:",
      error
    );

    alert("Something went wrong while completing the order.");

  }
};
  return (
    <div className="cart-page">
      <Header title="Review Your Order" />
      <PreviousButton />

      <div className="cart-page-items">
        {displayCart.map((item) => (
          <div className="cart-page-item" key={item._uniqueKey}>
            <div className="cart-page-item-info">
              <h2>{item.name}</h2>

              {item.type === "meal" && (
                <p>
                  Includes {item.side?.name} + {item.drink?.name}
                </p>
              )}
            </div>

            <div className="cart-page-item-quantity">
              <button
                disabled={isCartUpdating}
                style={isCartUpdating ? { opacity: 0.6, cursor: "not-allowed" } : undefined}
                onClick={() => updateItem(item._originalIndex, "decrease")}
              >
                −
              </button>

              <span>{item.quantity}</span>

              <button
                disabled={isCartUpdating}
                style={isCartUpdating ? { opacity: 0.6, cursor: "not-allowed" } : undefined}
                onClick={() => updateItem(item._originalIndex, "increase")}
              >
                +
              </button>
            </div>

            <div className="cart-page-item-price">
              ₹{item.subtotal}
            </div>

            <button
              className="cart-page-remove"
              disabled={isCartUpdating}
              style={isCartUpdating ? { opacity: 0.6, cursor: "not-allowed" } : undefined}
              onClick={() => updateItem(item._originalIndex, "remove")}
            >
              <img src={DeleteIcon} alt="Remove" />
            </button>
          </div>
        ))}
      </div>

      {/* PRE-CHECKOUT / REVIEW RECOMMENDATIONS SHELF (Matching original MLE git branch) */}
      {checkoutRecs.length > 0 && (
        <div className="cart-recommendations-container">
          <div className="cart-rec-header">
            <h3>Pairs Well With Your Order</h3>
            <span className="cart-rec-sub">Complete your day with some customer favorites</span>
          </div>
          <div className="cart-rec-grid">
            {checkoutRecs.map((item) => {
              const displayBadge = item.badge || getContextualBadge(item) || "⭐ Best Match";
              return (
                <div key={item.id} className="cart-rec-card">
                  <button
                    type="button"
                    title="Dismiss"
                    className="cart-rec-dismiss-btn"
                    onClick={() => setCheckoutRecs((prev) => prev.filter((r) => r.id !== item.id))}
                  >
                    ✕
                  </button>
                  <img
                    src={resolveImageUrl(item.image)}
                    alt={item.name}
                    className="cart-rec-image"
                    onError={(e) => {
                      e.currentTarget.style.opacity = "0.3";
                    }}
                  />
                  <div className="cart-rec-details">
                    {displayBadge && <span className="cart-rec-badge">{displayBadge}</span>}
                    <span className="cart-rec-title" title={item.name}>{item.name}</span>
                    <div className="cart-rec-bottom-row">
                      <span className="cart-rec-cost">₹{item.price}</span>
                      <button
                        className={`cart-rec-add-btn ${addedIds.has(item.id) ? "added" : ""}`}
                        onClick={() => handleAddRecommended(item)}
                      >
                        {addedIds.has(item.id) ? "✓ Added" : "+ Add"}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
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