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

  // Current-screen UI action, normally used by voice.
  if (data.data?.ui_action && executeUIAction) {
    console.log(
      "BACKEND REQUESTED UI ACTION:",
      data.data.ui_action
    );

    executeUIAction(
      data.data.ui_action,
      data.data?.value
    );

    return;
  }

  // Only replace recommendation data when the
  // backend actually returned screen data.
  if (
    data.screen &&
    data.data &&
    Object.keys(data.data).length > 0
  ) {
    if (data.screen === "product_details") {
      setProductData(data);
    } else {
      setRecommendationData(data);
    }
  }

  // Only navigate when the backend actually
  // selected a screen.
  if (data.screen) {
    const route = getRoute(data.screen);

    if (route) {
      navigate(route);
    }
  }
}