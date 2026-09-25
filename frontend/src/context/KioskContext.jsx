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
  const [dismissedMealProducts, setDismissedMealProducts] = useState(new Set());

  const dismissMealOffer = (productId) => {
    if (productId != null) {
      setDismissedMealProducts((prev) => {
        const next = new Set(prev);
        next.add(Number(productId) || productId);
        next.add(String(productId));
        return next;
      });
    }
  };

  const resetMealOfferState = () => {
    setDismissedMealProducts(new Set());
    setMealData(null);
    setMealPopupOpen(false);
    setSelectedMeal(null);
  };

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

        dismissedMealProducts,
        setDismissedMealProducts,
        dismissMealOffer,
        resetMealOfferState,
      }}
    >
      {children}
    </KioskContext.Provider>
  );
}

export function useKiosk() {
  return useContext(KioskContext);
}