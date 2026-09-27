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
import FooterDecoration from "../components/FooterDecoration";

<<<<<<< HEAD
import cb from "../assets/images/Container burger.png";
import cd from "../assets/images/Container drinks.png";
import cr from "../assets/images/Container recommend.png";
import cf from "../assets/images/Container fresh.png";
import co from "../assets/images/Container offers.png";
import cl from "../assets/images/Container light.png";
=======
import cb from "../assets/images/burger.png";
import cd from "../assets/images/drinks.png";
import cr from "../assets/images/recommend.png";
import cf from "../assets/images/fire.png";
import co from "../assets/images/offers.png";
import cl from "../assets/images/fresh.png";
>>>>>>> 9f50195b (WIP: recommendation progress)


/* =====================================================
   CATEGORY DATA
===================================================== */

const categoryData = [
  {
    id: "burger",
    title: "Burgers",
    subtitle: "Classic &",
    tag: "Premium",
    image: cb,
    style: {
      left: "36px",
      top: "390px",
    },
  },

  {
    id: "drink",
    title: "Drinks & Shakes",
    subtitle: "Cold drinks,",
    tag: "Shakes & more",
    image: cd,
    style: {
      left: "557px",
      top: "390px",
    },
  },

  {
    id: "dessert",
    title: "Recommend for me",
    subtitle: "AI picks for you",
    tag: "",
    image: cr,
    style: {
      left: "36px",
      top: "671px",
    },
  },

  {
    id: "side",
    title: "Today's fresh items",
    subtitle: "Signature &",
    tag: "Limited time",
    image: cf,
    style: {
      left: "557px",
      top: "671px",
    },
  },

  {
    id: "light",
    title: "Something light",
    subtitle: "Tacos, wraps &",
    tag: "lighter options",
    image: cl,
    style: {
      left: "36px",
      top: "952px",
    },
    clickable: false,
  },

  {
    id: "offers",
    title: "Offers & Combos",
    subtitle: "Best deals",
    tag: "for you",
    image: co,
    style: {
      left: "557px",
      top: "952px",
    },
    clickable: false,
  },
];


/* =====================================================
   CATEGORY CARD
===================================================== */

function CategoryCard({
  image,
  title,
  subtitle,
  tag,
  style,
  onClick,
  onArrowClick,
  clickable = true,
}) {
  return (
    <div
      className={`category-card ${
        !clickable ? "category-card-disabled" : ""
      }`}
      style={style}
      onClick={() => {
        if (clickable && onClick) {
          onClick();
        }
      }}
      role="button"
      tabIndex={clickable ? 0 : -1}
      onKeyDown={(event) => {
        if (
          (event.key === "Enter" || event.key === " ") &&
          clickable &&
          onClick
        ) {
          event.preventDefault();
          onClick();
        }
      }}
    >

      {/* IMAGE */}

      <div className="category-image-wrapper">
        <img
          src={image}
          alt={title}
          className="category-image"
        />
      </div>


      {/* TEXT */}

      <div className="category-content">

        <h3 className="category-title">
          {title}
        </h3>

        {subtitle && (
          <p className="category-subtitle">
            {subtitle}
          </p>
        )}

        {tag && (
          <p className="category-tag">
            {tag}
          </p>
        )}

      </div>


      {/* ARROW */}

      <button
        type="button"
        className="category-arrow"
        aria-label={`Open ${title}`}
        onClick={(event) => {
          event.stopPropagation();

          if (clickable && onArrowClick) {
            onArrowClick();
          }
        }}
      >
        →
      </button>

    </div>
  );
}


/* =====================================================
   CATEGORIES PAGE
===================================================== */

function Categories() {

  const navigate = useNavigate();

  const {
    setRecommendationData,
    setProductData,
  } = useKiosk();

  useCart();


  /* ==========================================
     SYNC CURRENT SCREEN
  ========================================== */

  useEffect(() => {
    syncScreen("category_selection");
  }, []);


  /* ==========================================
     CATEGORY CLICK
  ========================================== */

  const handleCategoryClick = async (category) => {
    try {

      const data = await sendMessage(
        `I want a ${category}`
      );

      console.log(
        "BACKEND RESPONSE:",
        data
      );

      handleKioskResponse(data, {
        navigate,
        setRecommendationData,
        setProductData,
      });

    } catch (error) {

      console.error(
        `${category} API Error:`,
        error
      );

    }
  };


  /* ==========================================
     ROTATING PHRASES
  ========================================== */

  const phrases = [
    '"What\'s special today?"',
    '"Add Peri Peri Fries"',
    '"Can I have a Cold Coffee?"',
  ];

  const [currentPhrase, setCurrentPhrase] =
    useState(0);


  useEffect(() => {

    const interval = setInterval(() => {

      setCurrentPhrase(
        (previous) =>
          (previous + 1) % phrases.length
      );

    }, 2000);

    return () => clearInterval(interval);

  }, []);


  /* ==========================================
     UI
  ========================================== */

  return (
    <div className="app-wrapper">

      <div className="categories-page">

        {/* HEADER */}

        <Header
          title="Welcome to Burger KING!"
        />


        {/* CATEGORY CARDS */}

        {categoryData.map((item) => (

          <CategoryCard
            key={item.id}

            image={item.image}

            title={item.title}

            subtitle={item.subtitle}

            tag={item.tag}

            style={item.style}

            clickable={
              item.clickable !== false
            }

            onClick={() =>
              handleCategoryClick(item.id)
            }

            onArrowClick={() =>
              handleCategoryClick(item.id)
            }
          />

        ))}


        {/* DIVIDER */}

        <div className="thin-line-two"></div>


        {/* PHRASES */}

        <p className="try-text">
          Try these phrases :
        </p>

        <p className="rotating-phrase">
          {phrases[currentPhrase]}
        </p>


        {/* CART */}

        <CartContainer />


        {/* FOOTER */}

        <FooterDecoration />

      </div>

    </div>
  );
}

export default Categories;