import {
  createContext,
  useContext,
  useCallback,
} from "react";

const UIActionContext = createContext(null);

export function UIActionProvider({ children }) {

  const executeUIAction = useCallback((action, value, extra) => {

    console.log(
      "EXECUTING UI ACTION:",
      action
    );

    window.dispatchEvent(
      new CustomEvent("kiosk-ui-action", {
        detail: {
          action,
          value,
          extra,
          meal: extra?.meal || (typeof value === "object" ? value?.meal : null),
          ...(typeof extra === "object" ? extra : {}),
        },
      })
    );

  }, []);

  return (
    <UIActionContext.Provider
      value={{
        executeUIAction,
      }}
    >
      {children}
    </UIActionContext.Provider>
  );
}

export function useUIAction() {

  const context = useContext(UIActionContext);

  if (!context) {

    throw new Error(
      "useUIAction must be used inside UIActionProvider"
    );

  }

  return context;
}