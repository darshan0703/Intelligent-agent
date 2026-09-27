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

  return (
    <KioskContext.Provider
      value={{
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