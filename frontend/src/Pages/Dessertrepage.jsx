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

  const { recommendationData } =
    useKiosk();

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

      {/* PRIORITY */}

      {freshDesserts[0] && (
        <ProductCard
          product={freshDesserts[0]}
          variant="large"
          className="card-1"
          badge="popular"
        />
      )}

      {freshDesserts[1] && (
        <ProductCard
          product={freshDesserts[1]}
          variant="large"
          className="card-2"
          badge="popular"
        />
      )}

      {/* PREMIUM */}

      {premiumDesserts[0] && (
        <ProductCard
          product={premiumDesserts[0]}
          variant="large"
          className="card-3"
          badge="premium"
        />
      )}

      {premiumDesserts[1] && (
        <ProductCard
          product={premiumDesserts[1]}
          variant="large"
          className="card-4"
          badge="premium"
        />
      )}

      {/* ADDITIONAL */}

      {moreDesserts[0] && (
        <ProductCard
          product={moreDesserts[0]}
          variant="small"
          className="card-5"
        />
      )}

      {moreDesserts[1] && (
        <ProductCard
          product={moreDesserts[1]}
          variant="small"
          className="card-6"
        />
      )}

      {moreDesserts[2] && (
        <ProductCard
          product={moreDesserts[2]}
          variant="small"
          className="card-7"
        />
      )}

      {moreDesserts[3] && (
        <ProductCard
          product={moreDesserts[3]}
          variant="small"
          className="card-8"
        />
      )}

      {/* TITLES */}

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

      {/* MORE OPTIONS */}

      <div className="more-header">
        <button
          className="view-all-btn"
          onClick={() =>
            navigate("/dessertmenu")
          }
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