import { BrowserRouter, Routes, Route } from "react-router-dom";

import Home from "./Pages/Home";
import Categories from "./Pages/Categories";

import Burger from "./Pages/Burgerrepage";
import Drink from "./Pages/Drinkrepage";
import Dessert from "./Pages/Dessertrepage";
import Sides from "./Pages/Sidesrepage";

import Burgermenu from "./Pages/Burgermenu";
import Drinkmenu from "./Pages/Drinkmenu";
import Dessertmenu from "./Pages/Dessertmenu";
import Sidesmenu from "./Pages/Sidesmenu";

import ProductPage from "./Pages/ProductPage";
import MealPage from "./Pages/MealPage";

import CartPage from "./Pages/CartPage";
import OrderCompletePage from "./Pages/OrderCompletePage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Home */}
        <Route path="/" element={<Home />} />

        {/* Categories */}
        <Route path="/Categories" element={<Categories />} />

        {/* Recommended category pages */}
        <Route path="/burgers" element={<Burger />} />
        <Route path="/drinks" element={<Drink />} />
        <Route path="/desserts" element={<Dessert />} />
        <Route path="/sides" element={<Sides />} />

        {/* Full menu pages */}
        <Route path="/burgermenu" element={<Burgermenu />} />
        <Route path="/drinkmenu" element={<Drinkmenu />} />
        <Route path="/dessertmenu" element={<Dessertmenu />} />
        <Route path="/sidesmenu" element={<Sidesmenu />} />

        {/* Product */}
        <Route path="/product" element={<ProductPage />} />

        {/* Meal conversion */}
        <Route path="/mealpage" element={<MealPage />} />

        {/* Cart and payment */}
        <Route path="/cart" element={<CartPage />} />
        <Route path="/order-complete" element={<OrderCompletePage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;