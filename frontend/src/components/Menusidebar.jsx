import "./MenuSidebar.css";

function Menusidebar({

  categories,
  activeCategory,
  onCategoryClick

}) {

  return (

    <div className="menu-sidebar">

      {categories.map((category) => (

        <button
          key={category}
          className={
            activeCategory === category
              ? "menu-category-btn active-category"
              : "menu-category-btn"
          }
          onClick={() => onCategoryClick(category)}
        >

          {category}

        </button>

      ))}

    </div>

  );
}

export default Menusidebar;