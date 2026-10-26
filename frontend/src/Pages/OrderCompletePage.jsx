import "./OrderCompletePage.css";

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import FooterDecoration from "../components/FooterDecoration";
import { syncScreen } from "../services/screenService";
import { useVoiceConversation } from "../context/VoiceConversationProvider";

function OrderCompletePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { stopVoiceConversation } = useVoiceConversation();

  const paymentMethod =
    location.state?.paymentMethod || "";

  // Generate a simple demo order number
  const orderNumber =
    location.state?.orderNumber ||
    Math.floor(1000 + Math.random() * 9000);

  useEffect(() => {
    // 1. Authoritatively synchronize the kiosk screen state to order_complete
    syncScreen("order_complete").catch((err) =>
      console.error("Failed to sync screen on OrderCompletePage:", err)
    );

    // 2. Stop voice conversation so background noise is not processed
    stopVoiceConversation?.();

    // 3. Clear session timing markers and retire completed session data
    if (typeof window !== "undefined") {
      localStorage.removeItem("session_start_perf");
      localStorage.removeItem("session_id");
      sessionStorage.clear();
    }

    const timer = setTimeout(() => {
      navigate("/", { replace: true });
    }, 10000);

    return () => clearTimeout(timer);
  }, [navigate, stopVoiceConversation]);

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

      <FooterDecoration />
    </div>
  );
}

export default OrderCompletePage;