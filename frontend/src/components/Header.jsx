import "./Header.css";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";
import { useVoiceConversation } from "../context/VoiceConversationProvider";
import { stopSpeaking } from "../services/voice/ttsService";
import { clearCart as clearCartApi } from "../services/api";

import CancelOrderDialog from "./CancelOrderDialog";

import ai from "../assets/images/ai cash.png";
import logo from "../assets/images/logo.png";
import lang from "../assets/images/English.png";

function Header({ title }) {
  const location = useLocation();
  const navigate = useNavigate();

  const { clearCart } = useCart();
  const {
    setProductData,
    setMealData,
    setSelectedMeal,
    setMealPopupOpen,
    setRecommendationData,
  } = useKiosk();
  const { stopVoiceConversation } = useVoiceConversation();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);

  // Normalize path and hide on "/" (Home), "/categories", and "/order-complete"
  const pathname = (location?.pathname || "").toLowerCase().replace(/\/$/, "") || "/";
  const isExcluded =
    pathname === "/" ||
    pathname === "/categories" ||
    pathname === "/order-complete";
  const showCancelButton = !isExcluded;

  const handleOpenDialog = () => {
    setIsDialogOpen(true);
  };

  const handleKeepOrdering = () => {
    setIsDialogOpen(false);
  };

  const handleConfirmCancel = async () => {
    if (isCanceling) return;
    setIsCanceling(true);

    try {
      // 1. Clear cart state in CartContext
      if (clearCart) {
        clearCart();
      }

      // 2. Reset KioskContext state setters
      if (setProductData) setProductData(null);
      if (setMealData) setMealData(null);
      if (setSelectedMeal) setSelectedMeal(null);
      if (setMealPopupOpen) setMealPopupOpen(false);
      if (setRecommendationData) setRecommendationData(null);

      // 3. Stop voice conversation and speech
      if (stopVoiceConversation) {
        stopVoiceConversation();
      }
      stopSpeaking();

      // 4. Clear backend cart session if API available
      try {
        await clearCartApi();
      } catch (apiErr) {
        console.warn("Backend cart clear request failed or not needed:", apiErr);
      }

      // 5. Close dialog and navigate to Welcome/Start page ("/")
      setIsDialogOpen(false);
      navigate("/", { replace: true });
    } catch (err) {
      console.error("Cancellation error:", err);
    } finally {
      setIsCanceling(false);
    }
  };

  return (
    <div className="header-container">

      {/* ==========================================
          ORANGE HEADER BACKGROUND
          ========================================== */}
      <div className="header-orange-bg">
        <div className="orange-oval oval-left"></div>
        <div className="orange-oval oval-right"></div>
      </div>

      {/* ==========================================
          AI
          ========================================== */}
      <img
        src={ai}
        alt="ai"
        className="ai-image"
      />

      {/* ==========================================
          LOGO
          ========================================== */}
      <img
        src={logo}
        alt="logo"
        className="logo-image"
      />

      {/* ==========================================
          LANGUAGE
          ========================================== */}
      <img
        src={lang}
        alt="lang"
        className="lang-image"
      />

      {/* ==========================================
          TITLE
          ========================================== */}
      <h1 className="page-title">
        {title}
      </h1>

      {/* ==========================================
          WAVE
          ========================================== */}
      <div className="wave-container">
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
        <div className="bar"></div>
      </div>

      {/* ==========================================
          LISTENING
          ========================================== */}
      <p className="listening-text">
        Listening<span className="dots"></span>
      </p>

      {/* ==========================================
          CANCEL ORDER BUTTON
          ========================================== */}
      {showCancelButton && (
        <button
          type="button"
          className="cancel-order-header-btn"
          onClick={handleOpenDialog}
          aria-label="Cancel this order"
        >
          <span className="cancel-icon" aria-hidden="true">×</span>
          <span className="cancel-text">Cancel order</span>
        </button>
      )}

      {/* ==========================================
          LINE
          ========================================== */}
      <div className="thin-line"></div>

      {/* ==========================================
          CANCEL ORDER CONFIRMATION DIALOG
          ========================================== */}
      <CancelOrderDialog
        isOpen={isDialogOpen}
        onKeepOrdering={handleKeepOrdering}
        onConfirmCancel={handleConfirmCancel}
        isCanceling={isCanceling}
      />

    </div>
  );
}

export default Header;