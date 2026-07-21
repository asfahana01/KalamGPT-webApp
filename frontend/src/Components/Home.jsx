import React, { useEffect, useState } from "react";
// import {
//   sortByRatings,
//   sortByReviews,
//   toggleVegOnly, 
// } from "../redux/slices/restaurantSlice"; 
// import { getRestaurants } from "../redux/actions/restaurantAction";

import Restaurant from "./Restaurant";
import Loader from "./layout/Loader";
import Message from "./Message";
import { useDispatch, useSelector } from "react-redux";
// import CountRestaurant from "./CountRestaurant";
import { useParams } from "react-router-dom";

const Home = () => {
    const [restaurants] = useState([
    {
      _id: "1",
      name: "Paradise Biryani",
      address: "Bengaluru",
      ratings: 4.5,
      numOfReviews: 120,
      isVeg: false,
      images: [
        {
          url: "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4",
        },
      ],
      reviewSentiment: "Positive",
      reviewSummaryBullets: [
        "Excellent taste",
        "Fast service",
        "Good ambience",
      ],
      reviewTopMentions: ["Biryani", "Service", "Taste"],
    },
    {
      _id: "2",
      name: "Haldiram",
      address: "Bengaluru",
      ratings: 4.8,
      numOfReviews: 250,
      isVeg: true,
      images: [
        {
          url: "https://images.unsplash.com/photo-1552566626-52f8b828add9",
        },
      ],
      reviewSentiment: "Very Positive",
      reviewSummaryBullets: [
        "Authentic South Indian food",
        "Clean restaurant",
        "Affordable prices",
      ],
      reviewTopMentions: ["Dosa", "Meals", "Coffee"],
    },
  ]);
 // Static values
  const restaurantsLoading = false;
  const restaurantsError = null;
  const creating = false;
  const createError = null;

  const isAuthenticated = true;
  const user = { role: "user" };

  const [showVegOnly, setShowVegOnly] = useState(false);

  const handleSortByRatings = () => {
    console.log("Sort By Ratings");
  };

  const handleSortByReviews = () => {
    console.log("Sort By Reviews");
  };

  const handleToggleVegOnly = () => {
    setShowVegOnly(!showVegOnly);
  };

  // admin controls
  const [showCreate, setShowCreate] = useState(false);

  const [newRestaurant, setNewRestaurant] = useState({
    name: "",
    address: "",
    isVeg: false,
    location: { type: "Point", coordinates: [] },
    imageUrl: "",
  });

  const [coordsInput, setCoordsInput] = useState("");

  const handleOpenCreate = () => {
    setShowCreate(true);
  };

  const handleCloseCreate = () => {
    setShowCreate(false);
  };

  const handleChange = (e) => {
    const { name, value, checked } = e.target;

    if (name === "isVeg") {
      setNewRestaurant({ ...newRestaurant, isVeg: checked });
    } else {
      setNewRestaurant({ ...newRestaurant, [name]: value });
    }
  };

  const submitCreate = (e) => {
    e.preventDefault();
    alert("Restaurant Created (Static Demo)");
    handleCloseCreate();
  };
  return (
    <>
      {/* <CountRestaurant /> */}

      {restaurantsLoading ? (
        <Loader />
      ) : restaurantsError ? (
        <Message variant="danger">{restaurantsError}</Message>
      ) : (
        <>
          <section>
            {/* SORT BUTTONS */}
            <div className="sort">
              <button className="sort_veg p-3" onClick={handleToggleVegOnly}>
                {showVegOnly ? "Show All" : "Pure Veg"}
              </button>

              <button className="sort_rev p-3" onClick={handleSortByReviews}>
                Sort By Reviews
              </button>

              <button className="sort_rate p-3" onClick={handleSortByRatings}>
                Sort By Ratings
              </button>
            </div>

            {/* RESTAURANTS */}
          <div className="row mt-4">
    {restaurants?.length > 0 ? (
    restaurants.map((restaurant) =>
      !showVegOnly || restaurant.isVeg ? (
        <Restaurant key={restaurant._id} restaurant={restaurant} />
      ) : null
    )
  ) : (
    <Message variant="info">No restaurants Found.</Message>
  )}
</div>
          </section>
        </>
      )}
    </>
  );
};

export default Home;