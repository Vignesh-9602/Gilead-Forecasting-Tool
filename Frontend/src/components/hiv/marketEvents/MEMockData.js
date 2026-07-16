export const marketEventMock = {
    ta_name: "HIV Treatment",

    available_scenarios: ["BASE", "Test Scenario", "Scenario 2"],

    available_months: [
        "2024-06-01",
        "2024-07-01",
        "2024-08-01",
        "2024-09-01",
        "2024-10-01",
        "2024-11-01",
        "2024-12-01",
        "2025-01-01",
        "2025-02-01",
        "2025-03-01",
        "2025-04-01",
        "2025-05-01"
    ],

    selected_filter: {
        scenario_name: "BASE",
        markets: ["Retail"],
        products: ["Truvada"],
        start_date: "2024-06-01",
        end_date: "2025-05-01"
    },

    metric_filters: [
        {
            label: "Market Share",
            value: "market_share"
        },
        {
            label: "Overall Market Volume",
            value: "market_volume"
        }
    ],

    event_tabs: {
        "market_event": {

            "impact_curve_configuration": {
                "products": [
                    "Truvada",
                    "Descovy"
                ],
                "markets": [
                    "Retail",
                    "Non-retail"
                ],
                "impact_markets": [
                    "Retail",
                    "Non-retail"
                ],
                "forecast_start_date": "2026-03-01",
                "curve_types": [
                    "Linear",
                    "Exponential",
                    "Logarithmic",
                    "SCurve"
                ],
                "rows": []
            },

            "metrics_views": {

                "market_share": {

                    "monthly": {
                        "chart": {
                            "months": [
                                "Jan-26",
                                "Feb-26",
                                "Mar-26",
                                "Apr-26",
                                "May-26",
                                "Jun-26",
                                "Jul-26",
                                "Aug-26",
                                "Sep-26",
                                "Oct-26",
                                "Nov-26",
                                "Dec-26"
                            ],
                            "forecast_start_index": 8,
                            "series": [
                                {
                                    "label": "Retail",
                                    "history": [
                                        22.0,
                                        22.5,
                                        23.0,
                                        23.5,
                                        24.0,
                                        24.5,
                                        25.0,
                                        25.5
                                    ],
                                    "forecast": [
                                        26.0,
                                        26.5,
                                        27.0,
                                        27.5
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "history": [
                                        78.0,
                                        77.5,
                                        77.0,
                                        76.5,
                                        76.0,
                                        75.5,
                                        75.0,
                                        74.5
                                    ],
                                    "forecast": [
                                        74.0,
                                        73.5,
                                        73.0,
                                        72.5
                                    ]
                                }
                            ]
                        },
                        "table": {
                            "headers": [
                                "Jan-26",
                                "Feb-26",
                                "Mar-26",
                                "Apr-26",
                                "May-26",
                                "Jun-26",
                                "Jul-26",
                                "Aug-26",
                                "Sep-26",
                                "Oct-26",
                                "Nov-26",
                                "Dec-26"
                            ],
                            "forecast_start_index": 8,
                            "editable": true,
                            "rows": [
                                {
                                    "label": "Retail",
                                    "values": [
                                        22.0,
                                        22.5,
                                        23.0,
                                        23.5,
                                        24.0,
                                        24.5,
                                        25.0,
                                        25.5,
                                        26.0,
                                        26.5,
                                        27.0,
                                        27.5
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "values": [
                                        78.0,
                                        77.5,
                                        77.0,
                                        76.5,
                                        76.0,
                                        75.5,
                                        75.0,
                                        74.5,
                                        74.0,
                                        73.5,
                                        73.0,
                                        72.5
                                    ]
                                }
                            ]
                        }
                    },

                    "yearly": {

                        "chart": {
                            "years": [
                                "2026",
                                "2027",
                                "2028"
                            ],
                            "forecast_start_index": 0,
                            "series": [
                                {
                                    "label": "Retail",
                                    "history": [],
                                    "forecast": [
                                        26,
                                        28,
                                        30
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "history": [],
                                    "forecast": [
                                        74,
                                        72,
                                        70
                                    ]
                                }
                            ]
                        },

                        "table": {
                            "headers": [
                                "2026",
                                "2027",
                                "2028"
                            ],
                            "forecast_start_index": 0,
                            "editable": true,
                            "rows": [
                                {
                                    "label": "Retail",
                                    "values": [
                                        26,
                                        28,
                                        30
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "values": [
                                        74,
                                        72,
                                        70
                                    ]
                                }
                            ]
                        }

                    }

                },

                "market_volume": {

                    "monthly": {
                        "chart": {
                            "months": [
                                "Jan-26",
                                "Feb-26",
                                "Mar-26",
                                "Apr-26",
                                "May-26",
                                "Jun-26",
                                "Jul-26",
                                "Aug-26",
                                "Sep-26",
                                "Oct-26",
                                "Nov-26",
                                "Dec-26"
                            ],
                            "forecast_start_index": 8,
                            "series": [
                                {
                                    "label": "Retail",
                                    "history": [
                                        220000,
                                        280000,
                                        240000,
                                        320000,
                                        260000,
                                        270000,
                                        400000,
                                        290000
                                    ],
                                    "forecast": [
                                        300000,
                                        315000,
                                        330000,
                                        345000
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "history": [
                                        780000,
                                        775000,
                                        770000,
                                        765000,
                                        760000,
                                        755000,
                                        750000,
                                        745000
                                    ],
                                    "forecast": [
                                        740000,
                                        735000,
                                        730000,
                                        725000
                                    ]
                                }
                            ]
                        },
                        "table": {
                            "headers": [
                                "Jan-26",
                                "Feb-26",
                                "Mar-26",
                                "Apr-26",
                                "May-26",
                                "Jun-26",
                                "Jul-26",
                                "Aug-26",
                                "Sep-26",
                                "Oct-26",
                                "Nov-26",
                                "Dec-26"
                            ],
                            "forecast_start_index": 8,
                            "editable": true,
                            "rows": [
                                {
                                    "label": "Retail",
                                    "values": [
                                        220000,
                                        400000,
                                        240000,
                                        320000,
                                        260000,
                                        270000,
                                        280000,
                                        290000,
                                        300000,
                                        315000,
                                        330000,
                                        345000
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "values": [
                                        780000,
                                        775000,
                                        770000,
                                        765000,
                                        760000,
                                        755000,
                                        750000,
                                        745000,
                                        740000,
                                        735000,
                                        730000,
                                        725000
                                    ]
                                }
                            ]
                        }
                    },

                    "yearly": {

                        "chart": {
                            "years": [
                                "2026",
                                "2027",
                                "2028"
                            ],
                            "forecast_start_index": 0,
                            "series": [
                                {
                                    "label": "Retail",
                                    "history": [],
                                    "forecast": [
                                        270000,
                                        285000,
                                        300000
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "history": [],
                                    "forecast": [
                                        810000,
                                        795000,
                                        780000
                                    ]
                                }
                            ]
                        },

                        "table": {
                            "headers": [
                                "2026",
                                "2027",
                                "2028"
                            ],
                            "forecast_start_index": 0,
                            "editable": true,
                            "rows": [
                                {
                                    "label": "Retail",
                                    "values": [
                                        270000,
                                        285000,
                                        300000
                                    ]
                                },
                                {
                                    "label": "Non-retail",
                                    "values": [
                                        810000,
                                        795000,
                                        780000
                                    ]
                                }
                            ]
                        }

                    }

                }

            }

        },

        product_event: {
            impact_curve_configuration: {
                products: ["Truvada", "Descovy"],
                markets: ["Retail", "Non-retail"],
                impact_products: ["Truvada", "Descovy"],
                forecast_start_date: "2026-03-01",
                curve_types: [
                    "Linear",
                    "Exponential",
                    "Logarithmic",
                    "SCurve"
                ],
                rows: []
            },

            metrics_views: {
                market_share: {
                    monthly: {
                        chart: {
                            months: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            series: [
                                {
                                    label: "Truvada",
                                    history: [40],
                                    forecast: [39, 38]
                                },
                                {
                                    label: "Descovy",
                                    history: [60],
                                    forecast: [61, 62]
                                }
                            ]
                        },
                        table: {
                            headers: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            editable: true,
                            rows: [
                                {
                                    label: "Truvada",
                                    values: [40, 39, 38]
                                },
                                {
                                    label: "Descovy",
                                    values: [60, 61, 62]
                                }
                            ]
                        }
                    },

                    yearly: {
                        chart: {
                            years: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            series: [
                                {
                                    label: "Truvada",
                                    history: [],
                                    forecast: [38, 35, 33]
                                },
                                {
                                    label: "Descovy",
                                    history: [],
                                    forecast: [62, 65, 67]
                                }
                            ]
                        },
                        table: {
                            headers: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            editable: true,
                            rows: [
                                {
                                    label: "Truvada",
                                    values: [38, 35, 33]
                                },
                                {
                                    label: "Descovy",
                                    values: [62, 65, 67]
                                }
                            ]
                        }
                    }
                },

                market_volume: {
                    monthly: {
                        chart: {
                            months: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            series: [
                                {
                                    label: "Truvada",
                                    history: [36000],
                                    forecast: [35000, 34000]
                                },
                                {
                                    label: "Descovy",
                                    history: [54000],
                                    forecast: [55000, 56000]
                                }
                            ]
                        },
                        table: {
                            headers: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            editable: true,
                            rows: [
                                {
                                    label: "Truvada",
                                    values: [36000, 35000, 34000]
                                },
                                {
                                    label: "Descovy",
                                    values: [54000, 55000, 56000]
                                }
                            ]
                        }
                    },

                    yearly: {
                        chart: {
                            years: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            series: [
                                {
                                    label: "Truvada",
                                    history: [],
                                    forecast: [420000, 400000, 380000]
                                },
                                {
                                    label: "Descovy",
                                    history: [],
                                    forecast: [660000, 680000, 700000]
                                }
                            ]
                        },
                        table: {
                            headers: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            editable: true,
                            rows: [
                                {
                                    label: "Truvada",
                                    values: [420000, 400000, 380000]
                                },
                                {
                                    label: "Descovy",
                                    values: [660000, 680000, 700000]
                                }
                            ]
                        }
                    }
                }
            }
        },

        overall_event: {
            impact_curve_configuration: {
                forecast_start_date: "2026-03-01",
                curve_types: [
                    "Linear",
                    "Exponential",
                    "Logarithmic",
                    "SCurve"
                ],
                rows: []
            },

            metrics_views: {
                market_share: {
                    monthly: {
                        chart: {
                            months: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            series: [
                                {
                                    label: "Overall",
                                    history: [100],
                                    forecast: [100, 100]
                                }
                            ]
                        },
                        table: {
                            headers: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            editable: true,
                            rows: [
                                {
                                    label: "Overall",
                                    values: [100, 100, 100]
                                }
                            ]
                        }
                    },

                    yearly: {
                        chart: {
                            years: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            series: [
                                {
                                    label: "Overall",
                                    history: [],
                                    forecast: [100, 100, 100]
                                }
                            ]
                        },
                        table: {
                            headers: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            editable: true,
                            rows: [
                                {
                                    label: "Overall",
                                    values: [100, 100, 100]
                                }
                            ]
                        }
                    }
                },

                market_volume: {
                    monthly: {
                        chart: {
                            months: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            series: [
                                {
                                    label: "Overall Market",
                                    history: [90000],
                                    forecast: [90000, 90000]
                                }
                            ]
                        },
                        table: {
                            headers: ["Jan-26", "Feb-26", "Mar-26"],
                            forecast_start_index: 1,
                            editable: true,
                            rows: [
                                {
                                    label: "Overall Market",
                                    values: [90000, 90000, 90000]
                                }
                            ]
                        }
                    },

                    yearly: {
                        chart: {
                            years: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            series: [
                                {
                                    label: "Overall Market",
                                    history: [],
                                    forecast: [1080000, 1080000, 1080000]
                                }
                            ]
                        },
                        table: {
                            headers: ["2026", "2027", "2028"],
                            forecast_start_index: 0,
                            editable: true,
                            rows: [
                                {
                                    label: "Overall Market",
                                    values: [1080000, 1080000, 1080000]
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
};