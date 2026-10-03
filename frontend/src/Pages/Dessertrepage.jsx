import "./Dessertrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useNavigate } from "react-router-dom";
import { useKiosk } from "../context/KioskContext";

function Dessert() {
  const navigate = useNavigate();

  const { recommendationData } = useKiosk();

  const freshDesserts =
    recommendationData?.data?.priority || [];

  const premiumDesserts =
    recommendationData?.data?.premium || [];

  const moreDesserts =
    recommendationData?.data?.additional || [];

  return (
    <div className="dessert-page">

      {/* SECTION ICONS */}

      <img
        src={fire}
        alt="fire"
        className="fire-image"
      />

      <img
        src={crown}
        alt="crown"
        className="crown-image"
      />

      {/* HEADER */}

      <Header title="Choose Your Dessert" />

      <BackButton />

      {/* =========================
          PRIORITY DESSERTS
          ========================= */}

      {freshDesserts.slice(0, 2).map((dessert, index) => (
        <ProductCard
          key={dessert.id || `priority-${index}`}
          product={dessert}
          variant="large"
          className={`card-${index + 1}`}
          badge="popular"
        />
      ))}

      {/* =========================
          PREMIUM DESSERTS
          ========================= */}

      {premiumDesserts.slice(0, 2).map((dessert, index) => (
        <ProductCard
          key={dessert.id || `premium-${index}`}
          product={dessert}
          variant="large"
          className={`card-${index + 3}`}
          badge="premium"
        />
      ))}

      {/* =========================
          ADDITIONAL DESSERTS
          ========================= */}

      {moreDesserts.slice(0, 4).map((dessert, index) => (
        <ProductCard
          key={dessert.id || `additional-${index}`}
          product={dessert}
          variant="small"
          className={`card-${index + 5}`}
        />
      ))}

      {/* =========================
          TITLES
          ========================= */}

      <p className="fresh-text">
        Sweet Picks For You
      </p>

      <p className="fresh-text2">
        Popular & perfect for you
      </p>

      <p className="premium-text">
        Premium Desserts
      </p>

      <p className="premium-text2">
        Rich, indulgent & made to delight
      </p>

      <p className="more-text">
        More Dessert Options
      </p>

      {/* =========================
          MORE OPTIONS
          ========================= */}

      <div className="more-header">
        <button
          className="view-all-btn"
          onClick={() => navigate("/dessertmenu")}
        >
          View All Desserts →
        </button>
      </div>

      {/* CART */}

      <CartContainer />

      {/* FOOTER */}

      <FooterDecoration />

    </div>
  );
}

export default Dessert;