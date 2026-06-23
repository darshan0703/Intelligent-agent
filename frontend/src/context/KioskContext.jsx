import { createContext, useContext, useState } from "react";

const KioskContext = createContext();

export function KioskProvider({ children }) {

  const [screenData, setScreenData] = useState(null);

  return (
    <KioskContext.Provider
      value={{
        screenData,
        setScreenData
      }}
    >
      {children}
    </KioskContext.Provider>
  );
}

export function useKiosk() {
  return useContext(KioskContext);
}