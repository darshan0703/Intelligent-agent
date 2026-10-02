import { createContext, useContext, useState } from "react";

const KioskContext = createContext();

export function KioskProvider({ children }) {

  // Recommendation Screen
  const [recommendationData, setRecommendationData] = useState(null);

  // Product Page
  const [productData, setProductData] = useState(null);

  // Meal Flow
  const [mealData, setMealData] = useState(null);
  const [mealPopupOpen, setMealPopupOpen] = useState(false);
  const [selectedMeal, setSelectedMeal] = useState(null);

  // Food Preference (Module 1 Dietary Lock)
  const [foodPreference, setFoodPreferenceState] = useState("both");

  const setFoodPreference = async (pref) => {
    setFoodPreferenceState(pref);
    try {
      await fetch("/session/preference", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preference: pref }),
      });
    } catch (e) {
      console.warn("Failed to sync food preference with session:", e);
    }
  };

  return (
    <KioskContext.Provider
      value={{
        foodPreference,
        setFoodPreference,

        recommendationData,
        setRecommendationData,

        productData,
        setProductData,

        mealData,
        setMealData,

        mealPopupOpen,
        setMealPopupOpen,

        selectedMeal,
        setSelectedMeal,
      }}
    >
      {children}
    </KioskContext.Provider>
  );
}

export function useKiosk() {
  return useContext(KioskContext);
}