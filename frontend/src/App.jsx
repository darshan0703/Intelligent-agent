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

function App() {
  

  return (
    <BrowserRouter>
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
      </Routes>
    </BrowserRouter>
  );
}

export default App;