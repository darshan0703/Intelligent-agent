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

import { useKiosk } from "../context/KioskContext";


function Burger() {

  const navigate = useNavigate();

  const {
    recommendationData,
  } = useKiosk();


  const [
    selectedType,
    setSelectedType
  ] = useState("both");


  const allBurgers =
    recommendationData?.data?.all_burgers || [];


  // ==========================================
  // SCREEN SYNC
  // ==========================================

  useEffect(() => {

    syncScreen("recommended_burgers");

  }, []);


  // ==========================================
  // FILTER CHANGES
  // ==========================================

  const handleFilterChange =
    useCallback((filter) => {

      console.log(
        "CHANGING BURGER FILTER:",
        filter
      );

      setSelectedType(
        filter
          .trim()
          .toLowerCase()
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
        "BURGER PAGE RECEIVED UI ACTION:",
        action
      );


      // ======================================
      // VEG
      // ======================================

      if (action === "filter_veg") {

        handleFilterChange("veg");

      }


      // ======================================
      // NON VEG
      // ======================================

      else if (
        action === "filter_non_veg"
      ) {

        handleFilterChange("non veg");

      }


      // ======================================
      // BOTH
      // ======================================

      else if (
        action === "filter_both"
      ) {

        handleFilterChange("both");

      }


      // ======================================
      // VIEW MORE
      // ======================================

      else if (
        action === "view_more"
      ) {

        navigate("/burgermenu");

      }


      // ======================================
      // GO BACK
      // ======================================

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


  // ==========================================
  // FILTER EXISTING DATA
  // ==========================================

  const filteredBurgers =
    selectedType === "both"
      ? allBurgers
      : allBurgers.filter(
          (burger) =>
            (burger.foodType ?? "")
              .trim()
              .toLowerCase() ===
            selectedType
              .trim()
              .toLowerCase()
        );


  // ==========================================
  // DISPLAY GROUPS
  // ==========================================

  const priorityItems =
    filteredBurgers.slice(0, 2);


  const premiumItems =
    filteredBurgers.slice(2, 4);


  const additionalItems =
    filteredBurgers.slice(4, 8);


  return (

    <div className="burger-page">


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


      <Header title="Choose Your Burger" />

      <BackButton />


      {/* FILTERS */}

      <Menufilters
        filters={[
          "both",
          "veg",
          "non veg",
        ]}
        activeFilter={selectedType}
        onFilterChange={
          handleFilterChange
        }
      />


      {/* PRIORITY */}

      {priorityItems[0] && (

        <ProductCard
          product={priorityItems[0]}
          variant="large"
          className="card-1"
        />

      )}


      {priorityItems[1] && (

        <ProductCard
          product={priorityItems[1]}
          variant="large"
          className="card-2"
        />

      )}


      {/* PREMIUM */}

      {premiumItems[0] && (

        <ProductCard
          product={premiumItems[0]}
          variant="large"
          className="card-3"
        />

      )}


      {premiumItems[1] && (

        <ProductCard
          product={premiumItems[1]}
          variant="large"
          className="card-4"
        />

      )}


      {/* ADDITIONAL */}

      {additionalItems[0] && (

        <ProductCard
          product={additionalItems[0]}
          variant="small"
          className="card-5"
        />

      )}


      {additionalItems[1] && (

        <ProductCard
          product={additionalItems[1]}
          variant="small"
          className="card-6"
        />

      )}


      {additionalItems[2] && (

        <ProductCard
          product={additionalItems[2]}
          variant="small"
          className="card-7"
        />

      )}


      {additionalItems[3] && (

        <ProductCard
          product={additionalItems[3]}
          variant="small"
          className="card-8"
        />

      )}


      {/* TITLES */}

      <p className="Recommendation-text">
        Fresh Picks For You
      </p>


      <p className="Recommendation-text2">
        Recommended based on availability
      </p>


      <div className="thin-line-2"></div>


      <p className="Premium-text">
        Premium Collection
      </p>


      <p className="Premium-text2">
        Handpicked just for you
      </p>


      <div className="thin-line-3"></div>


      {/* MORE OPTIONS */}

      <div className="more-header">

        <p className="more-text">
          More Burger Options
        </p>


        <button
          className="view-all-btn"
          onClick={() =>
            navigate("/burgermenu")
          }
        >
          View All →
        </button>

      </div>


      <CartContainer />

    </div>

  );

}


export default Burger;