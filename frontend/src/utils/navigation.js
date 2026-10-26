const screenRoutes = {
  category_selection: "/Categories",
  recommended_burgers: "/burgers",
  recommended_drinks: "/drinks",
  recommended_sides: "/sides",
  recommended_desserts: "/desserts",

  burger_menu: "/burgermenu",
  drink_menu: "/drinkmenu",
  side_menu: "/sidesmenu",
  dessert_menu: "/dessertmenu",

  product: "/product",
  meal_conversion: "/mealpage",

  cart: "/cart",
  checkout: "/cart",
  payment: "/cart",
  order_complete: "/order-complete",
};

export function getRoute(screen) {
  return screenRoutes[screen];
}