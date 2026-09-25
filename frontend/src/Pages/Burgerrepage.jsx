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

import { getSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

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
  ] = useState(() => {
    if (recommendationData?.ui_action === "filter_veg" || recommendationData?.preference === "veg") return "veg";
    if (recommendationData?.ui_action === "filter_non_veg" || recommendationData?.preference === "non_veg") return "non veg";
    if (foodPreference && foodPreference !== "both") return foodPreference;
    return sessionStorage.getItem("dietary_preference") || "both";
  });

  const [fallbackData, setFallbackData] = useState(() => {
    return (typeof window !== "undefined" && window.__CATEGORY_CACHE__?.['burger']) || null;
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

  // ==========================================
  // SCREEN SYNC & BACKEND RECOMMENDATIONS FETCH
  // ==========================================

  useEffect(() => {
    syncScreen("recommended_burgers");
    const sid = getSessionId();
    const prefParam = foodPreference && foodPreference !== "both" ? `&preference=${encodeURIComponent(foodPreference)}` : "";
    fetch(`${API_BASE_URL}/recommendations/category/burger?session_id=${sid}${prefParam}`)
      .then((res) => res.json())
      .then((resData) => {
        if (resData && resData.success) {
          const cached = {
            both: resData.both,
            veg: resData.veg,
            non_veg: resData.non_veg,
            priority: resData.priority,
            premium: resData.premium,
            additional: resData.additional,
          };
          if (typeof window !== "undefined") {
            window.__CATEGORY_CACHE__ = window.__CATEGORY_CACHE__ || {};
            window.__CATEGORY_CACHE__['burger'] = cached;
          }
          setFallbackData(cached);
        }
      })
      .catch((err) => console.error("Burger fetch error:", err));
  }, [foodPreference]);

  const isBurgerRec =
    recommendationData?.category === "burger" ||
    recommendationData?.screen === "recommended_burgers" ||
    Boolean(recommendationData?.data?.both || recommendationData?.data?.veg);

  const memoryCache = (typeof window !== "undefined" && window.__CATEGORY_CACHE__?.['burger']) || null;
  const validRecData = isBurgerRec ? recommendationData?.data : null;
  const data = validRecData || fallbackData || memoryCache || {};

  // ==========================================
  // ALL BACKEND RECOMMENDATION DATA
  // ==========================================

  const bothRecommendations =
    data.both || {
      priority: data.priority || [],
      premium: data.premium || [],
      additional: data.additional || []
    };

  const vegRecommendations =
    data.veg || fallbackData?.veg || memoryCache?.veg || {
      priority: (data.priority || []).filter(i => (i.foodType || i.type || i.food_type) === "veg"),
      premium: (data.premium || []).filter(i => (i.foodType || i.type || i.food_type) === "veg"),
      additional: (data.additional || []).filter(i => (i.foodType || i.type || i.food_type) === "veg")
    };

  const nonVegRecommendations =
    data.non_veg || fallbackData?.non_veg || memoryCache?.non_veg || {
      priority: (data.priority || []).filter(i => (i.foodType || i.type || i.food_type || "").toLowerCase().includes("non")),
      premium: (data.premium || []).filter(i => (i.foodType || i.type || i.food_type || "").toLowerCase().includes("non")),
      additional: (data.additional || []).filter(i => (i.foodType || i.type || i.food_type || "").toLowerCase().includes("non"))
    };

  // ==========================================
  // SELECT DATASET FOR CURRENT FILTER
  // ==========================================

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
        return ft === "veg" || (!ft.includes("non") && !/chicken|mutton/i.test(i.name || ""));
      });
    }
    if (selectedType === "non veg" || selectedType === "non_veg") {
      return items.filter(i => {
        const ft = (i.foodType || i.type || i.food_type || "").toLowerCase();
        return ft.includes("non") || /chicken|mutton/i.test(i.name || "");
      });
    }
    return items;
  };

  let priorityItems = filterBySelectedType(selectedRecommendations.priority || []);
  let premiumItems = filterBySelectedType(selectedRecommendations.premium || []);
  let additionalItems = filterBySelectedType(selectedRecommendations.additional || []);

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

  const usedIds = new Set(priorityItems.map(i => i.id || i.name));
  if (premiumItems.length < 2) {
    const candidates = dedupedCandidates.filter(i => !usedIds.has(i.id || i.name) && !premiumItems.some(p => (p.id || p.name) === (i.id || i.name)));
    premiumItems = [...premiumItems, ...candidates].slice(0, 2);
  }
  premiumItems.forEach(i => usedIds.add(i.id || i.name));

  if (additionalItems.length < 4) {
    const candidates = dedupedCandidates.filter(i => !usedIds.has(i.id || i.name) && !additionalItems.some(m => (m.id || m.name) === (i.id || i.name)));
    additionalItems = [...additionalItems, ...candidates].slice(0, 4);
  }
  // Hard fallback: if still fewer than 4, recycle available filtered candidates so 4 slots are NEVER skipped
  if (additionalItems.length < 4 && filteredCandidatePool.length > 0) {
    const fallbackSlice = filteredCandidatePool.filter(i => !additionalItems.some(m => (m.id || m.name) === (i.id || i.name)));
    additionalItems = [...additionalItems, ...fallbackSlice, ...filteredCandidatePool].slice(0, 4);
  }

  // ==========================================
  // FILTER CHANGES
  // ==========================================

  const handleFilterChange =
    useCallback((filter) => {
      const normalizedFilter =
        filter
          .trim()
          .toLowerCase();

      console.log(
        "CHANGING BURGER FILTER:",
        normalizedFilter
      );

      setSelectedType(
        normalizedFilter
      );
      if (setFoodPreference) {
        setFoodPreference(normalizedFilter);
      }
    }, [setFoodPreference]);

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

      if (action === "filter_veg") {
        handleFilterChange("veg");
      }

      else if (
        action === "filter_non_veg"
      ) {
        handleFilterChange("non veg");
      }

      else if (
        action === "filter_both"
      ) {
        handleFilterChange("both");
      }

      else if (
        action === "view_more"
      ) {
        navigate("/burgermenu");
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

      <Header title="Choose Your Burger" />

      <BackButton />

      {/* FILTERS */}

      <div className="burger-filter-position">
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
      </div>

      {/* PRIORITY */}

      {priorityItems[0] && (
        <ProductCard
          product={priorityItems[0]}
          variant="large"
          className="card-1"
          badge="popular"
        />
      )}

      {priorityItems[1] && (
        <ProductCard
          product={priorityItems[1]}
          variant="large"
          className="card-2"
          badge="popular"
        />
      )}

      {/* PREMIUM */}

      {premiumItems[0] && (
        <ProductCard
          product={premiumItems[0]}
          variant="large"
          className="card-3"
          badge="premium"
        />
      )}

      {premiumItems[1] && (
        <ProductCard
          product={premiumItems[1]}
          variant="large"
          className="card-4"
          badge="premium"
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

      {/* RECOMMENDED SECTION */}

      <p className="Recommendation-text">
        Fresh Picks For You
      </p>

      <p className="Recommendation-text2">
        Recommended based on availability
      </p>

      {/* PREMIUM SECTION */}

      <p className="Premium-text">
        Premium Collection
      </p>

      <p className="Premium-text2">
        Handpicked just for you
      </p>

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