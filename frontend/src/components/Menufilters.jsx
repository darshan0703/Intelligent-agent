import "./Menufilters.css";

function Menufilters({

  filters,
  activeFilter,
  onFilterChange

}) {

  return (

    <div className="menu-filters">

      {filters.map((filter) => (

        <button

          key={filter}

          className={
            activeFilter === filter
              ? "filter-btn active-filter"
              : "filter-btn"
          }

          onClick={() =>
            onFilterChange(filter)
          }

        >

          {filter}

        </button>

      ))}

    </div>

  );
}

export default Menufilters;