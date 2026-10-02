import "./Burgerrepage.css";

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

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";

import { useKiosk } from "../context/KioskContext";


function Burger() {

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
  // NORMALIZE FOOD PREFERENCE
  // ==========================================

  const normalizePreference = useCallback(
    (value) => {

      return String(value || "both")
        .toLowerCase()
        .replace(/_/g, " ")
        .trim();

    },
    []
  );


  // ==========================================
  // KEEP LOCAL FILTER IN SYNC
  // WITH GLOBAL FOOD PREFERENCE
  // ==========================================

  useEffect(() => {

    if (foodPreference) {

      setSelectedType(
        normalizePreference(foodPreference)
      );

    }

  }, [
    foodPreference,
    normalizePreference
  ]);


  // ==========================================
  // FALLBACK
  //
  // Only used when the page is opened directly
  // without recommendation data.
  // ==========================================

  useEffect(() => {

    if (
      recommendationData?.data?.both ||
      fallbackData
    ) {
      return;
    }


    fetch("/menu/burgers")

      .then((res) => res.json())

      .then((sections) => {

        const all = sections.flatMap(
          (section) =>
            section.products || []
        );


        const veg = all.filter(
          (product) => {

            const type = String(
              product.type ||
              product.foodType ||
              ""
            )
              .toLowerCase()
              .replace(/_/g, " ")
              .trim();

            return type === "veg";
          }
        );


        const nonVeg = all.filter(
          (product) => {

            const type = String(
              product.type ||
              product.foodType ||
              ""
            )
              .toLowerCase()
              .replace(/_/g, " ")
              .trim();

            return type === "non veg";
          }
        );


        setFallbackData({

          both: {
            priority: all.slice(0, 2),
            premium: all.slice(2, 4),
            additional: all.slice(4, 8),
          },

          veg: {
            priority: veg.slice(0, 2),
            premium: veg.slice(2, 4),
            additional: veg.slice(4, 8),
          },

          non_veg: {
            priority: nonVeg.slice(0, 2),
            premium: nonVeg.slice(2, 4),
            additional: nonVeg.slice(4, 8),
          },

        });

      })

      .catch((error) => {

        console.warn(
          "Fallback burger fetch failed:",
          error
        );

      });

  }, [
    recommendationData,
    fallbackData
  ]);


  // ==========================================
  // MASTER BACKEND RESPONSE
  // ==========================================

  const backendData =
    recommendationData?.data ||
    fallbackData ||
    {};


  // ==========================================
  // SELECT BACKEND DATASET
  //
  // IMPORTANT:
  //
  // We DO NOT filter products locally anymore.
  //
  // Backend already created:
  //
  // data.both
  // data.veg
  // data.non_veg
  //
  // ==========================================

  const preferenceKey =
    selectedType === "veg"
      ? "veg"
      : selectedType === "non veg"
        ? "non_veg"
        : "both";


  const selectedData =
    backendData[preferenceKey] ||
    backendData.both ||
    fallbackData?.[preferenceKey] ||
    fallbackData?.both ||
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
  // DEBUG
  // ==========================================

  console.log(
    "=========================================="
  );

  console.log(
    "BURGER SELECTED TYPE:",
    selectedType
  );

  console.log(
    "BURGER DATASET KEY:",
    preferenceKey
  );

  console.log(
    "BURGER SELECTED DATA:",
    selectedData
  );

  console.log(
    "BURGER PRIORITY:",
    priorityItems
  );

  console.log(
    "BURGER PREMIUM:",
    premiumItems
  );

  console.log(
    "BURGER ADDITIONAL:",
    additionalItems
  );

  console.log(
    "=========================================="
  );


  // ==========================================
  // SCREEN SYNC
  // ==========================================

  useEffect(() => {

    syncScreen(
      "recommended_burgers"
    );

  }, []);


  // ==========================================
  // FILTER CHANGE
  // ==========================================

  const handleFilterChange = useCallback(
    (filter) => {

      const normalizedFilter =
        normalizePreference(filter);


      console.log(
        "CHANGING BURGER FILTER:",
        normalizedFilter
      );


      setSelectedType(
        normalizedFilter
      );


      // Keep global preference synchronized.
      if (setFoodPreference) {

        setFoodPreference(
          normalizedFilter
        );

      }

    },
    [
      normalizePreference,
      setFoodPreference
    ]
  );


  // ==========================================
  // VOICE UI ACTION LISTENER
  // ==========================================

  useEffect(() => {

    const handleVoiceUIAction =
      (event) => {

        const action =
          event.detail?.action;


        console.log(
          "BURGER PAGE RECEIVED UI ACTION:",
          action
        );


        if (
          action === "filter_veg"
        ) {

          handleFilterChange(
            "veg"
          );

        }

        else if (
          action === "filter_non_veg"
        ) {

          handleFilterChange(
            "non veg"
          );

        }

        else if (
          action === "filter_both"
        ) {

          handleFilterChange(
            "both"
          );

        }

        else if (
          action === "view_more"
        ) {

          navigate(
            "/burgermenu"
          );

        }

        else if (
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

    <div className="burger-page">

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
        title="Choose Your Burger"
      />


      <BackButton />


      {/* FILTERS */}

      <div className="burger-filter-position">

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


      {/* ==================================
          PRIORITY
          ================================== */}

      {
        priorityItems[0] && (

          <ProductCard
            product={
              priorityItems[0]
            }
            variant="large"
            className="card-1"
            badge="popular"
          />

        )
      }


      {
        priorityItems[1] && (

          <ProductCard
            product={
              priorityItems[1]
            }
            variant="large"
            className="card-2"
            badge="popular"
          />

        )
      }


      {/* ==================================
          PREMIUM
          ================================== */}

      {
        premiumItems[0] && (

          <ProductCard
            product={
              premiumItems[0]
            }
            variant="large"
            className="card-3"
            badge="premium"
          />

        )
      }


      {
        premiumItems[1] && (

          <ProductCard
            product={
              premiumItems[1]
            }
            variant="large"
            className="card-4"
            badge="premium"
          />

        )
      }


      {/* ==================================
          ADDITIONAL
          ================================== */}

      {
        additionalItems[0] && (

          <ProductCard
            product={
              additionalItems[0]
            }
            variant="small"
            className="card-5"
          />

        )
      }


      {
        additionalItems[1] && (

          <ProductCard
            product={
              additionalItems[1]
            }
            variant="small"
            className="card-6"
          />

        )
      }


      {
        additionalItems[2] && (

          <ProductCard
            product={
              additionalItems[2]
            }
            variant="small"
            className="card-7"
          />

        )
      }


      {
        additionalItems[3] && (

          <ProductCard
            product={
              additionalItems[3]
            }
            variant="small"
            className="card-8"
          />

        )
      }


      {/* ==================================
          RECOMMENDED SECTION
          ================================== */}

      <p className="Recommendation-text">
        Fresh Picks For You
      </p>

      <p className="Recommendation-text2">
        Recommended based on availability
      </p>


      {/* ==================================
          PREMIUM SECTION
          ================================== */}

      <p className="Premium-text">
        Premium Collection
      </p>

      <p className="Premium-text2">
        Handpicked just for you
      </p>


      {/* ==================================
          MORE OPTIONS
          ================================== */}

      <div className="more-header">

        <p className="more-text">
          More Burger Options
        </p>


        <button
          className="view-all-btn"
          onClick={() =>
            navigate(
              "/burgermenu",
              {
                state: {
                  activeFilter:
                    selectedType,
                },
              }
            )
          }
        >
          View All Burgers →
        </button>

      </div>


      {/* CART */}

      <CartContainer />


      {/* FOOTER */}

      <FooterDecoration />

    </div>

  );

}


export default Burger;