import "./Sidesrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useKiosk } from "../context/KioskContext";
import { syncScreen } from "../services/screenService";
import { getSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function Sides() {
  const navigate = useNavigate();
  const { recommendationData, foodPreference } = useKiosk();

  const [selectedType, setSelectedType] = useState(() => {
    if (recommendationData?.ui_action === "filter_veg" || recommendationData?.preference === "veg") return "veg";
    if (recommendationData?.ui_action === "filter_non_veg" || recommendationData?.preference === "non_veg") return "non veg";
    if (foodPreference && foodPreference !== "both") return foodPreference;
    return "both";
  });

  const [fallbackData, setFallbackData] = useState(() => {
    return (typeof window !== "undefined" && window.__CATEGORY_CACHE__?.['side']) || null;
  });

  useEffect(() => {
    if (recommendationData?.ui_action === "filter_veg" || recommendationData?.preference === "veg") {
      setSelectedType("veg");
    } else if (recommendationData?.ui_action === "filter_non_veg" || recommendationData?.preference === "non_veg") {
      setSelectedType("non veg");
    } else if (foodPreference) {
      setSelectedType(foodPreference);
    }
  }, [recommendationData, foodPreference]);

  useEffect(() => {
    syncScreen("recommended_sides");
    const sid = getSessionId();
    const prefParam = foodPreference && foodPreference !== "both" ? `&preference=${encodeURIComponent(foodPreference)}` : "";
    fetch(`${API_BASE_URL}/recommendations/category/side?session_id=${sid}${prefParam}`)
      .then((res) => res.json())
      .then((data) => {
        if (data && data.success) {
          const cached = {
            priority: data.priority,
            premium: data.premium,
            additional: data.additional,
            both: data.both,
            veg: data.veg,
            non_veg: data.non_veg,
          };
          if (typeof window !== "undefined") {
            window.__CATEGORY_CACHE__ = window.__CATEGORY_CACHE__ || {};
            window.__CATEGORY_CACHE__['side'] = cached;
          }
          setFallbackData(cached);
        }
      })
      .catch((err) => console.error("Sides fetch error:", err));
  }, [foodPreference]);

  const isSideRec =
    (recommendationData?.category === "side" ||
     recommendationData?.screen === "recommended_sides" ||
     recommendationData?.data?.category === "side") &&
    Boolean(recommendationData?.data?.both || recommendationData?.data?.veg);

  const validRecData = isSideRec ? recommendationData?.data : null;
  const memoryCache = (typeof window !== "undefined" && window.__CATEGORY_CACHE__?.['side']) || null;
  const data = validRecData || fallbackData || memoryCache || {};

  const bothRecommendations = data.both || {
    priority: data.priority || [],
    premium: data.premium || [],
    additional: data.additional || []
  };

  const vegRecommendations = data.veg || fallbackData?.veg || memoryCache?.veg || {
    priority: (data.priority || []).filter(i => (i.foodType || i.type || i.food_type) === "veg"),
    premium: (data.premium || []).filter(i => (i.foodType || i.type || i.food_type) === "veg"),
    additional: (data.additional || []).filter(i => (i.foodType || i.type || i.food_type) === "veg")
  };

  const nonVegRecommendations = data.non_veg || fallbackData?.non_veg || memoryCache?.non_veg || {
    priority: (data.priority || []).filter(i => (i.foodType || i.type || i.food_type || "").toLowerCase().includes("non")),
    premium: (data.premium || []).filter(i => (i.foodType || i.type || i.food_type || "").toLowerCase().includes("non")),
    additional: (data.additional || []).filter(i => (i.foodType || i.type || i.food_type || "").toLowerCase().includes("non"))
  };

  const selectedRecommendations =
    selectedType === "veg"
      ? vegRecommendations
      : selectedType === "non veg" || selectedType === "non_veg"
        ? nonVegRecommendations
        : bothRecommendations;

  const filterBySelectedType = (items) => {
    if (!items || !Array.isArray(items)) return [];
    if (selectedType === "veg") {
      return items.filter(i => {
        const ft = (i.foodType || i.type || i.food_type || "").toLowerCase();
        return ft === "veg" || (!ft.includes("non") && !/chicken|wings|nugget|bone/i.test(i.name || ""));
      });
    }
    if (selectedType === "non veg" || selectedType === "non_veg") {
      return items.filter(i => {
        const ft = (i.foodType || i.type || i.food_type || "").toLowerCase();
        return ft.includes("non") || /chicken|wings|nugget|bone/i.test(i.name || "");
      });
    }
    return items;
  };

  let hotSides = filterBySelectedType(selectedRecommendations.priority || []);
  let premiumSides = filterBySelectedType(selectedRecommendations.premium || []);
  let moreSides = filterBySelectedType(selectedRecommendations.additional || []);

  // Backfill slots defensively so sections NEVER collapse into blank white space
  const allCandidatePool = [
    ...(selectedRecommendations.priority || []),
    ...(selectedRecommendations.premium || []),
    ...(selectedRecommendations.additional || []),
    ...(fallbackData?.veg?.priority || []),
    ...(fallbackData?.veg?.premium || []),
    ...(fallbackData?.veg?.additional || []),
    ...(fallbackData?.both?.priority || []),
    ...(fallbackData?.both?.premium || []),
    ...(fallbackData?.both?.additional || []),
    ...(memoryCache?.veg?.priority || []),
    ...(memoryCache?.veg?.premium || []),
    ...(memoryCache?.veg?.additional || []),
    ...(memoryCache?.both?.priority || []),
    ...(memoryCache?.both?.premium || []),
    ...(memoryCache?.both?.additional || []),
  ];
  const filteredCandidatePool = filterBySelectedType(allCandidatePool);
  const dedupedCandidates = Array.from(new Map(filteredCandidatePool.map(item => [item.id || item.name, item])).values());

  const usedIds = new Set(hotSides.map(i => i.id || i.name));
  if (premiumSides.length < 2) {
    const candidates = dedupedCandidates.filter(i => !usedIds.has(i.id || i.name) && !premiumSides.some(p => (p.id || p.name) === (i.id || i.name)));
    premiumSides = [...premiumSides, ...candidates].slice(0, 2);
  }
  premiumSides.forEach(i => usedIds.add(i.id || i.name));

  if (moreSides.length < 4) {
    const candidates = dedupedCandidates.filter(i => !usedIds.has(i.id || i.name) && !moreSides.some(m => (m.id || m.name) === (i.id || i.name)));
    moreSides = [...moreSides, ...candidates].slice(0, 4);
  }
  if (moreSides.length < 4 && filteredCandidatePool.length > 0) {
    const fallbackSlice = filteredCandidatePool.filter(i => !moreSides.some(m => (m.id || m.name) === (i.id || i.name)));
    moreSides = [...moreSides, ...fallbackSlice, ...filteredCandidatePool].slice(0, 4);
  }

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
          onClick={() => navigate("/sidesmenu")}
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