import "./MenuSection.css";

import ProductCard from "./ProductCard";

function MenuSection({

  title,
  products

}) {

  return (

    <div className="menu-section">

      <h2 className="menu-section-title">
        {title}
      </h2>

      <div className="menu-section-grid">

        {products.map((product) => (

          <ProductCard

            key={product.id}

            product={product}

            variant="menu"

          />

        ))}

      </div>

    </div>

  );
}

export default MenuSection;