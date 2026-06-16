
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

import { burgerSections } from "../data/burgers";

function Burgermenu() {

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

  const visibleSections = burgerSections
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

  }, [activeFilter]);

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

      visibleSections.forEach(section => {

        const element =
          sectionRefs.current[section.id];

        if (
          element &&
          scrollPosition >= element.offsetTop
        ) {

          currentCategory =
            section.title;

        }

      });

      // Fix for last category

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

  }, [activeFilter]);

  return (

    <div className="menu-page">

      <Header title="Choose Your Burger" />

      <BackButton />

      <Menusidebar
        categories={categories}
        activeCategory={activeCategory}
        onCategoryClick={scrollToCategory}
      />

      <Menufilters
        filters={[
          "both",
          "veg",
          "nonveg"
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

      <CartContainer
        itemCount={0}
        total={0}
      />

    </div>

  );

}

export default Burgermenu;
