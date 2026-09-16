import "./CartPage.css";
import { useState } from "react";
import { useCart } from "../context/CartContext";
import { useNavigate } from "react-router-dom";

import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import DeleteIcon from "../assets/images/Delete.png";

function CartPage() {
  const { cart, total, syncCart } = useCart();
  const navigate = useNavigate();

  const [selectedPayment, setSelectedPayment] = useState(null);

  const updateItem = async (itemIndex, action) => {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/cart/item",
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
    }
  };

 const handleContinue = async () => {
  if (!selectedPayment) return;

  try {
    const response = await fetch(
      "http://127.0.0.1:8000/order/complete",
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
              <button
                onClick={() => updateItem(index, "decrease")}
              >
                −
              </button>

              <span>{item.quantity}</span>

              <button
                onClick={() => updateItem(index, "increase")}
              >
                +
              </button>
            </div>

            <div className="cart-page-item-price">
              ₹{item.subtotal}
            </div>

            <button
              className="cart-page-remove"
              onClick={() => updateItem(index, "remove")}
            >
              <img src={DeleteIcon} alt="Remove" />
            </button>
          </div>
        ))}
      </div>

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
    </div>
  );
}

export default CartPage;