
import React, { useState } from "react";
import { Box, Paper, Typography } from "@mui/material";
import HIVOutputChart from "./HIVOutputChart";
import HIVOutputTable from "./HIVOutputTable";

const TABS = [
    { label: "Total Market Volume", value: "total_market_volume" },
    { label: "Market Distribution (%)", value: "market_distribution" },
    { label: "Product Distribution (%)", value: "product_distribution" },
    { label: "Market-Product", value: "market_product" },
    { label: "Product-Market", value: "product_market" },
];

const DEFAULT_METRIC_BY_TAB = {
    total_market_volume: "market_volume",
    market_distribution: "market_share",
    product_distribution: "market_share",
    market_product: "market_volume",
    product_market: "market_volume",
};

export default function HIVOutputAnalysis({ outputAnalysis, selectedMarket, selectedProduct }) {
    const [activeTab, setActiveTab] = useState("total_market_volume");
    const [selectedMetric, setSelectedMetric] = useState("market_volume");
    const [viewMode, setViewMode] = useState("monthly");

    const currentData = outputAnalysis?.[activeTab]?.[selectedMetric]?.[viewMode];
    const hasData = !!currentData?.chart?.series?.length;

    return (
        <Paper sx={{ mt: 3, borderRadius: "16px", border: "1px solid #D8DEE8", boxShadow: "none", overflow: "hidden" }}>
            <Box sx={{ px: 3, pt: 3 }}><Typography sx={{ fontSize: 18, fontWeight: 700 }}>Output Analysis</Typography></Box>
            <Box sx={{ mt: 2, background: "#e2e8f0", borderBottom: "1px solid #D8DEE8", display: "flex", gap: .5, px: .5, pt: .5 }}>
                {TABS.map(tab => (
                    <Box key={tab.value} onClick={() => { setActiveTab(tab.value); setSelectedMetric(DEFAULT_METRIC_BY_TAB[tab.value]); }}
                        sx={{
                            px: 2, py: 1, cursor: "pointer", fontSize: 12, fontWeight: 600, borderRadius: "6px 6px 0 0", whiteSpace: "nowrap",
                            color: activeTab === tab.value ? "#4F46E5" : "#64748b",
                            background: activeTab === tab.value ? "white" : "transparent"
                        }}>
                        {tab.label}
                    </Box>
                ))}
            </Box>
            {hasData ?
                <Box sx={{ p: 3 }}>
                    <HIVOutputChart
                        chartData={currentData.chart}
                        activeTab={activeTab}
                        selectedMarket={selectedMarket}
                        selectedProduct={selectedProduct}
                    />

                    <HIVOutputTable
                        tableData={currentData.table}
                        viewMode={viewMode}
                        setViewMode={setViewMode}
                        selectedMetric={selectedMetric}
                        setSelectedMetric={setSelectedMetric}
                        metricOptions={[
                            {
                                label: "Market Volume",
                                value: "market_volume",
                            },
                            {
                                label: "Market Share",
                                value: "market_share",
                            },
                        ]}
                    />
                </Box>
                :
                <Paper sx={{ m: 3, minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "none" }}>
                    <Typography>No Output Analysis Available</Typography>
                </Paper>}
        </Paper>
    );
}
