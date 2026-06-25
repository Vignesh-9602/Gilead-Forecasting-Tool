import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { GlobalContext } from "../context/Provider";
import MainLayout from "../layouts/MainLayout";
import HCVLayout from "../layouts/HCVLayout";

export default function TherapyAreaRouter() {
    const { favState } = useContext(GlobalContext);

    switch (favState?.selectedTherapyArea) {
        case "Oncology":
            return <MainLayout />;

        case "HCV":
            return <HCVLayout />;

        default:
            return <Navigate to="/landingpage" />;
    }
}