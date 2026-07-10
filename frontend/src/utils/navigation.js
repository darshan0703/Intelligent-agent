const screenRoutes = {
  recommended_burgers: "/burgers",
  recommended_drinks: "/drinks",
  recommended_sides: "/sides",
  recommended_desserts: "/desserts",

  burger_menu: "/burgermenu",
  drink_menu: "/drinkmenu",
  side_menu: "/sidemenu",
  dessert_menu: "/dessertmenu",

  product_details: "/product",

  cart: "/cart",
  checkout: "/checkout"
};

export function getRoute(screen) {
  return screenRoutes[screen] || "/Categories";
}