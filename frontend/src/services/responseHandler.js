import { getRoute } from "../utils/navigation.js";
import { measureScreenRender } from "./perf.js";

export function handleKioskResponse(
  data,
  {
    navigate,
    location,
    setRecommendationData,
    setProductData,
    executeUIAction,
    tracker = null,
  } = {}
) {
  console.log("HANDLING RESPONSE:", data);

  if (!data) return;

  // Current-screen UI action, normally used by voice.
  if (data.data?.ui_action && executeUIAction) {
    console.log(
      "BACKEND REQUESTED UI ACTION:",
      data.data.ui_action
    );

    // If backend requested open_cart, navigate directly to the cart route
    if (data.data.ui_action === "open_cart") {
      const route = getRoute(data.screen || "cart") || "/cart";
      if (tracker) {
        tracker.log("navigation_initiated", {
          destination: route,
          screen: data.screen || "cart",
        });
      }
      navigate?.(route);
      if (tracker) {
        measureScreenRender(tracker, route);
      }
      return;
    }

    executeUIAction(
      data.data.ui_action,
      data.data?.value,
      data.data
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
    if (data.screen === "product") {
      setProductData?.(data);
    } else if (data.screen !== "meal_conversion") {
      setRecommendationData?.(data);
    }
  }

  // Only navigate when the backend actually
  // selected a screen.
  if (data.screen) {
    const route = getRoute(data.screen);

    if (route) {
      if (tracker) {
        tracker.log("navigation_initiated", {
          destination: route,
          screen: data.screen,
        });
      }

      if (route === "/product") {
        const currentPath = location?.pathname;
        const existingOrigin = location?.state?.origin;

        // Capture current route if coming from another page.
        // If already on /product, preserve the existing origin.
        // Never overwrite a valid origin with undefined.
        const originToUse =
          currentPath && currentPath !== "/product"
            ? currentPath
            : existingOrigin;

        navigate(
          route,
          originToUse ? { state: { origin: originToUse } } : undefined
        );
      } else if (route === "/mealpage") {
        const currentPath = location?.pathname;
        const existingOrigin = location?.state?.origin;

        // Capture current route if coming from another page.
        // If already on /mealpage, preserve the existing origin.
        // Default safely to /burgers if origin is missing or "/".
        const originToUse =
          currentPath && currentPath !== "/mealpage" && currentPath !== "/"
            ? currentPath
            : (existingOrigin && existingOrigin !== "/" ? existingOrigin : "/burgers");

        // Safely extract meal object from data without crashing if missing
        const mealData =
          data.data?.meal ||
          data.data?.value?.meal ||
          data.meal ||
          location?.state?.meal ||
          null;

        navigate(
          route,
          {
            state: {
              meal: mealData,
              origin: originToUse,
            },
          }
        );
      } else {
        navigate(route);
      }

      if (tracker) {
        measureScreenRender(tracker, route);
      }
    }
  }
}