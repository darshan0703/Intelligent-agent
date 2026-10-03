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

import { sendMessage } from "../services/api";


function Sides() {

  const navigate = useNavigate();


  const {
    recommendationData,
    foodPreference,
    setFoodPreference,
  } = useKiosk();


  const [
    selectedType,
    setSelectedType
  ] = useState(
    foodPreference || "both"
  );


  const [
    fallbackData,
    setFallbackData
  ] = useState(null);


  // ==========================================
  // KEEP LOCAL FILTER IN SYNC
  // WITH GLOBAL FOOD PREFERENCE
  // ==========================================

  useEffect(() => {

    if (foodPreference) {

      setSelectedType(foodPreference);

    }

  }, [foodPreference]);


  // ==========================================
  // FALLBACK
  //
  // Restore recommendation data from backend
  // when page is opened directly or refreshed.
  //
  // IMPORTANT:
  //
  // The frontend does NOT create
  // recommendation tiers here.
  //
  // The backend remains responsible for:
  //
  // - priority
  // - premium
  // - additional
  // - veg
  // - non veg
  // ==========================================

  useEffect(() => {

    if (
      recommendationData?.data?.both ||
      fallbackData
    ) {
      return;
    }


    let cancelled = false;


    const restoreSideRecommendations =
      async () => {

        try {

          console.log(
            "Side recommendation data missing. Restoring..."
          );


          const data = await sendMessage(
            "I want some sides"
          );


          if (cancelled) {
            return;
          }


          console.log(
            "RESTORED SIDE RESPONSE:",
            data
          );


          setFallbackData(data);

        } catch (error) {

          if (!cancelled) {

            console.error(
              "Failed to restore side recommendations:",
              error
            );

          }

        }

      };


    restoreSideRecommendations();


    return () => {

      cancelled = true;

    };

  }, [
    recommendationData,
    fallbackData
  ]);


  // ==========================================
  // MASTER BACKEND RESPONSE
  // ==========================================

  const data =
    recommendationData?.data ||
    fallbackData?.data ||
    fallbackData ||
    {};


  // ==========================================
  // SELECT BACKEND DATASET
  //
  // Backend already creates:
  //
  // data.both
  // data.veg
  // data.non_veg
  //
  // The frontend ONLY selects which dataset
  // should be displayed.
  //
  // No filtering.
  // No slicing.
  // No recommendation generation.
  // ==========================================

  const preferenceKey =
    selectedType === "veg"
      ? "veg"
      : selectedType === "non veg"
        ? "non_veg"
        : "both";


  const selectedData =
    data[preferenceKey] ||
    data.both ||
    {};


  // ==========================================
  // SELECTED DATASET
  // ==========================================

  const priorityItems =
    selectedData.priority || [];


  const premiumItems =
    selectedData.premium || [];


  const additionalItems =
    selectedData.additional || [];


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
          .replace(/_/g, " ");


      console.log(
        "CHANGING SIDES FILTER:",
        normalizedFilter
      );


      setSelectedType(
        normalizedFilter
      );


      if (setFoodPreference) {

        setFoodPreference(
          normalizedFilter
        );

      }

    }, [
      setFoodPreference
    ]);


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


      if (
        action === "filter_veg"
      ) {

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
            navigate(
              "/sidesmenu",
              {
                state: {
                  activeFilter:
                    selectedType,
                },
              }
            )
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