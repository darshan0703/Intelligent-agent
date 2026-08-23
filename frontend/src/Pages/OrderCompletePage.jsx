import "./OrderCompletePage.css";

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

function OrderCompletePage() {
  const navigate = useNavigate();
  const location = useLocation();

  const paymentMethod =
    location.state?.paymentMethod || "";

  // Generate a simple demo order number
  const orderNumber =
    location.state?.orderNumber ||
    Math.floor(1000 + Math.random() * 9000);

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/", { replace: true });
    }, 10000);

    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="order-complete-page">
      <div className="order-complete-content">

        <div className="success-circle">
          ✓
        </div>

        <h1>Thank You!</h1>

        <p className="order-success-message">
          Your order has been placed successfully.
        </p>

        <div className="order-number-box">
          <span>ORDER NUMBER</span>
          <strong>#{orderNumber}</strong>
        </div>

        {paymentMethod && (
          <div className="payment-method-box">
            <span>Payment Method</span>
            <strong>{paymentMethod.toUpperCase()}</strong>
          </div>
        )}

        <p className="new-order-message">
            Enjoy your meal!        </p>

      </div>
    </div>
  );
}

export default OrderCompletePage;