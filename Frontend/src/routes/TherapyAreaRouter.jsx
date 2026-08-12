import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import { GlobalContext } from "../context/Provider";
import MainLayout from "../layouts/MainLayout";
import HCVLayout from "../layouts/HCVLayout";
import HIVLayout from "../layouts/HIVLayout";
import HIVPrepLayout from "../layouts/HIVPrepLayout";

export default function TherapyAreaRouter() {
    const { favState } = useContext(GlobalContext);

    switch (favState?.selectedTherapyArea) {
        case "Oncology":
            return <MainLayout />;

        case "HCV":
            return <HCVLayout />;

        case "HIV Treatment":
            return <HIVLayout />;

        case "HIV PrEP":
            return <HIVPrepLayout />;

        default:
            return <Navigate to="/landingpage" />;
    }
}