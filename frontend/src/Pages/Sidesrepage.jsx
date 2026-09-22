import "./Sidesrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useNavigate } from "react-router-dom";
import { useKiosk } from "../context/KioskContext";

function Sides() {
  const navigate = useNavigate();

  const { recommendationData } =
    useKiosk();

  const hotSides =
    recommendationData?.data?.priority || [];

  const premiumSides =
    recommendationData?.data?.premium || [];

  const moreSides =
    recommendationData?.data?.additional || [];

  return (
    <div className="sides-page">

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

      <Header title="Choose Your Sides" />

      <BackButton />

      {/* PRIORITY */}

      {hotSides[0] && (
        <ProductCard
          product={hotSides[0]}
          variant="large"
          className="card-1"
          badge="popular"
        />
      )}

      {hotSides[1] && (
        <ProductCard
          product={hotSides[1]}
          variant="large"
          className="card-2"
          badge="popular"
        />
      )}

      {/* PREMIUM */}

      {premiumSides[0] && (
        <ProductCard
          product={premiumSides[0]}
          variant="large"
          className="card-3"
          badge="premium"
        />
      )}

      {premiumSides[1] && (
        <ProductCard
          product={premiumSides[1]}
          variant="large"
          className="card-4"
          badge="premium"
        />
      )}

      {/* ADDITIONAL */}

      {moreSides[0] && (
        <ProductCard
          product={moreSides[0]}
          variant="small"
          className="card-5"
        />
      )}

      {moreSides[1] && (
        <ProductCard
          product={moreSides[1]}
          variant="small"
          className="card-6"
        />
      )}

      {moreSides[2] && (
        <ProductCard
          product={moreSides[2]}
          variant="small"
          className="card-7"
        />
      )}

      {moreSides[3] && (
        <ProductCard
          product={moreSides[3]}
          variant="small"
          className="card-8"
        />
      )}

      {/* TITLES */}

      <p className="fresh-text">
        Hot & Crispy Picks
      </p>

      <p className="fresh-text2">
        Freshly prepared favorites
      </p>

      <p className="premium-text">
        Premium Sides
      </p>

      <p className="premium-text2">
        Perfect add-ons for every meal
      </p>

      {/* MORE OPTIONS */}

      <div className="more-header">
        <p className="more-text">
          More Side Options
        </p>

        <button
          className="view-all-btn"
          onClick={() =>
            navigate("/sidesmenu")
          }
        >
          View All Sides →
        </button>
      </div>

      {/* CART */}

      <CartContainer />

      {/* FOOTER */}

      <FooterDecoration />

    </div>
  );
}

export default Sides;