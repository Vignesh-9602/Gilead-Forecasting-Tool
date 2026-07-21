import React, { useState } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
} from "@mui/material";
// import AnalysisChart from "./AnalysisChart";
import OutputChart from "./OutputChart";
import OutputTable from "./OutputTable";

const TABS = [
    { label: "Total Market Volume", value: "total_payer_volume" },
    { label: "Payer Distribution (%)", value: "payer_distribution" },
    { label: "Product Distribution (%)", value: "product_distribution" },
    { label: "Payer-Product", value: "payer_product" },
    { label: "Product-Payer", value: "product_payer" },
];

const DEFAULT_METRIC_BY_TAB = {
    total_payer_volume: "payer_volume",
    payer_distribution: "payer_share",
    product_distribution: "payer_share",
    payer_product: "payer_volume",
    product_payer: "payer_volume",
};

// Converts the API/mock row shape ({ label, target_metric, values, children })
// into what the current OutputTable component expects
// ({ key, label, metricLabel, values, rowType, children }).
const transformTableRows = (rows = [], parentKey = "row") =>
    rows.map((row, index) => {
        const key = `${parentKey}-${index}`;
        const hasChildren = Array.isArray(row.children) && row.children.length > 0;
        const isTotal = row.label?.toLowerCase().includes("grand total");

        return {
            key,
            label: row.label,
            metricLabel: row.target_metric,
            values: row.values,
            rowType: isTotal ? "total" : hasChildren ? "group" : "child",
            children: hasChildren ? transformTableRows(row.children, key) : undefined,
        };
    });

export default function OutputAnalysis({ outputAnalysis, selectedPayer, selectedProduct }) {
    const [activeTab, setActiveTab] = useState("total_payer_volume");
    const [selectedMetric, setSelectedMetric] = useState("payer_volume");
    const [viewMode, setViewMode] = useState("monthly");

    const currentData = outputAnalysis?.[activeTab]?.[selectedMetric]?.[viewMode];
    const hasData = !!(currentData?.chart?.series?.length || currentData?.table?.rows?.length);

    // Table headers minus the leading "Metric" column, since OutputTable
    // renders its own first two columns (pivotLabel + Target Metric).
    const tableHeaders = currentData?.table?.headers?.slice(1) || [];
    const tableRows = transformTableRows(currentData?.table?.rows);

    const activeTabLabel = TABS.find((t) => t.value === activeTab)?.label || "Output Table";


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
                    <OutputChart
                        chartData={currentData.chart}
                        activeTab={activeTab}
                        selectedPayer={selectedPayer}
                        selectedProduct={selectedProduct}
                    />
                    <Box
                        sx={{
                            display: "flex",
                            justifyContent: "flex-end",
                            alignItems: "center",
                            gap: 2,
                            mt: 3,
                            mb: 1,
                        }}
                    >
                        <Box
                            sx={{
                                display: "flex",
                                backgroundColor: "#E2E8F0",
                                borderRadius: "8px",
                                p: "2px",
                            }}
                        >
                            {[
                                { label: "Monthly", value: "monthly" },
                                { label: "Yearly", value: "yearly" },
                            ].map((tab) => (
                                <Box
                                    key={tab.value}
                                    onClick={() => setViewMode(tab.value)}
                                    sx={{
                                        px: 2,
                                        py: 0.8,
                                        cursor: "pointer",
                                        fontSize: "13px",
                                        fontWeight: 600,
                                        borderRadius: "6px",
                                        backgroundColor: viewMode === tab.value ? "#fff" : "transparent",
                                        color: viewMode === tab.value ? "#4F46E5" : "#64748B",
                                        transition: ".2s",
                                    }}
                                >
                                    {tab.label}
                                </Box>
                            ))}
                        </Box>

                        <FormControl
                            size="small"
                            sx={{
                                minWidth: 220,
                                "& .MuiOutlinedInput-root": {
                                    height: "35px",
                                    borderRadius: "8px",
                                    background: "#fff",
                                },
                            }}
                        >
                            <Select
                                value={selectedMetric}
                                onChange={(e) => setSelectedMetric(e.target.value)}
                            >
                                <MenuItem value="payer_volume">Payer Volume</MenuItem>
                                <MenuItem value="payer_share">Payer Share</MenuItem>
                            </Select>
                        </FormControl>
                    </Box>

                    <OutputTable
                        pivotLabel={activeTabLabel}
                        headers={tableHeaders}
                        rows={tableRows}
                        metric={selectedMetric}
                    />
                </Box>
                :
                <Paper sx={{ m: 3, minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "none" }}>
                    <Typography>No Output Analysis Available</Typography>
                </Paper>}
        </Paper>
    );
}