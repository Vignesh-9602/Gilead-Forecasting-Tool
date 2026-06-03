// pill loader

import React from "react";
import { Box } from "@mui/material";
import { useLoadingStore } from "../../stores";

export default function GlobalLoader() {
    const isLoading = useLoadingStore((s) => s.isLoading);
    if (!isLoading) return null;

    return (
        <>
            <style>{`
        @keyframes pillFill {
          0%   { width: 0;    opacity: 1; }
          70%  { width: 100%; opacity: 1; }
          85%  { width: 100%; opacity: 0; }
          100% { width: 0;    opacity: 0; }
        }
        @keyframes dotFade {
          0%, 100% { opacity: 0.2; }
          50%      { opacity: 1;   }
        }
        .gilead-pill-fill { animation: pillFill 1.8s ease-in-out infinite; }
        .gilead-dot-1 { animation: dotFade 1.8s ease-in-out infinite 0s; }
        .gilead-dot-2 { animation: dotFade 1.8s ease-in-out infinite 0.2s; }
        .gilead-dot-3 { animation: dotFade 1.8s ease-in-out infinite 0.4s; }
      `}</style>

            <Box sx={{
                position: "fixed", top: 0, left: 0,
                width: "100vw", height: "100vh",
                backgroundColor: "rgba(255,255,255,0.8)",
                zIndex: 2000,
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                gap: "16px",
            }}>

                {/* Pill */}
                <div style={{
                    width: "64px", height: "26px", borderRadius: "13px",
                    border: "2px solid #A01E35", overflow: "hidden",
                    position: "relative", background: "rgba(160,30,53,0.06)",
                }}>
                    <div className="gilead-pill-fill" style={{
                        position: "absolute", top: 0, left: 0,
                        height: "100%", background: "#A01E35", borderRadius: "11px",
                    }} />
                </div>

                {/* Dots */}
                <div style={{ display: "flex", gap: "5px" }}>
                    {[["gilead-dot-1", "#A01E35"], ["gilead-dot-2", "#7a1628"], ["gilead-dot-3", "#006272"]].map(([cls, bg]) => (
                        <div key={cls} className={cls} style={{
                            width: "5px", height: "5px",
                            borderRadius: "50%", background: bg,
                        }} />
                    ))}
                </div>

                {/* Brand label */}
                <span style={{
                    fontSize: "11px", letterSpacing: "0.13em",
                    textTransform: "uppercase", color: "#006272", fontWeight: 500,
                }}>
                    Gilead Sciences
                </span>

            </Box>
        </>
    );
}

// capsule loader

// import React from "react";
// import { Box } from "@mui/material";
// import { useLoadingStore } from "../../stores";

// export default function GlobalLoader() {
//     const isLoading = useLoadingStore((s) => s.isLoading);
//     if (!isLoading) return null;

//     return (
//         <>
//             <style>{`
//         @keyframes capPulse {
//           0%, 100% { transform: scaleY(1); }
//           50%       { transform: scaleY(0.7); }
//         }
//         .cap-left  { animation: capPulse 1.4s ease-in-out infinite; }
//         .cap-right { animation: capPulse 1.4s ease-in-out infinite 0.2s; }
//       `}</style>

//             <Box
//                 sx={{
//                     position: "fixed",
//                     top: 0, left: 0,
//                     width: "100vw", height: "100vh",
//                     backgroundColor: "rgba(255,255,255,0.75)",
//                     zIndex: 2000,
//                     display: "flex",
//                     flexDirection: "column",
//                     alignItems: "center",
//                     justifyContent: "center",
//                     gap: "14px",
//                 }}
//             >
//                 <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
//                     <div
//                         className="cap-left"
//                         style={{
//                             width: "28px", height: "22px",
//                             borderRadius: "11px 0 0 11px",
//                             background: "#C8102E",
//                         }}
//                     />
//                     <div
//                         className="cap-right"
//                         style={{
//                             width: "28px", height: "22px",
//                             borderRadius: "0 11px 11px 0",
//                             background: "#5A5A5D",
//                         }}
//                     />
//                 </div>

//                 {/* <span
//           style={{
//             fontSize: "11px",
//             letterSpacing: "0.12em",
//             textTransform: "uppercase",
//             color: "#999",
//           }}
//         >
//           GILEAD
//         </span> */}
//             </Box>
//         </>
//     );
// }

// src/components/common/GlobalLoader.jsx
// import React from "react";
// import { Box, CircularProgress } from "@mui/material";
// import { useLoadingStore } from "../../stores";

// export default function GlobalLoader() {
//   const isLoading = useLoadingStore((state) => state.isLoading);

//   if (!isLoading) return null;

//   return (
//     <Box
//       sx={{
//         position: "fixed",
//         top: 0,
//         left: 0,
//         width: "100vw",
//         height: "100vh",
//         // backdropFilter: "blur(2px)",
//         backgroundColor: "rgba(255,255,255,0.6)",
//         zIndex: 2000,
//         display: "flex",
//         alignItems: "center",
//         justifyContent: "center",
//       }}
//     >
//       <CircularProgress size={50} sx={{ color: "#4F46E5" }} />
//     </Box>
//   );
// }