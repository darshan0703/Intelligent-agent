import "./menu.css";

import Header from "../components/Header";
import BackButton from "../components/BackButton";
import Menusidebar from "../components/Menusidebar";
import Menufilters from "../components/Menufilters";
import CartContainer from "../components/CartContainer";
import MenuSection from "../components/MenuSection";

import {
  useRef,
  useState,
  useEffect
} from "react";

function Drinkmenu() {

  const [drinkSections, setDrinkSections] = useState([]);

 useEffect(() => {
    fetch("http://127.0.0.1:8000/menu/drinks")
        .then((res) => res.json())
        .then(setDrinkSections);
}, []);

  const menuContentRef = useRef(null);

  const sectionRefs = useRef({});

  const [activeCategory, setActiveCategory] =
    useState("");

  const [activeFilter, setActiveFilter] =
    useState("both");

  const filterProducts = (products) => {

    if (activeFilter === "both") {
      return products;
    }

    return products.filter(
      product => product.type === activeFilter
    );

  };

  const visibleSections = drinkSections
    .map(section => ({
      ...section,
      products: filterProducts(
        section.products
      )
    }))
    .filter(
      section =>
        section.products.length > 0
    );

  const categories = visibleSections.map(
    section => section.title
  );

  useEffect(() => {

    if (
      visibleSections.length > 0 &&
      !visibleSections.some(
        section =>
          section.title === activeCategory
      )
    ) {

      setActiveCategory(
        visibleSections[0].title
      );

    }

  }, [activeFilter, visibleSections.length]);

  const scrollToCategory = (categoryTitle) => {

    setActiveCategory(categoryTitle);

    const section = visibleSections.find(
      section =>
        section.title === categoryTitle
    );

    if (!section) return;

    sectionRefs.current[
      section.id
    ]?.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });

  };

  useEffect(() => {

    const menu = menuContentRef.current;

    if (!menu) return;

    const handleScroll = () => {

      const scrollPosition =
        menu.scrollTop +
        menu.clientHeight / 4;

      let currentCategory =
        visibleSections[0]?.title;

       console.log({
    scrollTop: menu.scrollTop,
    currentCategory,});

      visibleSections.forEach(section => {

        const element =
          sectionRefs.current[section.id];

           console.log(
    section.title,
    element?.offsetTop
     );

        if (
          element &&
          scrollPosition >= element.offsetTop
        ) {

          currentCategory =
            section.title;

        }

      });

      const isNearBottom =
        menu.scrollTop +
          menu.clientHeight >=
        menu.scrollHeight - 50;

      if (isNearBottom) {

        currentCategory =
          visibleSections[
            visibleSections.length - 1
          ]?.title;

      }

      setActiveCategory(prev =>
        prev !== currentCategory
          ? currentCategory
          : prev
      );

    };

    handleScroll();

    menu.addEventListener(
      "scroll",
      handleScroll
    );

    return () => {

      menu.removeEventListener(
        "scroll",
        handleScroll
      );

    };

  }, [activeFilter,drinkSections]);

  return (

    <div className="menu-page">

      <Header title="Choose Your Drink" />

      <BackButton />

      <Menusidebar
        categories={categories}
        activeCategory={activeCategory}
        onCategoryClick={scrollToCategory}
      />

      <Menufilters
        filters={[
          "both",
          "cold",
          "hot"
        ]}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
      />

      <div
        className="menu-content"
        ref={menuContentRef}
      >

        {visibleSections.map(section => (

          <div
            key={section.id}
            ref={(el) => {
              sectionRefs.current[
                section.id
              ] = el;
            }}
          >

            <MenuSection
              title={section.title}
              products={section.products}
            />

          </div>

        ))}

      </div>

      <CartContainer />

    </div>

  );

}

export default Drinkmenu;
