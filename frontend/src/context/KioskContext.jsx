import { createContext, useContext, useState, useEffect } from "react";
import { getSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

const KioskContext = createContext();

export function KioskProvider({ children }) {
  // Recommendation Screen
  const [recommendationData, setRecommendationData] = useState(null);

  // Global Dietary Filter (both / veg / non veg)
  const [foodPreference, setFoodPreferenceState] = useState(() => {
    return sessionStorage.getItem("dietary_preference") || "both";
  });

  const setFoodPreference = (pref) => {
    const p = (pref || "both").trim().toLowerCase();
    setFoodPreferenceState(p);
    sessionStorage.setItem("dietary_preference", p);
    // Asynchronously notify backend session
    const sid = getSessionId();
    fetch(`${API_BASE_URL}/session/preference`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sid, preference: p }),
    }).catch(() => {});
  };

  // Product Page
  const [productData, setProductData] = useState(null);

  // Meal Flow
  const [mealData, setMealData] = useState(null);
  const [mealPopupOpen, setMealPopupOpen] = useState(false);
  const [selectedMeal, setSelectedMeal] = useState(null);

  // Real-Time Ephemeral Session Heuristics (Zero-Training)
  const [sessionContext, setSessionContext] = useState({
    active_affinities: [],
    rejected_categories: [],
    active_affinity: {},
    rejected_sub_roles: [],
    velocity_state: null,
  });

  const addActiveAffinity = (affinity) => {
    if (!affinity) return;
    const clean = affinity.trim().toLowerCase();
    setSessionContext((prev) => {
      if (prev.active_affinities.includes(clean)) return prev;
      return {
        ...prev,
        active_affinities: [...prev.active_affinities, clean],
      };
    });
  };

  const removeActiveAffinity = (affinity) => {
    const clean = (affinity || "").trim().toLowerCase();
    setSessionContext((prev) => ({
      ...prev,
      active_affinities: prev.active_affinities.filter((a) => a !== clean),
    }));
  };

  const setActiveScalarAffinity = (attribute, value) => {
    if (!attribute) return;
    setSessionContext((prev) => ({
      ...prev,
      active_affinity: {
        ...(prev.active_affinity || {}),
        [attribute]: value,
      },
    }));
  };

  const rejectCategory = (category) => {
    if (!category) return;
    const clean = category.trim().toLowerCase();
    setSessionContext((prev) => {
      if (prev.rejected_categories.includes(clean)) return prev;
      return {
        ...prev,
        rejected_categories: [...prev.rejected_categories, clean],
      };
    });
  };

  const unrejectCategory = (category) => {
    const clean = (category || "").trim().toLowerCase();
    setSessionContext((prev) => ({
      ...prev,
      rejected_categories: prev.rejected_categories.filter((c) => c !== clean),
    }));
  };

  const rejectSubRole = (subRole) => {
    if (!subRole) return;
    const clean = subRole.trim().toLowerCase();
    setSessionContext((prev) => {
      if ((prev.rejected_sub_roles || []).includes(clean)) return prev;
      return {
        ...prev,
        rejected_sub_roles: [...(prev.rejected_sub_roles || []), clean],
      };
    });
  };

  const unrejectSubRole = (subRole) => {
    const clean = (subRole || "").trim().toLowerCase();
    setSessionContext((prev) => ({
      ...prev,
      rejected_sub_roles: (prev.rejected_sub_roles || []).filter((r) => r !== clean),
    }));
  };

  const setVelocityState = (state) => {
    setSessionContext((prev) => ({
      ...prev,
      velocity_state: state ? String(state).trim().toLowerCase() : null,
    }));
  };

  const trackProductInteraction = (product) => {
    if (!product) return;
    const text = `${product.name || ""} ${product.shortDescription || ""} ${product.category || ""} ${product.foodType || ""}`.toLowerCase();
    const candidateAffinities = ["spicy", "chicken", "paneer", "peri peri", "cheese", "chocolate", "crispy"];
    candidateAffinities.forEach((aff) => {
      if (text.includes(aff)) {
        addActiveAffinity(aff);
      }
    });

    // Attribute Affinity Tracker: Peri Peri / Spicy clicks set Spice >= 4
    if (text.includes("peri peri") || text.includes("peri-peri") || text.includes("spicy") || text.includes("fiery")) {
      setActiveScalarAffinity("Spice", 4);
    }

    if (Array.isArray(product.tags)) {
      product.tags.forEach((t) => addActiveAffinity(t));
    }
  };

  const resetSessionState = () => {
    sessionStorage.removeItem("dietary_preference");
    setFoodPreferenceState("both");
    setRecommendationData(null);
    setProductData(null);
    setMealData(null);
    setMealPopupOpen(false);
    setSelectedMeal(null);
    setSessionContext({
      active_affinities: [],
      rejected_categories: [],
      active_affinity: {},
      rejected_sub_roles: [],
      velocity_state: null,
    });
  };

  return (
    <KioskContext.Provider
      value={{
        recommendationData,
        setRecommendationData,

        foodPreference,
        setFoodPreference,

        productData,
        setProductData,

        mealData,
        setMealData,

        mealPopupOpen,
        setMealPopupOpen,

        selectedMeal,
        setSelectedMeal,

        sessionContext,
        setSessionContext,
        addActiveAffinity,
        removeActiveAffinity,
        setActiveScalarAffinity,
        rejectCategory,
        unrejectCategory,
        rejectSubRole,
        unrejectSubRole,
        setVelocityState,
        trackProductInteraction,
        resetSessionState,
      }}
    >
      {children}
    </KioskContext.Provider>
  );
}

export function useKiosk() {
  return useContext(KioskContext);
}