import { createContext, useContext, useState } from "react";

const KioskContext = createContext();

export function KioskProvider({ children }) {

  const [recommendationData, setRecommendationData] = useState(null);

  const [productData, setProductData] = useState(null);

  return (
    <KioskContext.Provider
      value={{
        recommendationData,
        setRecommendationData,

        productData,
        setProductData,
      }}
    >
      {children}
    </KioskContext.Provider>
  );
}

export function useKiosk() {
  return useContext(KioskContext);
}