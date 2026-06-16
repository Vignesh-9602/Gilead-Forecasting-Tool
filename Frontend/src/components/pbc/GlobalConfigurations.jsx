import React from "react";
import { Box, Paper, Typography } from "@mui/material";

export default function PBCGlobalConfigurations() {
    return (
        <Box p={2}>
            <Paper sx={{ p: 3 }}>
                <Typography variant="h6">
                    PBC Global Configurations
                </Typography>

                {/* <Typography sx={{ mt: 2 }}>
                    PBC configuration screen under development.
                </Typography> */}
            </Paper>
        </Box>
    );
}