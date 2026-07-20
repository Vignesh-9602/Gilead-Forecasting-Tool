export const mockOutputData = {
    "selected_filter": {
        "scenario_names": [
            "Base",
            "Optimistic Growth"
        ],
        "markets": [
            "Retail",
            "Non-retail"
        ],
        "products": [
            "Truvada",
            "Descovy"
        ],
        "start_date": "2024-06-01",
        "end_date": "2026-12-01"
    },
    "metric_filters": [
        {
            "label": "Market Volume",
            "value": "market_volume"
        },
        {
            "label": "Market Share",
            "value": "market_share"
        }
    ],
    "selected_metric": "market_volume",
    "view_options": [
        {
            "label": "Monthly",
            "value": "monthly"
        },
        {
            "label": "Yearly",
            "value": "yearly"
        }
    ],
    "selected_view": "monthly",
    "output_tabs": {
        "total_market_volume": {
            "market_volume": {
                "monthly": {
                    "chart": {
                        "months": [
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "forecast_start_index": 2,
                        "series": [
                            {
                                "label": "Base",
                                "history": [
                                    420,
                                    440
                                ],
                                "forecast": [
                                    460,
                                    480
                                ]
                            },
                            {
                                "label": "Optimistic Growth",
                                "history": [
                                    483,
                                    505
                                ],
                                "forecast": [
                                    530,
                                    551
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    420,
                                    440,
                                    460,
                                    480
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    483,
                                    505,
                                    530,
                                    551
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {
                        "months": [
                            "2025",
                            "2026"
                        ],
                        "forecast_start_index": 1,
                        "series": [
                            {
                                "label": "Base",
                                "history": [
                                    4880
                                ],
                                "forecast": [
                                    5480
                                ]
                            },
                            {
                                "label": "Optimistic Growth",
                                "history": [
                                    5612
                                ],
                                "forecast": [
                                    6302
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    4880,
                                    5480
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    5612,
                                    6302
                                ]
                            }
                        ]
                    }
                }
            },
            "market_share": {
                "monthly": {
                    "chart": {
                        "months": [
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "forecast_start_index": 2,
                        "series": [
                            {
                                "label": "Base",
                                "history": [
                                    100.0,
                                    100.0
                                ],
                                "forecast": [
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Optimistic Growth",
                                "history": [
                                    100.0,
                                    100.0
                                ],
                                "forecast": [
                                    100.0,
                                    100.0
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {
                        "months": [
                            "2025",
                            "2026"
                        ],
                        "forecast_start_index": 1,
                        "series": [
                            {
                                "label": "Base",
                                "history": [
                                    100.0
                                ],
                                "forecast": [
                                    100.0
                                ]
                            },
                            {
                                "label": "Optimistic Growth",
                                "history": [
                                    100.0
                                ],
                                "forecast": [
                                    100.0
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ]
                            }
                        ]
                    }
                }
            }
        },
        "market_distribution": {
            "market_volume": {
                "monthly": {
                    "chart": {
                        "months": [
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "forecast_start_index": 2,
                        "series": [
                            {
                                "label": "Retail (Base)",
                                "history": [
                                    320,
                                    335
                                ],
                                "forecast": [
                                    350,
                                    365
                                ]
                            },
                            {
                                "label": "Non-retail (Base)",
                                "history": [
                                    100,
                                    105
                                ],
                                "forecast": [
                                    110,
                                    115
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth)",
                                "history": [
                                    368,
                                    385
                                ],
                                "forecast": [
                                    403,
                                    419
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth)",
                                "history": [
                                    115,
                                    120
                                ],
                                "forecast": [
                                    127,
                                    132
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    420,
                                    440,
                                    460,
                                    480
                                ]
                            },
                            {
                                "label": "Retail (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    320,
                                    335,
                                    350,
                                    365
                                ]
                            },
                            {
                                "label": "Non-retail (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    100,
                                    105,
                                    110,
                                    115
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    483,
                                    505,
                                    530,
                                    551
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    368,
                                    385,
                                    403,
                                    419
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    115,
                                    120,
                                    127,
                                    132
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {
                        "months": [
                            "2025",
                            "2026"
                        ],
                        "forecast_start_index": 1,
                        "series": [
                            {
                                "label": "Retail (Base)",
                                "history": [
                                    3700
                                ],
                                "forecast": [
                                    4200
                                ]
                            },
                            {
                                "label": "Non-retail (Base)",
                                "history": [
                                    1180
                                ],
                                "forecast": [
                                    1280
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth)",
                                "history": [
                                    4255
                                ],
                                "forecast": [
                                    4830
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth)",
                                "history": [
                                    1357
                                ],
                                "forecast": [
                                    1472
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    4880,
                                    5480
                                ]
                            },
                            {
                                "label": "Retail (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    3700,
                                    4200
                                ]
                            },
                            {
                                "label": "Non-retail (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    1180,
                                    1280
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    5612,
                                    6302
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    4255,
                                    4830
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    1357,
                                    1472
                                ]
                            }
                        ]
                    }
                }
            },
            "market_share": {
                "monthly": {
                    "chart": {
                        "months": [
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "forecast_start_index": 2,
                        "series": [
                            {
                                "label": "Retail (Base)",
                                "history": [
                                    320,
                                    335
                                ],
                                "forecast": [
                                    350,
                                    365
                                ]
                            },
                            {
                                "label": "Non-retail (Base)",
                                "history": [
                                    100,
                                    105
                                ],
                                "forecast": [
                                    110,
                                    115
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth)",
                                "history": [
                                    368,
                                    385
                                ],
                                "forecast": [
                                    403,
                                    419
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth)",
                                "history": [
                                    115,
                                    120
                                ],
                                "forecast": [
                                    127,
                                    132
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Retail (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    76.2,
                                    76.1,
                                    76.1,
                                    76.0
                                ]
                            },
                            {
                                "label": "Non-retail (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    23.8,
                                    23.9,
                                    23.9,
                                    24.0
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    76.2,
                                    76.2,
                                    76.0,
                                    76.0
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    23.8,
                                    23.8,
                                    24.0,
                                    24.0
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {
                        "months": [
                            "2025",
                            "2026"
                        ],
                        "forecast_start_index": 1,
                        "series": [
                            {
                                "label": "Retail (Base)",
                                "history": [
                                    3700
                                ],
                                "forecast": [
                                    4200
                                ]
                            },
                            {
                                "label": "Non-retail (Base)",
                                "history": [
                                    1180
                                ],
                                "forecast": [
                                    1280
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth)",
                                "history": [
                                    4255
                                ],
                                "forecast": [
                                    4830
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth)",
                                "history": [
                                    1357
                                ],
                                "forecast": [
                                    1472
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Retail (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    75.8,
                                    76.6
                                ]
                            },
                            {
                                "label": "Non-retail (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    24.2,
                                    23.4
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    75.8,
                                    76.6
                                ]
                            },
                            {
                                "label": "Non-retail (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    24.2,
                                    23.4
                                ]
                            }
                        ]
                    }
                }
            }
        },
        "product_distribution": {
            "market_volume": {
                "monthly": {
                    "chart": {
                        "months": [
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "forecast_start_index": 2,
                        "series": [
                            {
                                "label": "Truvada (Base)",
                                "history": [
                                    160,
                                    167
                                ],
                                "forecast": [
                                    174,
                                    181
                                ]
                            },
                            {
                                "label": "Descovy (Base)",
                                "history": [
                                    260,
                                    273
                                ],
                                "forecast": [
                                    286,
                                    299
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth)",
                                "history": [
                                    184,
                                    192
                                ],
                                "forecast": [
                                    201,
                                    208
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth)",
                                "history": [
                                    299,
                                    313
                                ],
                                "forecast": [
                                    329,
                                    343
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    420,
                                    440,
                                    460,
                                    480
                                ]
                            },
                            {
                                "label": "Truvada (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    160,
                                    167,
                                    174,
                                    181
                                ]
                            },
                            {
                                "label": "Descovy (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    260,
                                    273,
                                    286,
                                    299
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    483,
                                    505,
                                    530,
                                    551
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    184,
                                    192,
                                    201,
                                    208
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    299,
                                    313,
                                    329,
                                    343
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {
                        "months": [
                            "2025",
                            "2026"
                        ],
                        "forecast_start_index": 1,
                        "series": [
                            {
                                "label": "Truvada (Base)",
                                "history": [
                                    1880
                                ],
                                "forecast": [
                                    2120
                                ]
                            },
                            {
                                "label": "Descovy (Base)",
                                "history": [
                                    3000
                                ],
                                "forecast": [
                                    3360
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth)",
                                "history": [
                                    2162
                                ],
                                "forecast": [
                                    2438
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth)",
                                "history": [
                                    3450
                                ],
                                "forecast": [
                                    3864
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    4880,
                                    5480
                                ]
                            },
                            {
                                "label": "Truvada (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    1880,
                                    2120
                                ]
                            },
                            {
                                "label": "Descovy (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    3000,
                                    3360
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    5612,
                                    6302
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    2162,
                                    2438
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    3450,
                                    3864
                                ]
                            }
                        ]
                    }
                }
            },
            "market_share": {
                "monthly": {
                    "chart": {
                        "months": [
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "forecast_start_index": 2,
                        "series": [
                            {
                                "label": "Truvada (Base)",
                                "history": [
                                    160,
                                    167
                                ],
                                "forecast": [
                                    174,
                                    181
                                ]
                            },
                            {
                                "label": "Descovy (Base)",
                                "history": [
                                    260,
                                    273
                                ],
                                "forecast": [
                                    286,
                                    299
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth)",
                                "history": [
                                    184,
                                    192
                                ],
                                "forecast": [
                                    201,
                                    208
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth)",
                                "history": [
                                    299,
                                    313
                                ],
                                "forecast": [
                                    329,
                                    343
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Truvada (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    38.1,
                                    38.0,
                                    37.8,
                                    37.7
                                ]
                            },
                            {
                                "label": "Descovy (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    61.9,
                                    62.0,
                                    62.2,
                                    62.3
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    38.1,
                                    38.0,
                                    37.9,
                                    37.7
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    61.9,
                                    62.0,
                                    62.1,
                                    62.3
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {
                        "months": [
                            "2025",
                            "2026"
                        ],
                        "forecast_start_index": 1,
                        "series": [
                            {
                                "label": "Truvada (Base)",
                                "history": [
                                    1880
                                ],
                                "forecast": [
                                    2120
                                ]
                            },
                            {
                                "label": "Descovy (Base)",
                                "history": [
                                    3000
                                ],
                                "forecast": [
                                    3360
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth)",
                                "history": [
                                    2162
                                ],
                                "forecast": [
                                    2438
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth)",
                                "history": [
                                    3450
                                ],
                                "forecast": [
                                    3864
                                ]
                            }
                        ]
                    },
                    "table": {
                        "type": "flat",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Truvada (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    38.5,
                                    38.7
                                ]
                            },
                            {
                                "label": "Descovy (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    61.5,
                                    61.3
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ]
                            },
                            {
                                "label": "Truvada (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    38.5,
                                    38.7
                                ]
                            },
                            {
                                "label": "Descovy (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    61.5,
                                    61.3
                                ]
                            }
                        ]
                    }
                }
            }
        },
        "product_market": {
            "market_volume": {
                "monthly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    420,
                                    440,
                                    460,
                                    480
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            160,
                                            167,
                                            174,
                                            181
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    120,
                                                    125,
                                                    130,
                                                    135
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    40,
                                                    42,
                                                    44,
                                                    46
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            260,
                                            273,
                                            286,
                                            299
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    200,
                                                    210,
                                                    220,
                                                    230
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    60,
                                                    63,
                                                    66,
                                                    69
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    483,
                                    505,
                                    530,
                                    551
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            184,
                                            192,
                                            201,
                                            208
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    138,
                                                    144,
                                                    150,
                                                    155
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    46,
                                                    48,
                                                    51,
                                                    53
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            299,
                                            313,
                                            329,
                                            343
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    230,
                                                    241,
                                                    253,
                                                    264
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    69,
                                                    72,
                                                    76,
                                                    79
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    4880,
                                    5480
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            1880,
                                            2120
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    1400,
                                                    1600
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    480,
                                                    520
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            3000,
                                            3360
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    2300,
                                                    2600
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    700,
                                                    760
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    5612,
                                    6302
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            2162,
                                            2438
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    1610,
                                                    1840
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    552,
                                                    598
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            3450,
                                            3864
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    2645,
                                                    2990
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    805,
                                                    874
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "market_share": {
                "monthly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            38.1,
                                            38.0,
                                            37.8,
                                            37.7
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.6,
                                                    28.4,
                                                    28.3,
                                                    28.1
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.5,
                                                    9.5,
                                                    9.6,
                                                    9.6
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            61.9,
                                            62.0,
                                            62.2,
                                            62.3
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.6,
                                                    47.7,
                                                    47.8,
                                                    47.9
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    14.3,
                                                    14.3,
                                                    14.4
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            38.1,
                                            38.0,
                                            37.9,
                                            37.7
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.6,
                                                    28.5,
                                                    28.3,
                                                    28.1
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.5,
                                                    9.5,
                                                    9.6,
                                                    9.6
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            61.9,
                                            62.0,
                                            62.1,
                                            62.3
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.6,
                                                    47.7,
                                                    47.7,
                                                    47.9
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    14.3,
                                                    14.3,
                                                    14.3
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            38.5,
                                            38.7
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.7,
                                                    29.2
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.8,
                                                    9.5
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            61.5,
                                            61.3
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.1,
                                                    47.4
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    13.9
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Truvada",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            38.5,
                                            38.7
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.7,
                                                    29.2
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.8,
                                                    9.5
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Descovy",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            61.5,
                                            61.3
                                        ],
                                        "children": [
                                            {
                                                "label": "Retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.1,
                                                    47.4
                                                ]
                                            },
                                            {
                                                "label": "Non-retail",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    13.9
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        },
        "market_product": {
            "market_volume": {
                "monthly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    420,
                                    440,
                                    460,
                                    480
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            320,
                                            335,
                                            350,
                                            365
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    120,
                                                    125,
                                                    130,
                                                    135
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    200,
                                                    210,
                                                    220,
                                                    230
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            100,
                                            105,
                                            110,
                                            115
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    40,
                                                    42,
                                                    44,
                                                    46
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    60,
                                                    63,
                                                    66,
                                                    69
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    483,
                                    505,
                                    530,
                                    551
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            368,
                                            385,
                                            403,
                                            419
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    138,
                                                    144,
                                                    150,
                                                    155
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    230,
                                                    241,
                                                    253,
                                                    264
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            115,
                                            120,
                                            127,
                                            132
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    46,
                                                    48,
                                                    51,
                                                    53
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    69,
                                                    72,
                                                    76,
                                                    79
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    4880,
                                    5480
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            3700,
                                            4200
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    1400,
                                                    1600
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    2300,
                                                    2600
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            1180,
                                            1280
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    480,
                                                    520
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    700,
                                                    760
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Volume",
                                "values": [
                                    5612,
                                    6302
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            4255,
                                            4830
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    1610,
                                                    1840
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    2645,
                                                    2990
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Volume",
                                        "values": [
                                            1357,
                                            1472
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    552,
                                                    598
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Volume",
                                                "values": [
                                                    805,
                                                    874
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "market_share": {
                "monthly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2026-05",
                            "2026-06",
                            "2026-07",
                            "2026-08"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            76.2,
                                            76.1,
                                            76.1,
                                            76.0
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.6,
                                                    28.4,
                                                    28.3,
                                                    28.1
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.6,
                                                    47.7,
                                                    47.8,
                                                    47.9
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            23.8,
                                            23.9,
                                            23.9,
                                            24.0
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.5,
                                                    9.5,
                                                    9.6,
                                                    9.6
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    14.3,
                                                    14.3,
                                                    14.4
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0,
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            76.2,
                                            76.2,
                                            76.0,
                                            76.0
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.6,
                                                    28.5,
                                                    28.3,
                                                    28.1
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.6,
                                                    47.7,
                                                    47.7,
                                                    47.9
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            23.8,
                                            23.8,
                                            24.0,
                                            24.0
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.5,
                                                    9.5,
                                                    9.6,
                                                    9.6
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    14.3,
                                                    14.3,
                                                    14.3
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                },
                "yearly": {
                    "chart": {},
                    "table": {
                        "type": "hierarchy",
                        "headers": [
                            "Metric",
                            "2025",
                            "2026"
                        ],
                        "rows": [
                            {
                                "label": "Grand Total (Base Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            75.8,
                                            76.6
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.7,
                                                    29.2
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.1,
                                                    47.4
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            24.2,
                                            23.4
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.8,
                                                    9.5
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    13.9
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "label": "Grand Total (Optimistic Growth Scenario)",
                                "target_metric": "Market Share (%)",
                                "values": [
                                    100.0,
                                    100.0
                                ],
                                "children": [
                                    {
                                        "label": "Retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            75.8,
                                            76.6
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    28.7,
                                                    29.2
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    47.1,
                                                    47.4
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "label": "Non-retail",
                                        "target_metric": "Market Share (%)",
                                        "values": [
                                            24.2,
                                            23.4
                                        ],
                                        "children": [
                                            {
                                                "label": "Truvada",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    9.8,
                                                    9.5
                                                ]
                                            },
                                            {
                                                "label": "Descovy",
                                                "target_metric": "Market Share (%)",
                                                "values": [
                                                    14.3,
                                                    13.9
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
    }
}