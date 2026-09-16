import "./CartContainer.css";
import { useCart } from "../context/CartContext";
import { useNavigate } from "react-router-dom";

function CartContainer() {
  const navigate = useNavigate();

  const {
    cart,
    itemCount,
    total
  } = useCart();

  const count = Number(itemCount) || 0;
  const cartTotal = Number(total) || 0;
  const isEmpty = count === 0;

  const handleReviewPay = () => {
    if (count === 0) {
      return;
    }
    navigate("/Cart");
  };

  return (
    <div className={`cart-container ${isEmpty ? "empty" : "expanded"}`}>
      {/* ========================================= */}
      {/* TOP BAR / HEADER */}
      {/* ========================================= */}

      <div className="cart-header">
        {/* LEFT */}
        <div className="cart-left">
          <span className="cart-icon">🛒</span>
          <p className="Your-cart">Your Cart</p>
          <p className="cart-count">
            ({count} {count === 1 ? "item" : "items"})
          </p>
        </div>

        {/* WHEN EMPTY: Show inline Total & ₹ 0/- on the right in one line */}
        {isEmpty && (
          <div className="cart-inline-total">
            <span className="inline-total-label">Total</span>
            <span className="inline-total-price">₹ 0/-</span>
          </div>
        )}
      </div>


      {/* ========================================= */}
      {/* CART ITEMS (Only shown when expanded) */}
      {/* ========================================= */}

      {!isEmpty && (
        <div className="cart-items">
          {cart.map((item, index) => (
            <div key={index} className="cart-item">
              <div className="cart-item-header">
                {/* ITEM NAME */}
                <div className="cart-item-name">{item.name}</div>

                {/* QUANTITY */}
                <div className="cart-item-qty">x{item.quantity}</div>

                {/* ITEM PRICE */}
                <div className="cart-item-price">₹{item.subtotal}</div>
              </div>

              {/* MEAL DETAILS */}
              {item.type === "meal" && (
                <div className="cart-meal-items">
                  (includes {item.side?.name} + {item.drink?.name})
                </div>
              )}
            </div>
          ))}
        </div>
      )}


      {/* ========================================= */}
      {/* EMPTY CART MESSAGE */}
      {/* ========================================= */}

      {isEmpty && (
        <p className="No-items">
          NO ITEMS ADDED
        </p>
      )}


      {/* ========================================= */}
      {/* TOTAL / FOOTER (Only when expanded) */}
      {/* ========================================= */}

      {!isEmpty && (
        <div className="cart-footer">
          <p className="total-text">Total</p>
          <button
            className="review-pay-btn"
            onClick={handleReviewPay}
          >
            <span>Review & Pay</span>
            <span>₹ {cartTotal.toLocaleString("en-IN")}/-</span>
          </button>
        </div>
      )}


      {/* ========================================= */}
      {/* DIVIDER */}
      {/* ========================================= */}

      {!isEmpty && <div className="thin-line"></div>}
    </div>
  );
}

export default CartContainer;