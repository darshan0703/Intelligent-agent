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


function Categories() {

  const navigate = useNavigate();


  const {
    setRecommendationData,
    setProductData,
  } = useKiosk();


  const {
    cart,
    itemCount,
    total,
  } = useCart();


  // ==========================================
  // SYNC CURRENT SCREEN WITH BACKEND
  // ==========================================

  useEffect(() => {

    syncScreen(
      "category_selection"
    );

  }, []);


  // ==========================================
  // CATEGORY CLICK
  // ==========================================

  const handleCategoryClick = async (
    category
  ) => {

    try {

      console.log(
        `${category.toUpperCase()} CLICKED`
      );


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
          title="Welcome to Burger KING!"
        />


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


        <p className="try-text">
          Try these phrases :
        </p>


        <p className="rotating-phrase">
          {phrases[currentPhrase]}
        </p>


        <CartContainer />

      </div>

    </div>

  );

}


export default Categories;