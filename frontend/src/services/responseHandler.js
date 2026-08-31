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
  console.log("HANDLING RESPONSE:", data);

  if (!data) return;

  // Voice/current-screen UI action
  if (data.data?.ui_action && executeUIAction) {
    console.log(
      "BACKEND REQUESTED UI ACTION:",
      data.data.ui_action
    );

    executeUIAction(data.data.ui_action);
    return;
  }

  // Normal backend response
  if (data.screen === "product_details") {
    setProductData(data);
  } else {
    setRecommendationData(data);
  }

  // Backend-driven navigation
  const route = getRoute(data.screen);

  if (route) {
    navigate(route);
  }
}