import "./Categories.css";

import {
  useEffect,
  useState,
} from "react";

import { useNavigate } from "react-router-dom";

import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";

import { sendMessage } from "../services/api";

import { handleKioskResponse } from "../services/responseHandler";

import { syncScreen } from "../services/screenService";

import Header from "../components/Header";
import CartContainer from "../components/CartContainer";

import cb from "../assets/images/container burger.png";
import cd from "../assets/images/container drinks.png";
import cr from "../assets/images/container recommend.png";
import cf from "../assets/images/container fresh.png";
import co from "../assets/images/container offers.png";
import cl from "../assets/images/container light.png";


import { getSessionId, resetSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function Categories() {

  const navigate = useNavigate();

  const {
    setRecommendationData,
    setProductData,
    resetSessionState,
  } = useKiosk();

  const {
    cart,
    itemCount,
    total,
    clearCart,
  } = useCart();

  // ==========================================
  // SYNC CURRENT SCREEN WITH BACKEND
  // ==========================================

  useEffect(() => {
    syncScreen("category_selection");
  }, []);

  // ==========================================
  // EXIT / END SESSION HANDLER
  // ==========================================

  const handleExitSession = async () => {
    try {
      const sid = getSessionId();
      await fetch(`${API_BASE_URL}/session/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid }),
      }).catch(() => {});
    } catch (err) {
      console.error("Session exit error:", err);
    } finally {
      if (clearCart) clearCart();
      if (resetSessionState) resetSessionState();
      resetSessionId();
      navigate("/");
    }
  };


  // ==========================================
  // CATEGORY CLICK
  // ==========================================

  const handleCategoryClick = async (
    category
  ) => {

    try {

      const data = await sendMessage(
        `I want a ${category}`
      );


      console.log(
        "BACKEND RESPONSE:",
        data
      );


      handleKioskResponse(
        data,
        {
          navigate,
          setRecommendationData,
          setProductData,
        }
      );

    }

    catch (error) {

      console.error(
        `${category} API Error:`,
        error
      );

    }

  };


  // ==========================================
  // ROTATING PHRASES
  // ==========================================

  const phrases = [
    "\"What's special today?\"",
    "\"Add Peri Peri Fries\"",
    "\"Can I have a Cold Coffee?\""
  ];


  const [
    currentPhrase,
    setCurrentPhrase
  ] = useState(0);


  useEffect(() => {

    const interval = setInterval(() => {

      setCurrentPhrase(
        (prev) =>
          (prev + 1) %
          phrases.length
      );

    }, 2000);


    return () =>
      clearInterval(interval);

  }, []);


  // ==========================================
  // UI
  // ==========================================

  return (

    <div className="app-wrapper">

      <div className="header-glow"></div>


      <div className="categories-page">

        <Header
          title="Welcome to Burger King"
        />

        {/* EXIT / NEW SESSION BUTTON */}
        <button
          className="exit-kiosk-btn"
          onClick={handleExitSession}
          title="End session and start over"
        >
          <span className="exit-icon">🚪</span>
          <span className="exit-text">Exit Session</span>
        </button>


        {/* BURGER */}

        <img
          src={cb}
          alt="container burger"
          className="cb-image"
          onClick={() =>
            handleCategoryClick("burger")
          }
        />


        {/* DRINKS */}

        <img
          src={cd}
          alt="container drinks"
          className="cd-image"
          onClick={() =>
            handleCategoryClick("drink")
          }
        />


        {/* DESSERT */}

        <img
          src={cr}
          alt="container recommend"
          className="cr-image"
          onClick={() =>
            handleCategoryClick("dessert")
          }
        />


        {/* SIDES */}

        <img
          src={cf}
          alt="container fresh"
          className="cf-image"
          onClick={() =>
            handleCategoryClick("side")
          }
        />


        {/* OFFERS */}

        <img
          src={co}
          alt="container offers"
          className="co-image"
        />


        {/* LIGHT */}

        <img
          src={cl}
          alt="container light"
          className="cl-image"
        />


        <div className="thin-line-two"></div>


        <div className="try-phrase-box">
          <div className="try-phrase-header">
            <span className="try-phrase-icon">🎙️</span>
            <span className="try-phrase-label">Try asking our AI Voice Cashier:</span>
          </div>
          <div className="try-phrase-badge">
            <span className="rotating-phrase">{phrases[currentPhrase]}</span>
          </div>
        </div>


        <CartContainer />

      </div>

    </div>

  );

}


export default Categories;