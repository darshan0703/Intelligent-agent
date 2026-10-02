import "./Sidesrepage.css";

import { useNavigate } from "react-router-dom";

import {
  useState,
  useEffect,
  useCallback,
} from "react";

import { syncScreen } from "../services/screenService";

import Menufilters from "../components/Menufilters";

import Header from "../components/Header";

import ProductCard from "../components/ProductCard";

import CartContainer from "../components/CartContainer";

import BackButton from "../components/BackButton";

import FooterDecoration from "../components/FooterDecoration";

import fire from "../assets/images/fire.png";

import crown from "../assets/images/crown.png";

import { useKiosk } from "../context/KioskContext";

function Sides() {
  const navigate = useNavigate();

  const {
    recommendationData,
  } = useKiosk();

  const [
    selectedType,
    setSelectedType
  ] = useState("both");

  // ==========================================
  // MASTER BACKEND DATASET
  // ==========================================

  const data =
    recommendationData?.data || {};

  const allSides = {
    priority: data.priority || [],
    premium: data.premium || [],
    additional: data.additional || [],
  };

  // ==========================================
  // FILTER MASTER DATASET
  // ==========================================

  const filterProducts = useCallback(
    (products) => {

      if (selectedType === "both") {
        return products;
      }

      return products.filter(
        (product) =>
          product.foodType
            ?.toLowerCase()
            .replace("_", " ")
            .trim() === selectedType
      );
    },
    [selectedType]
  );

  // ==========================================
  // FILTERED SECTIONS
  // ==========================================

  const priorityItems =
    filterProducts(
      allSides.priority
    );

  const premiumItems =
    filterProducts(
      allSides.premium
    );

  const additionalItems =
    filterProducts(
      allSides.additional
    );

  // ==========================================
  // SCREEN SYNC
  // ==========================================

  useEffect(() => {
    syncScreen("recommended_sides");
  }, []);

  // ==========================================
  // FILTER CHANGES
  // ==========================================

  const handleFilterChange =
    useCallback((filter) => {

      const normalizedFilter =
        filter
          .trim()
          .toLowerCase()
          .replace("_", " ");

      console.log(
        "CHANGING SIDES FILTER:",
        normalizedFilter
      );

      setSelectedType(
        normalizedFilter
      );

    }, []);

  // ==========================================
  // VOICE UI ACTION LISTENER
  // ==========================================

  useEffect(() => {

    const handleVoiceUIAction = (event) => {

      const action =
        event.detail?.action;

      console.log(
        "SIDES PAGE RECEIVED UI ACTION:",
        action
      );

      if (action === "filter_veg") {

        handleFilterChange("veg");

      } else if (
        action === "filter_non_veg"
      ) {

        handleFilterChange("non veg");

      } else if (
        action === "filter_both"
      ) {

        handleFilterChange("both");

      } else if (
        action === "view_more"
      ) {

        navigate("/sidesmenu");

      } else if (
        action === "go_back"
      ) {

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

      <Header
        title="Choose Your Sides"
      />

      <BackButton />

      {/* FILTERS */}

      <div className="sides-filter-position">

        <Menufilters
          filters={[
            "both",
            "veg",
            "non veg",
          ]}
          activeFilter={
            selectedType
          }
          onFilterChange={
            handleFilterChange
          }
        />

      </div>

      {/* PRIORITY */}

      {priorityItems[0] && (

        <ProductCard
          product={
            priorityItems[0]
          }
          variant="large"
          className="card-1"
          badge="popular"
        />

      )}

      {priorityItems[1] && (

        <ProductCard
          product={
            priorityItems[1]
          }
          variant="large"
          className="card-2"
          badge="popular"
        />

      )}

      {/* PREMIUM */}

      {premiumItems[0] && (

        <ProductCard
          product={
            premiumItems[0]
          }
          variant="large"
          className="card-3"
          badge="premium"
        />

      )}

      {premiumItems[1] && (

        <ProductCard
          product={
            premiumItems[1]
          }
          variant="large"
          className="card-4"
          badge="premium"
        />

      )}

      {/* ADDITIONAL */}

      {additionalItems[0] && (

        <ProductCard
          product={
            additionalItems[0]
          }
          variant="small"
          className="card-5"
        />

      )}

      {additionalItems[1] && (

        <ProductCard
          product={
            additionalItems[1]
          }
          variant="small"
          className="card-6"
        />

      )}

      {additionalItems[2] && (

        <ProductCard
          product={
            additionalItems[2]
          }
          variant="small"
          className="card-7"
        />

      )}

      {additionalItems[3] && (

        <ProductCard
          product={
            additionalItems[3]
          }
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