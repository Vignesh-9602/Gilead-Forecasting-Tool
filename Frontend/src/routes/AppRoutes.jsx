import React, { useState, useContext } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import LandingPage from "../pages/LandingPage";
import MainLayout from "../layouts/MainLayout";
import { GlobalContext } from "../context/Provider";
import TherapyAreaRouter from "./TherapyAreaRouter";
// import Login from "../pages/LoginPage";

export default function AppRoutes() {
  const { favState } = useContext(GlobalContext);

  // const isLoggedIn =
  //   !!localStorage.getItem("user");

  return (
    <BrowserRouter>
      <Routes>
        {/* Redirect base URL */}
        <Route path="/" element={<Navigate to="/landingpage" />} />
        {/* <Route path="/" element={<Login />} /> */}
        {/* <Route
          path="/"
          element={
            isLoggedIn ? (
              <Navigate to="/landingpage" />
            ) : (
              <Navigate to="/login" />
            )
          }
        />

        <Route
          path="/login"
          element={<Login />}
        /> */}

        <Route path="/landingpage" element={<LandingPage />} />

        {/* <Route
          path="/app"
          element={
            favState?.selectedTherapyArea ? (
              <MainLayout />
            ) : (
              <Navigate to="/landingpage" />
            )
          }
        /> */}

        <Route
          path="/app"
          element={
            favState?.selectedTherapyArea ? (
              <TherapyAreaRouter />
            ) : (
              <Navigate to="/landingpage" />
            )
          }
        />

        <Route path="/login" element={<div>Login Page</div>} />
      </Routes>
    </BrowserRouter>
  );
}