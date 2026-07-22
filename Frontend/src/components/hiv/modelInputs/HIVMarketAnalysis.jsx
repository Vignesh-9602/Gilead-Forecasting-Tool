import React, { useState, useEffect } from "react";

import {
    Box,
    Paper,
    Typography,
} from "@mui/material";

import HIVMarketChart from "./HIVMarketChart";
import HIVMarketTable from "./HIVMarketTable";

// import { mockData } from "./mockData";
// import { mockData } from "./newMockData";

const TABS = [
    {
        label: "Total Market Volume",
        value: "total_market_volume",
    },
    {
        label: "Channel Distribution (%)",
        value: "market_distribution",
    },
    {
        label: "Product Distribution (%)",
        value: "product_distribution",
    },
    {
        label: "Channel-Product",
        value: "market_product",
    },
    {
        label: "Product-Channel",
        value: "product_market",
    },
];

export default function HIVMarketAnalysis({
    marketAnalysis,
    allScenariosData,
    availableScenarios,
    activeScenario,
    selectedMarket,
    selectedProduct,
    onTabChange,
    selectedMetric,
    setSelectedMetric,
    onEdit,
    onSaveScenario,
    onApplyScenario,
    onUpdateScenario
}) {

    const DEFAULT_METRIC_BY_TAB = {
        total_market_volume: "market_volume",
        market_distribution: "market_share",
        product_distribution: "market_share",
        market_product: "market_volume",
        product_market: "market_volume",
    };

    const [activeTab, setActiveTab] = useState(
        "total_market_volume"
    );

    // const [selectedMetric, setSelectedMetric] = useState(
    //     DEFAULT_METRIC_BY_TAB.total_market_volume
    // );

    const [viewMode, setViewMode] = useState("monthly");

    const [compareScenario, setCompareScenario] = useState([]);

    useEffect(() => {
        setCompareScenario(availableScenarios);
    }, [availableScenarios]);

    // const currentData =
    //     mockData[activeTab]?.[selectedMetric];

    const currentData =
        marketAnalysis?.[activeTab]?.[selectedMetric]?.[viewMode];

    // if (!currentData) {
    //     return null;
    // }

    const hasData =
        !!currentData?.chart?.series?.length &&
        !!currentData?.table?.rows?.length;

    const chartData =
        activeTab === "total_market_volume"
            ? (() => {
                const scenarios = compareScenario
                    .map(name => allScenariosData?.[name])
                    .filter(Boolean);

                if (!scenarios.length) {
                    return currentData?.chart;
                }

                const firstChart =
                    scenarios[0]?.market_analysis?.total_market_volume?.[selectedMetric]?.[viewMode]?.chart;

                return {
                    ...firstChart,
                    series: scenarios.flatMap(
                        (scenario) =>
                            scenario?.market_analysis?.total_market_volume?.[selectedMetric]?.[viewMode]?.chart?.series || []
                    ),
                };
            })()
            : currentData?.chart;

    return (
        <Paper
            sx={{
                mt: 3,
                borderRadius: "16px",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
                overflow: "hidden",
            }}
        >
            {/* Header */}

            <Box
                sx={{
                    px: 3,
                    pt: 3,
                }}
            >
                <Typography
                    sx={{
                        fontSize: "18px",
                        fontWeight: 700,
                        color: "#0F172A",
                    }}
                >
                    Market Analysis
                </Typography>

                {/* <Typography
                    sx={{
                        color: "#64748B",
                        fontSize: "14px",
                        mt: 0.5,
                    }}
                >
                    Analyze market and product level trends.
                </Typography> */}
            </Box>

            {/* ---------- Custom Tabs ---------- */}

            <Box
                sx={{
                    mt: 2,
                    backgroundColor: "#e2e8f0",
                    borderBottom: "1px solid #D8DEE8",
                    px: 0.5,
                    pt: 0.5,
                    display: "flex",
                    gap: 0.5,
                    overflowX: "auto",

                    "&::-webkit-scrollbar": {
                        height: 6,
                    },
                }}
            >
                {TABS.map((tab) => (
                    <Box
                        key={tab.value}
                        onClick={() => {
                            setActiveTab(tab.value);
                            setSelectedMetric(DEFAULT_METRIC_BY_TAB[tab.value]);
                            onTabChange?.(tab.value);
                        }}
                        sx={{
                            px: 2,
                            py: 1,
                            cursor: "pointer",

                            fontSize: "12px",

                            fontWeight: 600,

                            whiteSpace: "nowrap",

                            borderRadius:
                                "6px 6px 0 0",

                            color:
                                activeTab === tab.value
                                    ? "#4F46E5"
                                    : "#64748b",

                            backgroundColor:
                                activeTab === tab.value
                                    ? "white"
                                    : "transparent",

                            border:
                                activeTab === tab.value
                                    ? "1px solid #D8DEE8"
                                    : "1px solid transparent",

                            borderBottom:
                                activeTab === tab.value
                                    ? "1px solid white"
                                    : "1px solid transparent",

                            mb:
                                activeTab === tab.value
                                    ? "-1px"
                                    : 0,

                            transition: ".2s",

                            userSelect: "none",

                            "&:hover": {
                                backgroundColor:
                                    activeTab ===
                                        tab.value
                                        ? "white"
                                        : "#f1f5f9",
                            },
                        }}
                    >
                        {tab.label}
                    </Box>
                ))}
            </Box>

            {hasData ? (
                <>

                    {/* ---------- Chart ---------- */}

                    <Box
                        sx={{
                            p: 3,
                        }}
                    >

                        <HIVMarketChart
                            chartData={chartData}
                            activeTab={activeTab}
                            selectedMarket={selectedMarket}
                            selectedProduct={selectedProduct}
                        />
                    </Box>

                    {/* ---------- Table ---------- */}

                    <Box
                        sx={{
                            px: 3,
                            pb: 3,
                        }}
                    >
                        <HIVMarketTable
                            activeTab={activeTab}
                            tableData={currentData?.table}
                            selectedMetric={selectedMetric}
                            months={
                                currentData?.chart?.months ||
                                currentData?.chart?.years ||
                                []
                            }
                            setSelectedMetric={setSelectedMetric}
                            forecastStartIndex={
                                currentData?.chart?.forecast_start_index
                            }
                            availableScenarios={availableScenarios}
                            activeScenario={activeScenario}
                            selectedMarket={selectedMarket}
                            selectedProduct={selectedProduct}
                            viewMode={viewMode}
                            setViewMode={setViewMode}
                            marketAnalysis={marketAnalysis}
                            onEdit={onEdit}
                            onSaveScenario={onSaveScenario}
                            onApplyScenario={onApplyScenario}
                            allScenariosData={allScenariosData}
                            onUpdateScenario={onUpdateScenario}
                            compareScenario={compareScenario}
                            setCompareScenario={setCompareScenario}
                        />
                    </Box>
                </>
            ) : (
                <Paper
                    sx={{
                        m: 3,
                        border: "1px dashed #CBD5E1",
                        borderRadius: "12px",
                        boxShadow: "none",
                        minHeight: 300,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        backgroundColor: "#F8FAFC",
                    }}
                >
                    <Box
                        sx={{
                            textAlign: "center",
                        }}
                    >
                        <Typography
                            sx={{
                                fontSize: 18,
                                fontWeight: 700,
                                color: "#334155",
                            }}
                        >
                            No Market Analysis Available
                        </Typography>

                        <Typography
                            sx={{
                                mt: 1,
                                color: "#64748B",
                                fontSize: 14,
                            }}
                        >
                            Click <b>Apply Filter</b> to load the market analysis chart
                            and table.
                        </Typography>
                    </Box>
                </Paper>
            )}
        </Paper>
    );
}