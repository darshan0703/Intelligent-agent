import { BrowserRouter, Routes, Route } from "react-router-dom";
import { UIActionProvider } from "./context/UIActionContext";
import { KioskProvider } from "./context/KioskContext";
import { VoiceConversationProvider } from "./context/VoiceConversationProvider";

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
      <KioskProvider>
        <UIActionProvider>
        <VoiceConversationProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/Categories" element={<Categories />} />

            <Route path="/burgers" element={<Burger />} />
            <Route path="/drinks" element={<Drink />} />
            <Route path="/desserts" element={<Dessert />} />
            <Route path="/sides" element={<Sides />} />

            <Route path="/burgermenu" element={<Burgermenu />} />
            <Route path="/drinkmenu" element={<Drinkmenu />} />
            <Route path="/dessertmenu" element={<Dessertmenu />} />
            <Route path="/sidesmenu" element={<Sidesmenu />} />

            <Route path="/product" element={<ProductPage />} />
            <Route path="/mealpage" element={<MealPage />} />

            <Route path="/cart" element={<CartPage />} />
            <Route
              path="/order-complete"
              element={<OrderCompletePage />}
            />
          </Routes>
        </VoiceConversationProvider>
        </UIActionProvider>
      </KioskProvider>
    </BrowserRouter>
  );
}

export default App;