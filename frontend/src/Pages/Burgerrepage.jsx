import "./Burgerrepage.css";

import { useNavigate } from "react-router-dom";
import { useState } from "react";

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

  const { recommendationData } = useKiosk();

  const [selectedType, setSelectedType] =
    useState("both");

  const allBurgers =
    recommendationData?.data?.all_burgers || [];

  const filteredBurgers =
    selectedType === "both"
      ? allBurgers
      : allBurgers.filter(
          (burger) =>
            burger.food_type.toLowerCase() ===
            selectedType
        );

  const priorityItems =
    filteredBurgers.slice(0, 2);

  const premiumItems =
    filteredBurgers.slice(2, 4);

  const additionalItems =
    filteredBurgers.slice(4, 8);

  const handleFilterChange = (filter) => {

    setSelectedType(
      filter.toLowerCase()
    );

  };

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

      <Menufilters
        filters={[
          "both",
          "veg",
          "non veg"
        ]}
        activeFilter={selectedType}
        onFilterChange={handleFilterChange}
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

  console.log(
  "ALL BURGERS:",
  recommendationData?.data?.all_burgers
 );

 console.log(
  "RECOMMENDATION DATA:",
  recommendationData
 );
}

export default Burger;