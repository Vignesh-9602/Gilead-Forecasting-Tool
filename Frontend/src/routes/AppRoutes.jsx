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

export default function AppRoutes() {
  const { favState } = useContext(GlobalContext);

  return (
    <BrowserRouter>
      <Routes>
        {/* Redirect base URL */}
        <Route path="/" element={<Navigate to="/landingpage" />} />

        <Route path="/landingpage" element={<LandingPage />} />

        <Route
          path="/app"
          element={
            favState?.selectedTherapyArea ? (
              <MainLayout />
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