import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { GlobalContext } from "../context/Provider";
import MainLayout from "../layouts/MainLayout";
import PBCLayout from "../layouts/PBCLayout";

export default function TherapyAreaRouter() {
    const { favState } = useContext(GlobalContext);

    switch (favState?.selectedTherapyArea) {
        case "Oncology":
            return <MainLayout />;

        case "PBC":
            return <PBCLayout />;

        default:
            return <Navigate to="/landingpage" />;
    }
}