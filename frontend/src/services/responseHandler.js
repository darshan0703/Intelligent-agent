import { getRoute } from "../utils/navigation";

export function handleKioskResponse(
  data,
  {
    navigate,
    setRecommendationData,
    setProductData,
    executeUIAction,
  }
) {
  console.log("========== KIOSK RESPONSE ==========");
  console.log("FULL RESPONSE:", data);

  if (!data) {
    console.warn("NO BACKEND RESPONSE");
    return;
  }

  // 1. Handle UI action
  const uiAction =
    data?.data?.ui_action ||
    data?.ui_action;

  const uiValue =
    data?.data?.value ||
    data?.value;

  if (uiAction && executeUIAction) {
    console.log("UI ACTION:", uiAction);
    console.log("UI VALUE:", uiValue);

    executeUIAction(uiAction, uiValue);
  }

  // 2. Handle screen data
  if (data?.screen && data?.data) {
    console.log("SCREEN:", data.screen);
    console.log("SCREEN DATA:", data.data);

    if (data.screen === "product") {
      setProductData?.(data);
    } else {
      setRecommendationData?.(data);
    }
  }

  // 3. Navigate to the screen
  if (data?.screen) {
    const route = getRoute(data.screen);

    console.log("BACKEND SCREEN:", data.screen);
    console.log("FRONTEND ROUTE:", route);

    if (route) {
      console.log("NAVIGATING TO:", route);
      navigate(route);
    } else {
      console.warn(
        "NO ROUTE FOUND FOR:",
        data.screen
      );
    }
  }

  // 4. Display message in console
  if (data?.message) {
    console.log("MESSAGE:", data.message);
  }

  // 5. Cart
  if (data?.cart) {
    console.log("CART:", data.cart);
  }

  console.log("====================================");
}