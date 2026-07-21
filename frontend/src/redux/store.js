import { configureStore } from "@reduxjs/toolkit";
import restaurantReducer from "./slices/restaurantSlice";
// import menuReducer from "./slices/menuSlice";



const store = configureStore({
    reducer : {
        restaurants : restaurantReducer,
        // menus: menuReducer,

    }
})
export default store;