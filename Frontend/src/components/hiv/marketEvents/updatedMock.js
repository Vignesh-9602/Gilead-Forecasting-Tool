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
                "coverage_curve_type": "Linear",
                "coverage_factor": "",
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
                                    "label": "Truvada",
                                    "history": [
                                        34.0,
                                        34.2,
                                        34.5,
                                        34.6,
                                        34.7,
                                        34.8,
                                        35.0,
                                        35.2
                                    ],
                                    "forecast": [
                                        35.3,
                                        35.4,
                                        35.5,
                                        35.6
                                    ]
                                },
                                {
                                    "label": "Descovy",
                                    "history": [
                                        33.0,
                                        32.9,
                                        32.8,
                                        32.8,
                                        32.7,
                                        32.6,
                                        32.5,
                                        32.5
                                    ],
                                    "forecast": [
                                        32.4,
                                        32.4,
                                        32.3,
                                        32.2
                                    ]
                                },
                                {
                                    "label": "Biktarvy",
                                    "history": [
                                        33.0,
                                        32.9,
                                        32.7,
                                        32.6,
                                        32.6,
                                        32.6,
                                        32.5,
                                        32.3
                                    ],
                                    "forecast": [
                                        32.3,
                                        32.2,
                                        32.2,
                                        32.2
                                    ]
                                }
                            ]
                        },
                        "table": {
                            "type": "hierarchy",
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
                                    "label": "Overall",
                                    "values": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
                                },
                                {
                                    "label": "Truvada",
                                    "values": [34.0, 34.2, 34.5, 34.6, 34.7, 34.8, 35.0, 35.2, 35.3, 35.4, 35.5, 35.6],
                                    "children": [
                                        {
                                            "label": "Retail",
                                            "values": [14.0, 14.2, 14.3, 14.5, 14.7, 14.9, 15.0, 15.2, 15.3, 15.5, 15.6, 15.7]
                                        },
                                        {
                                            "label": "Non-retail",
                                            "values": [20.0, 20.0, 20.2, 20.1, 20.0, 19.9, 20.0, 20.0, 20.0, 19.9, 19.9, 19.9]
                                        }
                                    ]
                                },
                                {
                                    "label": "Descovy",
                                    "values": [33.0, 32.9, 32.8, 32.8, 32.7, 32.6, 32.5, 32.5, 32.4, 32.4, 32.3, 32.2],
                                    "children": [
                                        {
                                            "label": "Retail",
                                            "values": [12.5, 12.5, 12.4, 12.4, 12.3, 12.2, 12.2, 12.1, 12.1, 12.0, 12.0, 11.9]
                                        },
                                        {
                                            "label": "Non-retail",
                                            "values": [20.5, 20.4, 20.4, 20.4, 20.4, 20.4, 20.3, 20.4, 20.3, 20.4, 20.3, 20.3]
                                        }
                                    ]
                                },
                                {
                                    "label": "Biktarvy",
                                    "values": [33.0, 32.9, 32.7, 32.6, 32.6, 32.6, 32.5, 32.3, 32.3, 32.2, 32.2, 32.2],
                                    "children": [
                                        {
                                            "label": "Retail",
                                            "values": [13.5, 13.4, 13.3, 13.2, 13.2, 13.1, 13.1, 13.0, 13.0, 12.9, 12.9, 12.8]
                                        },
                                        {
                                            "label": "Non-retail",
                                            "values": [19.5, 19.5, 19.4, 19.4, 19.4, 19.5, 19.4, 19.3, 19.3, 19.3, 19.3, 19.4]
                                        }
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
                                    "label": "Truvada",
                                    "history": [
                                        300000,
                                        302000,
                                        304000,
                                        306000,
                                        308000,
                                        310000,
                                        312000,
                                        314000
                                    ],
                                    "forecast": [
                                        316000,
                                        318000,
                                        320000,
                                        322000
                                    ]
                                },
                                {
                                    "label": "Descovy",
                                    "history": [
                                        290000,
                                        291000,
                                        292000,
                                        293000,
                                        294000,
                                        295000,
                                        296000,
                                        297000
                                    ],
                                    "forecast": [
                                        298000,
                                        299000,
                                        300000,
                                        301000
                                    ]
                                },
                                {
                                    "label": "Biktarvy",
                                    "history": [
                                        310000,
                                        312000,
                                        314000,
                                        316000,
                                        318000,
                                        320000,
                                        322000,
                                        324000
                                    ],
                                    "forecast": [
                                        326000,
                                        328000,
                                        330000,
                                        332000
                                    ]
                                }
                            ]
                        },
                        "table": {
                            "type": "hierarchy",
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
                                    "label": "Overall",
                                    "values": [900000, 905000, 910000, 915000, 920000, 925000, 930000, 935000, 940000, 945000, 950000, 955000]
                                },
                                {
                                    "label": "Truvada",
                                    "values": [300000, 302000, 304000, 306000, 308000, 310000, 312000, 314000, 316000, 318000, 320000, 322000],
                                    "children": [
                                        {
                                            "label": "Retail",
                                            "values": [120000, 121000, 122000, 123000, 124000, 125000, 126000, 127000, 128000, 129000, 130000, 131000]
                                        },
                                        {
                                            "label": "Non-retail",
                                            "values": [180000, 181000, 182000, 183000, 184000, 185000, 186000, 187000, 188000, 189000, 190000, 191000]
                                        }
                                    ]
                                },
                                {
                                    "label": "Descovy",
                                    "values": [290000, 291000, 292000, 293000, 294000, 295000, 296000, 297000, 298000, 299000, 300000, 301000],
                                    "children": [
                                        {
                                            "label": "Retail",
                                            "values": [110000, 111000, 112000, 113000, 114000, 115000, 116000, 117000, 118000, 119000, 120000, 121000]
                                        },
                                        {
                                            "label": "Non-retail",
                                            "values": [180000, 180000, 180000, 180000, 180000, 180000, 180000, 180000, 180000, 180000, 180000, 180000]
                                        }
                                    ]
                                },
                                {
                                    "label": "Biktarvy",
                                    "values": [310000, 312000, 314000, 316000, 318000, 320000, 322000, 324000, 326000, 328000, 330000, 332000],
                                    "children": [
                                        {
                                            "label": "Retail",
                                            "values": [130000, 131000, 132000, 133000, 134000, 135000, 136000, 137000, 138000, 139000, 140000, 141000]
                                        },
                                        {
                                            "label": "Non-retail",
                                            "values": [180000, 181000, 182000, 183000, 184000, 185000, 186000, 187000, 188000, 189000, 190000, 191000]
                                        }
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
                            months: [
                                "Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26",
                                "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"
                            ],
                            forecast_start_index: 8,
                            series: [
                                {
                                    label: "Retail",
                                    history: [40.0, 39.8, 39.6, 39.5, 39.3, 39.2, 39.0, 38.8],
                                    forecast: [38.5, 38.2, 38.0, 37.8]
                                },
                                {
                                    label: "Non-retail",
                                    history: [60.0, 60.2, 60.4, 60.5, 60.7, 60.8, 61.0, 61.2],
                                    forecast: [61.5, 61.8, 62.0, 62.2]
                                }
                            ]
                        },

                        table: {
                            type: "hierarchy",
                            headers: [
                                "Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26",
                                "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"
                            ],
                            forecast_start_index: 8,
                            editable: true,
                            rows: [
                                {
                                    "label": "Overall",
                                    "values": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
                                },
                                {
                                    label: "Retail",
                                    values: [40.0, 39.8, 39.6, 39.5, 39.3, 39.2, 39.0, 38.8, 38.5, 38.2, 38.0, 37.8],
                                    children: [
                                        {
                                            label: "Truvada",
                                            values: [18.0, 17.9, 17.8, 17.7, 17.6, 17.5, 17.4, 17.3, 17.1, 17.0, 16.9, 16.8]
                                        },
                                        {
                                            label: "Descovy",
                                            values: [22.0, 21.9, 21.8, 21.8, 21.7, 21.7, 21.6, 21.5, 21.4, 21.2, 21.1, 21.0]
                                        }
                                    ]
                                },
                                {
                                    label: "Non-retail",
                                    values: [60.0, 60.2, 60.4, 60.5, 60.7, 60.8, 61.0, 61.2, 61.5, 61.8, 62.0, 62.2],
                                    children: [
                                        {
                                            label: "Truvada",
                                            values: [25.0, 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.9, 26.0, 26.1, 26.2]
                                        },
                                        {
                                            label: "Descovy",
                                            values: [35.0, 35.1, 35.2, 35.2, 35.3, 35.3, 35.4, 35.5, 35.6, 35.8, 35.9, 36.0]
                                        }
                                    ]
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
                            months: [
                                "Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26",
                                "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"
                            ],
                            forecast_start_index: 8,
                            series: [
                                {
                                    label: "Retail",
                                    history: [36000, 35800, 35600, 35400, 35200, 35000, 34800, 34600],
                                    forecast: [34400, 34200, 34000, 33800]
                                },
                                {
                                    label: "Non-retail",
                                    history: [54000, 54200, 54400, 54600, 54800, 55000, 55200, 55400],
                                    forecast: [55600, 55800, 56000, 56200]
                                }
                            ]
                        },

                        table: {
                            type: "hierarchy",
                            headers: [
                                "Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26",
                                "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"
                            ],
                            forecast_start_index: 8,
                            editable: true,
                            rows: [
                                {
                                    "label": "Overall",
                                    "values": [900000, 905000, 910000, 915000, 920000, 925000, 930000, 935000, 940000, 945000, 950000, 955000]
                                },
                                {
                                    label: "Retail",
                                    values: [
                                        36000, 35800, 35600, 35400, 35200, 35000,
                                        34800, 34600, 34400, 34200, 34000, 33800
                                    ],
                                    children: [
                                        {
                                            label: "Truvada",
                                            values: [
                                                15000, 14900, 14800, 14700, 14600, 14500,
                                                14400, 14300, 14200, 14100, 14000, 13900
                                            ]
                                        },
                                        {
                                            label: "Descovy",
                                            values: [
                                                21000, 20900, 20800, 20700, 20600, 20500,
                                                20400, 20300, 20200, 20100, 20000, 19900
                                            ]
                                        }
                                    ]
                                },
                                {
                                    label: "Non-retail",
                                    values: [
                                        54000, 54200, 54400, 54600, 54800, 55000,
                                        55200, 55400, 55600, 55800, 56000, 56200
                                    ],
                                    children: [
                                        {
                                            label: "Truvada",
                                            values: [
                                                22000, 22100, 22200, 22300, 22400, 22500,
                                                22600, 22700, 22800, 22900, 23000, 23100
                                            ]
                                        },
                                        {
                                            label: "Descovy",
                                            values: [
                                                32000, 32100, 32200, 32300, 32400, 32500,
                                                32600, 32700, 32800, 32900, 33000, 33100
                                            ]
                                        }
                                    ]
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
                            headers: [
                                "Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26",
                                "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"
                            ],
                            forecast_start_index: 1,
                            editable: true,
                            rows: [
                                {
                                    label: "Overall",
                                    values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,]
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
                            headers: [
                                "Jan-26", "Feb-26", "Mar-26", "Apr-26", "May-26", "Jun-26",
                                "Jul-26", "Aug-26", "Sep-26", "Oct-26", "Nov-26", "Dec-26"
                            ],
                            forecast_start_index: 1,
                            editable: true,
                            rows: [
                                {
                                    label: "Overall Market",
                                    values: [900000, 905000, 910000, 915000, 920000, 925000, 930000, 935000, 940000, 945000, 950000, 955000]
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