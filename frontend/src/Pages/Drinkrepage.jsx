import "./Drinkrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useNavigate } from "react-router-dom";
import { useKiosk } from "../context/KioskContext";

function Drink() {
  const navigate = useNavigate();

  const { recommendationData } = useKiosk();

  const freshDrinks = recommendationData?.data?.priority || [];
  const premiumDrinks = recommendationData?.data?.premium || [];
  const moreDrinks = recommendationData?.data?.additional || [];

  return (
    <div className="drink-page">

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
      <Header title="Choose Your Drink" />

      <BackButton />

      {/* PRIORITY */}

      {freshDrinks[0] && (
        <ProductCard
          product={freshDrinks[0]}
          variant="large"
          className="card-1"
        />
      )}

      {freshDrinks[1] && (
        <ProductCard
          product={freshDrinks[1]}
          variant="large"
          className="card-2"
        />
      )}

      {/* PREMIUM */}

      {premiumDrinks[0] && (
        <ProductCard
          product={premiumDrinks[0]}
          variant="large"
          className="card-3"
        />
      )}

      {premiumDrinks[1] && (
        <ProductCard
          product={premiumDrinks[1]}
          variant="large"
          className="card-4"
        />
      )}

      {/* ADDITIONAL */}

      {moreDrinks[0] && (
        <ProductCard
          product={moreDrinks[0]}
          variant="small"
          className="card-5"
        />
      )}

      {moreDrinks[1] && (
        <ProductCard
          product={moreDrinks[1]}
          variant="small"
          className="card-6"
        />
      )}

      {moreDrinks[2] && (
        <ProductCard
          product={moreDrinks[2]}
          variant="small"
          className="card-7"
        />
      )}

      {moreDrinks[3] && (
        <ProductCard
          product={moreDrinks[3]}
          variant="small"
          className="card-8"
        />
      )}

      {/* TITLES */}

      <p className="fresh-text">
        Freshly Made Drinks
      </p>

      <p className="fresh-text2">
        Popular & perfect right now
      </p>

      <div className="thin-line-2"></div>

      <p className="premium-text">
        Premium Beverages
      </p>

      <p className="premium-text2">
        Indulge in our most loved shakes & drinks
      </p>

      <div className="thin-line-3"></div>

      <p className="more-text">
        More Drink Options
      </p>

      <div className="more-header">
        <button
          className="view-all-btn"
          onClick={() => navigate("/drinkmenu")}
        >
          View All →
        </button>
      </div>

      <CartContainer />

    </div>
  );
}

export default Drink;