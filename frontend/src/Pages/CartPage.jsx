import "./CartPage.css";
import { useState, useEffect, useRef } from "react";
import { useCart } from "../context/CartContext";
import { useNavigate } from "react-router-dom";
import { syncScreen } from "../services/screenService";

import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import DeleteIcon from "../assets/images/Delete.png";
import FooterDecoration from "../components/FooterDecoration";
import { createPerfTracker, measureScreenRender } from "../services/perf";

function CartPage() {
  const { cart, displayCart, total, syncCart } = useCart();
  const navigate = useNavigate();

  const [isCartUpdating, setIsCartUpdating] = useState(false);

  const [selectedPayment, setSelectedPayment] = useState(null);
  const selectedPaymentRef = useRef(selectedPayment);
  selectedPaymentRef.current = selectedPayment;
  const isSubmittingRef = useRef(false);

  const [checkoutRecs, setCheckoutRecs] = useState([]);
  const [addedIds, setAddedIds] = useState(new Set());

  const handlePaymentSelect = (method) => {
    setSelectedPayment(method);
    selectedPaymentRef.current = method;
    syncScreen("cart", { selected_payment: method }).catch(() => {});
  };

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
    syncScreen("cart").catch((err) =>
      console.error("Failed to sync screen on CartPage:", err)
    );
    fetch("/cart")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.success) {
          syncCart(data);
        }
      })
      .catch((err) => console.error("Failed to sync cart on mount:", err));
  }, []);

  useEffect(() => {
    if (!cart || cart.length === 0 || isSubmittingRef.current) {
      setCheckoutRecs([]);
      return;
    }
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

  // Voice UI Action Listener for cart operations
  useEffect(() => {
    const findTargetItem = (val, items) => {
      if (!items || items.length === 0) return null;
      if ((!val || val === "null" || val === "none") && items.length === 1) {
        return items[0];
      }
      if (!val) return null;

      const raw = String(val).toLowerCase().trim();

      // 1. Exact match
      let match = items.find((it) => it.name.toLowerCase() === raw);
      if (match) return match;

      // 2. Substring match
      match = items.find(
        (it) =>
          it.name.toLowerCase().includes(raw) ||
          raw.includes(it.name.toLowerCase())
      );
      if (match) return match;

      // 3. Token match
      const tokens = raw.replace(/[^a-z0-9\s]/g, "").split(/\s+/).filter(Boolean);
      if (tokens.length > 0) {
        match = items.find((it) => {
          const itName = it.name.toLowerCase();
          return tokens.some((t) => t.length > 2 && itName.includes(t));
        });
        if (match) return match;
      }

      // 4. Ordinal / Index match
      const ordinals = ["first", "second", "third", "fourth", "fifth"];
      const ordIdx = ordinals.indexOf(raw);
      if (ordIdx !== -1 && ordIdx < items.length) return items[ordIdx];
      const num = parseInt(raw, 10);
      if (!isNaN(num) && num >= 1 && num <= items.length) return items[num - 1];

      return null;
    };

    const handleVoiceAction = (event) => {
      const { action, value } = event.detail || {};
      if (!action) return;

      if (action === "checkout") {
        // Direct customer to payment options without auto-completing the order
        const paymentSection = document.querySelector(".payment-section");
        paymentSection?.scrollIntoView({ behavior: "smooth" });
      } else if (action === "select_payment" || action === "payment_method") {
        const method = String(value || "").toLowerCase();
        let chosen = null;
        if (method.includes("upi")) chosen = "upi";
        else if (method.includes("card")) chosen = "card";
        else if (method.includes("cash")) chosen = "cash";
        if (chosen) {
          handlePaymentSelect(chosen);
          const paymentSection = document.querySelector(".payment-section");
          paymentSection?.scrollIntoView({ behavior: "smooth" });
        }
      } else if (action === "confirm_order") {
        handleContinue();
      } else if (action === "add_recommended") {
        if (value?.cart) {
          syncCart(value.cart);
        } else if (value) {
          const recName = typeof value === "string" ? value : value?.name;
          const matched = checkoutRecs.find(
            (r) => (r.name || "").toLowerCase() === String(recName).toLowerCase()
          );
          if (matched) {
            handleAddRecommended(matched);
          }
        }
      } else if (action === "go_back") {
        navigate("/Categories");
      } else if (["increase_quantity", "decrease_quantity", "remove_item"].includes(action)) {
        if (value?.cart) {
          syncCart(value.cart);
        } else {
          const target = findTargetItem(value, displayCart);
          if (target) {
            const act =
              action === "increase_quantity"
                ? "increase"
                : action === "decrease_quantity"
                ? "decrease"
                : "remove";
            updateItem(target._originalIndex, act);
          }
        }
      }
    };

    window.addEventListener("kiosk-ui-action", handleVoiceAction);
    return () => window.removeEventListener("kiosk-ui-action", handleVoiceAction);
  }, [displayCart, selectedPayment, checkoutRecs, navigate]);

  const handleContinue = async () => {
    const paymentToUse = selectedPaymentRef.current || selectedPayment;
    if (!paymentToUse || isSubmittingRef.current) return;
    isSubmittingRef.current = true;

    const tracker = createPerfTracker("touch");
    tracker.log("touch_action_initiated", { action: "complete_order", payment_method: paymentToUse });

    try {
      const endBackend = tracker.startStage("backend_request", { endpoint: "/order/complete" });
      const response = await fetch(
        "/order/complete",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Interaction-ID": tracker.id,
          },
        }
      );

      const data = await response.json();
      endBackend();
      tracker.log("milestone_backend_response_received", {
        duration_ms: (performance.now() - tracker.startTime).toFixed(2),
        endpoint: "/order/complete",
      });

      console.log("ORDER COMPLETE:", data);

      if (data.success) {
        if (typeof window !== "undefined") {
          const sessionStart = localStorage.getItem("session_start_perf");
          if (sessionStart) {
            const elapsed = performance.now() - parseFloat(sessionStart);
            tracker.log("milestone_order_session_completed", {
              total_duration_ms: elapsed.toFixed(2),
              total_duration_s: (elapsed / 1000).toFixed(2),
            });
          }
        }

        syncCart({
          success: true,
          cart: [],
          itemCount: 0,
          subtotal: 0,
          total: 0,
        });

        tracker.log("navigation_initiated", { destination: "/order-complete" });
        navigate("/order-complete", {
          state: {
            paymentMethod: paymentToUse,
          },
        });
        measureScreenRender(tracker, "/order-complete");

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
    } finally {
      isSubmittingRef.current = false;
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
            onClick={() => handlePaymentSelect("upi")}
          >
            <span className="payment-icon">📱</span>
            <span>UPI</span>
          </button>

          <button
            className={`payment-option ${
              selectedPayment === "card" ? "active" : ""
            }`}
            onClick={() => handlePaymentSelect("card")}
          >
            <span className="payment-icon">💳</span>
            <span>Card</span>
          </button>

          <button
            className={`payment-option ${
              selectedPayment === "cash" ? "active" : ""
            }`}
            onClick={() => handlePaymentSelect("cash")}
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