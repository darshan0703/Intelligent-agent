import "./Drinkrepage.css";

import { useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";
import Menufilters from "../components/Menufilters";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useKiosk } from "../context/KioskContext";

function Drink() {
  const navigate = useNavigate();

  const { recommendationData } = useKiosk();

  const [selectedType, setSelectedType] =
    useState("both");

  const data =
    recommendationData?.data || {};

  const allDrinks = {
    priority: data.priority || [],
    premium: data.premium || [],
    additional: data.additional || [],
  };

  const filterProducts = useCallback(
    (products) => {
      if (selectedType === "both") {
        return products;
      }

      return products.filter(
        (product) =>
          product.type?.toLowerCase() ===
          selectedType
      );
    },
    [selectedType]
  );

  const freshDrinks =
    filterProducts(allDrinks.priority);

  const premiumDrinks =
    filterProducts(allDrinks.premium);

  const moreDrinks =
    filterProducts(allDrinks.additional);

  const handleFilterChange =
    useCallback((filter) => {
      const normalizedFilter =
        filter.trim().toLowerCase();

      console.log(
        "CHANGING DRINK FILTER:",
        normalizedFilter
      );

      setSelectedType(
        normalizedFilter
      );
    }, []);

  useEffect(() => {
    const handleVoiceUIAction = (event) => {
      const action =
        event.detail?.action;

      console.log(
        "DRINK PAGE RECEIVED UI ACTION:",
        action
      );

      if (action === "filter_cold") {
        handleFilterChange("cold");
      }

      else if (action === "filter_hot") {
        handleFilterChange("hot");
      }

      else if (action === "filter_both") {
        handleFilterChange("both");
      }

      else if (action === "view_more") {
        navigate("/drinkmenu");
      }

      else if (action === "go_back") {
        navigate(-1);
      }
    };

    window.addEventListener(
      "kiosk-ui-action",
      handleVoiceUIAction
    );

    return () => {
      window.removeEventListener(
        "kiosk-ui-action",
        handleVoiceUIAction
      );
    };
  }, [
    handleFilterChange,
    navigate
  ]);

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

      {/* FILTERS */}

      <div className="drink-filter-position">
        <Menufilters
          filters={[
            "both",
            "cold",
            "hot"
          ]}
          activeFilter={selectedType}
          onFilterChange={
            handleFilterChange
          }
        />
      </div>

      {/* PRIORITY */}

      {freshDrinks[0] && (
        <ProductCard
          product={freshDrinks[0]}
          variant="large"
          className="card-1"
          badge="popular"
        />
      )}

      {freshDrinks[1] && (
        <ProductCard
          product={freshDrinks[1]}
          variant="large"
          className="card-2"
          badge="popular"
        />
      )}

      {/* PREMIUM */}

      {premiumDrinks[0] && (
        <ProductCard
          product={premiumDrinks[0]}
          variant="large"
          className="card-3"
          badge="premium"
        />
      )}

      {premiumDrinks[1] && (
        <ProductCard
          product={premiumDrinks[1]}
          variant="large"
          className="card-4"
          badge="premium"
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

      <p className="premium-text">
        Premium Beverages
      </p>

      <p className="premium-text2">
        Indulge in our most loved shakes & drinks
      </p>

      {/* MORE OPTIONS */}

      <div className="more-header">
        <p className="more-text">
          More Drink Options
        </p>

        <button
          className="view-all-btn"
          onClick={() =>
            navigate("/drinkmenu")
          }
        >
          View All Drinks →
        </button>
      </div>

      {/* CART */}

      <CartContainer />

      {/* FOOTER */}

      <FooterDecoration />

    </div>
  );
}

export default Drink;