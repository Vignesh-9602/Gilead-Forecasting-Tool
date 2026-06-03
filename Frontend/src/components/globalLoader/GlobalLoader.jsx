import React from "react";
import { Box } from "@mui/material";
import { useLoadingStore } from "../../stores";

export default function GlobalLoader() {
  const isLoading = useLoadingStore((s) => s.isLoading);
  if (!isLoading) return null;

  return (
    <>
      <style>{`
        @keyframes capPulse {
          0%, 100% { transform: scaleY(1); }
          50%       { transform: scaleY(0.7); }
        }
        .cap-left  { animation: capPulse 1.4s ease-in-out infinite; }
        .cap-right { animation: capPulse 1.4s ease-in-out infinite 0.2s; }
      `}</style>

      <Box
        sx={{
          position: "fixed",
          top: 0, left: 0,
          width: "100vw", height: "100vh",
          backgroundColor: "rgba(255,255,255,0.75)",
          zIndex: 2000,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "14px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
          <div
            className="cap-left"
            style={{
              width: "28px", height: "22px",
              borderRadius: "11px 0 0 11px",
              background: "#C8102E",
            }}
          />
          <div
            className="cap-right"
            style={{
              width: "28px", height: "22px",
              borderRadius: "0 11px 11px 0",
              background: "#5A5A5D",
            }}
          />
        </div>

        {/* <span
          style={{
            fontSize: "11px",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "#999",
          }}
        >
          GILEAD
        </span> */}
      </Box>
    </>
  );
}