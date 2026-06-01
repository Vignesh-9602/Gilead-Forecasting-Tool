// src/components/common/GlobalLoader.jsx
import React from "react";
import { Box, CircularProgress } from "@mui/material";
import { useLoadingStore } from "../../stores";

export default function GlobalLoader() {
  const isLoading = useLoadingStore((state) => state.isLoading);

  if (!isLoading) return null;

  return (
    <Box
      sx={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        // backdropFilter: "blur(2px)",
        backgroundColor: "rgba(255,255,255,0.6)",
        zIndex: 2000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <CircularProgress size={50} sx={{ color: "#4F46E5" }} />
    </Box>
  );
}