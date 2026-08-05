from copy import deepcopy
from fastapi import HTTPException
from app.hiv_prep.services.Model_Input_Service import *

def build_market_distribution_out(
    cur,
    ta,
    scenario,
    total_vals,
    months,
    split_idx,
    start,
    end,
    selected_markets=None,
):
    """
    Market distribution — volume and share split across markets.

    Supports multiple selected markets.

    total_vals:
        Raw floats.

    Yearly market share:
        sum(market volume in year)
        /
        sum(total volume in year)
        * 100

    Source yearly share:
        sum(source volume in year)
        /
        sum(market volume in year)
        * 100
    """

    # ------------------------------------------------------
    # Normalize selected markets
    # ------------------------------------------------------

    if selected_markets is None:
        selected_markets = []

    if isinstance(selected_markets, str):
        selected_markets = [selected_markets]

    selected_market_keys = {
        str(market).strip().lower()
        for market in selected_markets
        if market
        and str(market).strip().lower() != "all"
    }

    def is_selected_market(market_name):
        """
        No selected markets means include all markets.
        """

        if not selected_market_keys:
            return True

        return (
            str(market_name).strip().lower()
            in selected_market_keys
        )

    markets = get_markets(
        cur,
        ta,
    )

    n = len(total_vals)
    all_years = get_ordered_years(months)

    vol_chart_series = []
    share_chart_series = []

    market_vol_rows = []
    market_share_rows = []

    # ------------------------------------------------------
    # Overall monthly rows
    # ------------------------------------------------------

    overall_vol_row = {
        "label": "Overall",
        "values": round_volume(total_vals),
    }

    overall_share_row = {
        "label": "Overall",
        "values": [100.0] * n,
    }

    # ------------------------------------------------------
    # Yearly descriptors
    # ------------------------------------------------------

    mv_series_data = []
    ms_series_data = []

    mv_table_rows = [
        {
            "label": "Overall",
            "monthly_values": total_vals,
        }
    ]

    ms_table_rows = [
        {
            "label": "Overall",
            "fixed_values": [100.0] * len(all_years),
        }
    ]

    market_totals = {}

    # ------------------------------------------------------
    # Build each market
    # ------------------------------------------------------

    for mkt in markets:
        d = fetch_forecast_scenario(
            cur,
            ta,
            mkt,
            None,
            "ALL",
            "market_share",
            scenario,
        )

        if not d:
            continue

        s = build_series(
            d,
            start,
            end,
        )

        share = list(
            s.get("values", [])
        )

        # Ensure series length matches total series
        share = (
            share[:n]
            + [0.0] * max(0, n - len(share))
        )

        # Raw market volumes
        vol = build_volume_from_share(
            total_vals,
            share,
        )

        vol = (
            vol[:n]
            + [0.0] * max(0, n - len(vol))
        )

        market_totals[mkt] = vol

        # Monthly display
        vol_display = round_volume(vol)

        h, f = split_series(
            vol_display,
            split_idx,
        )

        sh, sf = split_series(
            share,
            split_idx,
        )

        # --------------------------------------------------
        # Add selected markets to charts and yearly chart data
        # --------------------------------------------------

        if is_selected_market(mkt):
            vol_chart_series.append(
                {
                    "label": mkt,
                    "history": h,
                    "forecast": f,
                }
            )

            share_chart_series.append(
                {
                    "label": mkt,
                    "history": sh,
                    "forecast": sf,
                }
            )

            mv_series_data.append(
                {
                    "label": mkt,
                    "monthly_values": vol,
                }
            )

            ms_series_data.append(
                {
                    "label": mkt,
                    "child_vols": vol,
                    "parent_vols": total_vals,
                }
            )

        # --------------------------------------------------
        # Build source children
        # --------------------------------------------------

        sources = get_sources(
            cur,
            ta,
            mkt,
        )

        vol_children = []
        share_children_vals = []
        share_children_labels = []

        mv_child_rows = []
        ms_child_rows = []

        for src in sources:
            sd = fetch_forecast_scenario(
                cur,
                ta,
                mkt,
                src,
                "ALL",
                "market_share",
                scenario,
            )

            if not sd:
                continue

            ss = build_series(
                sd,
                start,
                end,
            )

            src_share = list(
                ss.get("values", [])
            )

            src_share = (
                src_share[:n]
                + [0.0] * max(
                    0,
                    n - len(src_share),
                )
            )

            src_vol = build_volume_from_share(
                vol,
                src_share,
            )

            src_vol = (
                src_vol[:n]
                + [0.0] * max(
                    0,
                    n - len(src_vol),
                )
            )

            vol_children.append(
                {
                    "label": src,
                    "values": round_volume(src_vol),
                }
            )

            share_children_vals.append(
                src_vol
            )

            share_children_labels.append(
                src
            )

            mv_child_rows.append(
                {
                    "label": src,
                    "monthly_values": src_vol,
                }
            )

            ms_child_rows.append(
                {
                    "label": src,
                    "child_vols": src_vol,
                    "parent_vols": vol,
                }
            )

        # --------------------------------------------------
        # Monthly table rows
        # --------------------------------------------------

        vol_row = {
            "label": mkt,
            "values": vol_display,
        }

        share_row = {
            "label": mkt,
            "values": share,
        }

        if vol_children:
            normalized_source_shares = (
                normalize_shares_to_100(
                    share_children_vals,
                    n,
                )
            )

            vol_children_display = [
                [
                    round(
                        vol[month_index]
                        * normalized_source_shares[child_index][month_index]
                        / 100
                    )
                    for month_index in range(n)
                ]
                for child_index in range(
                    len(normalized_source_shares)
                )
            ]

            vol_row["children"] = [
                {
                    "label": (
                        share_children_labels[
                            child_index
                        ]
                    ),
                    "values": (
                        vol_children_display[
                            child_index
                        ]
                    ),
                }
                for child_index in range(
                    len(normalized_source_shares)
                )
            ]

            share_row["children"] = [
                {
                    "label": (
                        share_children_labels[
                            child_index
                        ]
                    ),
                    "values": (
                        normalized_source_shares[
                            child_index
                        ]
                    ),
                }
                for child_index in range(
                    len(normalized_source_shares)
                )
            ]

        # Keep complete table here.
        # Your post-build table filtering helper can remove
        # unselected markets afterward.
        market_vol_rows.append(vol_row)
        market_share_rows.append(share_row)

        # --------------------------------------------------
        # Yearly hierarchy table descriptors
        # --------------------------------------------------

        mv_trow = {
            "label": mkt,
            "monthly_values": vol,
        }

        if mv_child_rows:
            mv_trow["children"] = mv_child_rows

        mv_table_rows.append(mv_trow)

        ms_trow = {
            "label": mkt,
            "child_vols": vol,
            "parent_vols": total_vals,
        }

        if ms_child_rows:
            ms_trow["children"] = ms_child_rows

        ms_table_rows.append(ms_trow)

    # ------------------------------------------------------
    # Monthly chart/table structures
    # ------------------------------------------------------

    mv_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": vol_chart_series,
    }

    mv_table = {
        "type": "hierarchy",
        "rows": [
            overall_vol_row,
            *market_vol_rows,
        ],
    }

    ms_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": share_chart_series,
    }

    ms_table = {
        "type": "hierarchy",
        "rows": [
            overall_share_row,
            *market_share_rows,
        ],
    }

    # ------------------------------------------------------
    # Selected market metadata
    # ------------------------------------------------------

    selected_market_volumes = {
        market_name: market_values
        for market_name, market_values
        in market_totals.items()
        if is_selected_market(market_name)
    }

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart,
                mv_table,
                months,
                split_idx,
                mv_series_data,
                mv_table_rows,
                "hierarchy",
            ),
        },

        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart,
                ms_table,
                months,
                split_idx,
                ms_series_data,
                ms_table_rows,
                "hierarchy",
            ),
        },

        "_selected": {
            "months": months,
            "split_idx": split_idx,

            # Multi-select-safe
            "volumes": selected_market_volumes,

            # Optional compatibility when exactly one market
            # is selected.
            "volume": (
                next(
                    iter(
                        selected_market_volumes.values()
                    )
                )
                if len(selected_market_volumes) == 1
                else [0.0] * n
            ),

            "parent_volume": total_vals,
        },
    }

def build_product_distribution_out(
    cur,
    ta,
    scenario,
    markets,
    total_vals,
    months,
    split_idx,
    start,
    end,
    selected_products=None,
):
    """
    Product distribution -- volume and share split across products,
    blended across every market/source.

    Supports multiple selected products.

    For products with directly saved overrides using:
        ("ALL", "ALL", product, "market_share")

    the saved share is pinned exactly. Other products are derived from
    market/source/product shares and normalized around the pinned values.
    """

    # ------------------------------------------------------
    # Normalize selected products
    # ------------------------------------------------------

    if selected_products is None:
        selected_products = []

    if isinstance(selected_products, str):
        selected_products = [selected_products]

    selected_product_keys = {
        str(product).strip().lower()
        for product in selected_products
        if product
        and str(product).strip().lower() != "all"
    }

    def is_selected_product(product_name):
        # No selected filter means include all products
        if not selected_product_keys:
            return True

        return (
            str(product_name).strip().lower()
            in selected_product_keys
        )

    products = get_products(cur, ta)
    n = len(total_vals)
    all_years = get_ordered_years(months)

    prod_vol_map = {
        product: [0.0] * n
        for product in products
    }

    override_share_map = {
        product: None
        for product in products
    }

    # ======================================================
    # 1. Pull directly saved product overrides
    # ======================================================

    for product in products:
        override_data = (
            fetch_forecast_scenario_with_fallback(
                cur,
                ta,
                "ALL",
                None,
                product,
                "market_share",
                scenario,
            )
        )

        if not override_data:
            continue

        series = build_series(
            override_data,
            start,
            end,
        )

        share = list(
            series.get("values", [])
        )

        share = (
            share[:n]
            + [0.0] * max(
                0,
                n - len(share),
            )
        )

        override_share_map[product] = share

        product_volume = build_volume_from_share(
            total_vals,
            share,
        )

        prod_vol_map[product] = (
            product_volume[:n]
            + [0.0] * max(
                0,
                n - len(product_volume),
            )
        )

    # ======================================================
    # 2. Recompute non-overridden products
    # ======================================================

    for market in markets:
        market_data = fetch_forecast_scenario(
            cur,
            ta,
            market,
            None,
            "ALL",
            "market_share",
            scenario,
        )

        if not market_data:
            continue

        market_series = build_series(
            market_data,
            start,
            end,
        )

        market_share = list(
            market_series.get("values", [])
        )

        market_share = (
            market_share[:n]
            + [0.0] * max(
                0,
                n - len(market_share),
            )
        )

        market_volume = build_volume_from_share(
            total_vals,
            market_share,
        )

        market_volume = (
            market_volume[:n]
            + [0.0] * max(
                0,
                n - len(market_volume),
            )
        )

        for product in products:
            # Directly saved product share remains pinned
            if override_share_map[product] is not None:
                continue

            # --------------------------------------------------
            # Retail: product share directly under market
            # --------------------------------------------------

            if str(market).strip().lower() == "retail":
                product_data = (
                    fetch_forecast_scenario_with_fallback(
                        cur,
                        ta,
                        market,
                        None,
                        product,
                        "market_share",
                        scenario,
                    )
                )

                if not product_data:
                    continue

                product_series = build_series(
                    product_data,
                    start,
                    end,
                )

                product_share = list(
                    product_series.get("values", [])
                )

                product_share = (
                    product_share[:n]
                    + [0.0] * max(
                        0,
                        n - len(product_share),
                    )
                )

                product_volume = (
                    build_volume_from_share(
                        market_volume,
                        product_share,
                    )
                )

                for index in range(
                    min(len(product_volume), n)
                ):
                    prod_vol_map[product][index] += (
                        product_volume[index]
                    )

            # --------------------------------------------------
            # Non-retail: market -> source -> product
            # --------------------------------------------------

            else:
                sources = get_sources(
                    cur,
                    ta,
                    market,
                )

                for source in sources:
                    source_data = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            market,
                            source,
                            "ALL",
                            "market_share",
                            scenario,
                        )
                    )

                    if not source_data:
                        continue

                    source_series = build_series(
                        source_data,
                        start,
                        end,
                    )

                    source_share = list(
                        source_series.get("values", [])
                    )

                    source_share = (
                        source_share[:n]
                        + [0.0] * max(
                            0,
                            n - len(source_share),
                        )
                    )

                    source_volume = (
                        build_volume_from_share(
                            market_volume,
                            source_share,
                        )
                    )

                    source_volume = (
                        source_volume[:n]
                        + [0.0] * max(
                            0,
                            n - len(source_volume),
                        )
                    )

                    product_data = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            market,
                            source,
                            product,
                            "market_share",
                            scenario,
                        )
                    )

                    if not product_data:
                        continue

                    product_series = build_series(
                        product_data,
                        start,
                        end,
                    )

                    product_share = list(
                        product_series.get("values", [])
                    )

                    product_share = (
                        product_share[:n]
                        + [0.0] * max(
                            0,
                            n - len(product_share),
                        )
                    )

                    product_volume = (
                        build_volume_from_share(
                            source_volume,
                            product_share,
                        )
                    )

                    for index in range(
                        min(len(product_volume), n)
                    ):
                        prod_vol_map[product][index] += (
                            product_volume[index]
                        )

    # ======================================================
    # Normalize shares while respecting pinned overrides
    # ======================================================

    product_labels = list(
        prod_vol_map.keys()
    )

    raw_volumes = [
        prod_vol_map[product]
        for product in product_labels
    ]

    normalized_shares = (
        normalize_shares_with_pins(
            raw_volumes,
            product_labels,
            override_share_map,
            n,
        )
    )

    # ======================================================
    # Monthly table rows
    # ======================================================

    overall_volume_row = {
        "label": "Overall",
        "values": round_volume(total_vals),
    }

    overall_share_row = {
        "label": "Overall",
        "values": [100.0] * n,
    }

    volume_table_rows = [
        {
            "label": product,
            "values": round_volume(
                prod_vol_map[product]
            ),
        }
        for product in product_labels
    ]

    share_table_rows = [
        {
            "label": product,
            "values": normalized_shares[index],
        }
        for index, product in enumerate(
            product_labels
        )
    ]

    # ======================================================
    # Monthly volume chart
    # ======================================================

    volume_chart_series = []

    for product in product_labels:
        if not is_selected_product(product):
            continue

        display_values = round_volume(
            prod_vol_map[product]
        )

        history, forecast = split_series(
            display_values,
            split_idx,
        )

        volume_chart_series.append(
            {
                "label": product,
                "history": history,
                "forecast": forecast,
            }
        )

    mv_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": volume_chart_series,
    }

    mv_table = {
        "type": "flat",
        "rows": [
            overall_volume_row,
            *volume_table_rows,
        ],
    }

    # ======================================================
    # Monthly share chart
    # ======================================================

    share_chart_series = []

    for index, product in enumerate(
        product_labels
    ):
        if not is_selected_product(product):
            continue

        history, forecast = split_series(
            normalized_shares[index],
            split_idx,
        )

        share_chart_series.append(
            {
                "label": product,
                "history": history,
                "forecast": forecast,
            }
        )

    ms_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": share_chart_series,
    }

    ms_table = {
        "type": "flat",
        "rows": [
            overall_share_row,
            *share_table_rows,
        ],
    }

    # ======================================================
    # Yearly volume chart/table descriptors
    # ======================================================

    mv_series_data = [
        {
            "label": product,
            "monthly_values": prod_vol_map[product],
        }
        for product in product_labels
        if is_selected_product(product)
    ]

    mv_table_rows = [
        {
            "label": "Overall",
            "monthly_values": total_vals,
        },
        *[
            {
                "label": product,
                "monthly_values": prod_vol_map[product],
            }
            for product in product_labels
        ],
    ]

    # ======================================================
    # Yearly share chart/table descriptors
    # ======================================================

    ms_series_data = [
        {
            "label": product,
            "child_vols": prod_vol_map[product],
            "parent_vols": total_vals,
        }
        for product in product_labels
        if is_selected_product(product)
    ]

    ms_table_rows = [
        {
            "label": "Overall",
            "fixed_values": (
                [100.0] * len(all_years)
            ),
        },
        *[
            {
                "label": product,
                "child_vols": prod_vol_map[product],
                "parent_vols": total_vals,
            }
            for product in product_labels
        ],
    ]

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart,
                mv_table,
                months,
                split_idx,
                mv_series_data,
                mv_table_rows,
                "flat",
            ),
        },

        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart,
                ms_table,
                months,
                split_idx,
                ms_series_data,
                ms_table_rows,
                "flat",
            ),
        },
    }

def build_market_product_out(
    cur,
    ta,
    scenario,
    markets,
    products,
    total_vals,
    months,
    split_idx,
    start,
    end,
    selected_markets=None,
    selected_products=None,
):
    """
    Market -> Product breakdown.

    Supports multiple selected markets and products.

    Chart:
        Includes every selected market-product combination.

    Table:
        Contains the full hierarchy here. It can be filtered afterward by
        apply_market_analysis_table_filters().

    Yearly product share within market:
        sum(product raw volume)
        /
        sum(market raw volume)
        * 100
    """

    # ------------------------------------------------------
    # Normalize selected filters
    # ------------------------------------------------------

    if selected_markets is None:
        selected_markets = []

    if isinstance(selected_markets, str):
        selected_markets = [selected_markets]

    selected_market_keys = {
        str(market).strip().lower()
        for market in selected_markets
        if market
        and str(market).strip().lower() != "all"
    }

    if selected_products is None:
        selected_products = []

    if isinstance(selected_products, str):
        selected_products = [selected_products]

    selected_product_keys = {
        str(product).strip().lower()
        for product in selected_products
        if product
        and str(product).strip().lower() != "all"
    }

    def is_selected_market(market_name):
        if not selected_market_keys:
            return True

        return (
            str(market_name).strip().lower()
            in selected_market_keys
        )

    def is_selected_product(product_name):
        if not selected_product_keys:
            return True

        return (
            str(product_name).strip().lower()
            in selected_product_keys
        )

    n = len(total_vals)
    all_years = get_ordered_years(months)

    mp_vol = {}
    market_totals = {}

    # ======================================================
    # Build raw market-product volumes
    # ======================================================

    for market in markets:
        mp_vol[market] = {}

        market_data = fetch_forecast_scenario(
            cur,
            ta,
            market,
            None,
            "ALL",
            "market_share",
            scenario,
        )

        if market_data:
            market_series = build_series(
                market_data,
                start,
                end,
            )

            market_share = list(
                market_series.get("values", [])
            )

            market_share = (
                market_share[:n]
                + [0.0] * max(
                    0,
                    n - len(market_share),
                )
            )

            market_volume = build_volume_from_share(
                total_vals,
                market_share,
            )

            market_volume = (
                market_volume[:n]
                + [0.0] * max(
                    0,
                    n - len(market_volume),
                )
            )

        else:
            market_volume = [0.0] * n

        market_totals[market] = market_volume

        for product in products:

            # --------------------------------------------------
            # Retail: market -> product
            # --------------------------------------------------

            if str(market).strip().lower() == "retail":
                product_data = (
                    fetch_forecast_scenario_with_fallback(
                        cur,
                        ta,
                        market,
                        None,
                        product,
                        "market_share",
                        scenario,
                    )
                )

                if not product_data:
                    continue

                product_series = build_series(
                    product_data,
                    start,
                    end,
                )

                product_share = list(
                    product_series.get("values", [])
                )

                product_share = (
                    product_share[:n]
                    + [0.0] * max(
                        0,
                        n - len(product_share),
                    )
                )

                product_volume = build_volume_from_share(
                    market_volume,
                    product_share,
                )

                product_volume = (
                    product_volume[:n]
                    + [0.0] * max(
                        0,
                        n - len(product_volume),
                    )
                )

            # --------------------------------------------------
            # Non-retail: market -> source -> product
            # --------------------------------------------------

            else:
                product_volume = [0.0] * n

                sources = get_sources(
                    cur,
                    ta,
                    market,
                )

                for source in sources:
                    source_data = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            market,
                            source,
                            "ALL",
                            "market_share",
                            scenario,
                        )
                    )

                    if not source_data:
                        continue

                    source_series = build_series(
                        source_data,
                        start,
                        end,
                    )

                    source_share = list(
                        source_series.get("values", [])
                    )

                    source_share = (
                        source_share[:n]
                        + [0.0] * max(
                            0,
                            n - len(source_share),
                        )
                    )

                    source_volume = build_volume_from_share(
                        market_volume,
                        source_share,
                    )

                    source_volume = (
                        source_volume[:n]
                        + [0.0] * max(
                            0,
                            n - len(source_volume),
                        )
                    )

                    source_product_data = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            market,
                            source,
                            product,
                            "market_share",
                            scenario,
                        )
                    )

                    if not source_product_data:
                        continue

                    source_product_series = build_series(
                        source_product_data,
                        start,
                        end,
                    )

                    source_product_share = list(
                        source_product_series.get(
                            "values",
                            [],
                        )
                    )

                    source_product_share = (
                        source_product_share[:n]
                        + [0.0] * max(
                            0,
                            n - len(
                                source_product_share
                            ),
                        )
                    )

                    source_product_volume = (
                        build_volume_from_share(
                            source_volume,
                            source_product_share,
                        )
                    )

                    for index in range(
                        min(
                            n,
                            len(source_product_volume),
                        )
                    ):
                        product_volume[index] += (
                            source_product_volume[index]
                        )

            mp_vol[market][product] = product_volume

    # ======================================================
    # Build selected chart series
    # ======================================================

    volume_chart_series = []
    share_chart_series = []

    mv_series_data = []
    ms_series_data = []

    for market in markets:
        if not is_selected_market(market):
            continue

        market_volume = market_totals.get(
            market,
            [0.0] * n,
        )

        available_products = [
            product
            for product in products
            if product in mp_vol.get(market, {})
        ]

        product_volumes = [
            mp_vol[market][product]
            for product in available_products
        ]

        normalized_shares = (
            normalize_shares_to_100(
                product_volumes,
                n,
            )
            if product_volumes
            else []
        )

        for product_index, product in enumerate(
            available_products
        ):
            if not is_selected_product(product):
                continue

            product_volume = mp_vol[market][product]

            volume_display = round_volume(
                product_volume
            )

            volume_history, volume_forecast = (
                split_series(
                    volume_display,
                    split_idx,
                )
            )

            label = f"{market} - {product}"

            volume_chart_series.append(
                {
                    "label": label,
                    "market": market,
                    "product": product,
                    "history": volume_history,
                    "forecast": volume_forecast,
                }
            )

            mv_series_data.append(
                {
                    "label": label,
                    "market": market,
                    "product": product,
                    "monthly_values": product_volume,
                }
            )

            product_share = normalized_shares[
                product_index
            ]

            share_history, share_forecast = (
                split_series(
                    product_share,
                    split_idx,
                )
            )

            share_chart_series.append(
                {
                    "label": label,
                    "market": market,
                    "product": product,
                    "history": share_history,
                    "forecast": share_forecast,
                }
            )

            ms_series_data.append(
                {
                    "label": label,
                    "market": market,
                    "product": product,
                    "child_vols": product_volume,
                    "parent_vols": market_volume,
                }
            )

    # ======================================================
    # Build full monthly/yearly hierarchy tables
    # ======================================================

    volume_table_rows = []
    share_table_rows = []

    mv_table_rows = []
    ms_table_rows = []

    for market in markets:
        market_volume = market_totals.get(
            market,
            [0.0] * n,
        )

        available_products = [
            product
            for product in products
            if product in mp_vol.get(market, {})
        ]

        product_volumes = [
            mp_vol[market][product]
            for product in available_products
        ]

        normalized_shares = (
            normalize_shares_to_100(
                product_volumes,
                n,
            )
            if product_volumes
            else []
        )

        # Preserve raw product volumes in the volume table.
        # This avoids recalculating displayed volumes from rounded shares.
        volume_children = [
            {
                "label": product,
                "values": round_volume(
                    mp_vol[market][product]
                ),
            }
            for product in available_products
        ]

        share_children = [
            {
                "label": product,
                "values": normalized_shares[index],
            }
            for index, product in enumerate(
                available_products
            )
        ]

        volume_row = {
            "label": market,
            "values": round_volume(
                market_volume
            ),
        }

        share_row = {
            "label": market,
            "values": [100.0] * n,
        }

        if volume_children:
            volume_row["children"] = (
                volume_children
            )

        if share_children:
            share_row["children"] = (
                share_children
            )

        volume_table_rows.append(
            volume_row
        )

        share_table_rows.append(
            share_row
        )

        yearly_volume_row = {
            "label": market,
            "monthly_values": market_volume,
        }

        if available_products:
            yearly_volume_row["children"] = [
                {
                    "label": product,
                    "monthly_values": (
                        mp_vol[market][product]
                    ),
                }
                for product in available_products
            ]

        mv_table_rows.append(
            yearly_volume_row
        )

        yearly_share_row = {
            "label": market,
            "fixed_values": (
                [100.0] * len(all_years)
            ),
        }

        if available_products:
            yearly_share_row["children"] = [
                {
                    "label": product,
                    "child_vols": (
                        mp_vol[market][product]
                    ),
                    "parent_vols": market_volume,
                }
                for product in available_products
            ]

        ms_table_rows.append(
            yearly_share_row
        )

    mv_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": volume_chart_series,
    }

    mv_table = {
        "type": "hierarchy",
        "rows": volume_table_rows,
    }

    ms_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": share_chart_series,
    }

    ms_table = {
        "type": "hierarchy",
        "rows": share_table_rows,
    }

    # ======================================================
    # Multi-select metadata
    # ======================================================

    selected_volumes = {}

    for market in markets:
        if not is_selected_market(market):
            continue

        for product in products:
            if not is_selected_product(product):
                continue

            if product not in mp_vol.get(
                market,
                {},
            ):
                continue

            selected_volumes[
                f"{market} - {product}"
            ] = mp_vol[market][product]

    selected_parent_volumes = {
        market: market_totals[market]
        for market in markets
        if market in market_totals
        and is_selected_market(market)
    }

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart,
                mv_table,
                months,
                split_idx,
                mv_series_data,
                mv_table_rows,
                "hierarchy",
            ),
        },

        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart,
                ms_table,
                months,
                split_idx,
                ms_series_data,
                ms_table_rows,
                "hierarchy",
            ),
        },

        "_selected": {
            "months": months,
            "split_idx": split_idx,

            # Multi-selection data
            "volumes": selected_volumes,
            "parent_volumes": (
                selected_parent_volumes
            ),

            # Backward compatibility when exactly one
            # market-product combination is selected.
            "volume": (
                next(
                    iter(selected_volumes.values())
                )
                if len(selected_volumes) == 1
                else [0.0] * n
            ),

            "parent_volume": (
                next(
                    iter(
                        selected_parent_volumes.values()
                    )
                )
                if len(selected_parent_volumes) == 1
                else total_vals
            ),
        },
    }

def build_product_market_out(
    cur,
    ta,
    scenario,
    markets,
    products,
    total_vals,
    months,
    split_idx,
    start,
    end,
    selected_products=None,
    selected_markets=None,
):
    """
    Product -> Market breakdown.

    Supports multiple selected products and markets.

    pm_vol accumulates raw floats.
    Monthly display rounds only at output.

    Yearly market share within product:
        sum(market raw volume)
        /
        sum(product raw volume)
        * 100
    """

    # ------------------------------------------------------
    # Normalize selected filters
    # ------------------------------------------------------

    if selected_products is None:
        selected_products = []

    if isinstance(selected_products, str):
        selected_products = [selected_products]

    selected_product_keys = {
        str(product).strip().lower()
        for product in selected_products
        if product
        and str(product).strip().lower() != "all"
    }

    if selected_markets is None:
        selected_markets = []

    if isinstance(selected_markets, str):
        selected_markets = [selected_markets]

    selected_market_keys = {
        str(market).strip().lower()
        for market in selected_markets
        if market
        and str(market).strip().lower() != "all"
    }

    def is_selected_product(product_name):
        if not selected_product_keys:
            return True

        return (
            str(product_name).strip().lower()
            in selected_product_keys
        )

    def is_selected_market(market_name):
        if not selected_market_keys:
            return True

        return (
            str(market_name).strip().lower()
            in selected_market_keys
        )

    n = len(total_vals)
    all_years = get_ordered_years(months)

    pm_vol = {}
    product_totals = {}

    # ======================================================
    # Build raw product-market volumes
    # ======================================================

    for product in products:
        pm_vol[product] = {}
        product_total = [0.0] * n

        for market in markets:

            # --------------------------------------------------
            # Retail: total -> market -> product
            # --------------------------------------------------

            if str(market).strip().lower() == "retail":
                product_data = fetch_forecast_scenario(
                    cur,
                    ta,
                    market,
                    None,
                    product,
                    "market_share",
                    scenario,
                )

                if not product_data:
                    continue

                product_series = build_series(
                    product_data,
                    start,
                    end,
                )

                market_data = fetch_forecast_scenario(
                    cur,
                    ta,
                    market,
                    None,
                    "ALL",
                    "market_share",
                    scenario,
                )

                if not market_data:
                    continue

                market_series = build_series(
                    market_data,
                    start,
                    end,
                )

                market_share = list(
                    market_series.get("values", [])
                )

                product_share = list(
                    product_series.get("values", [])
                )

                market_share = (
                    market_share[:n]
                    + [0.0] * max(
                        0,
                        n - len(market_share),
                    )
                )

                product_share = (
                    product_share[:n]
                    + [0.0] * max(
                        0,
                        n - len(product_share),
                    )
                )

                market_volume = build_volume_from_share(
                    total_vals,
                    market_share,
                )

                market_volume = (
                    market_volume[:n]
                    + [0.0] * max(
                        0,
                        n - len(market_volume),
                    )
                )

                volume = build_volume_from_share(
                    market_volume,
                    product_share,
                )

                volume = (
                    volume[:n]
                    + [0.0] * max(
                        0,
                        n - len(volume),
                    )
                )

            # --------------------------------------------------
            # Non-retail: total -> market -> source -> product
            # --------------------------------------------------

            else:
                volume = [0.0] * n

                market_data = fetch_forecast_scenario(
                    cur,
                    ta,
                    market,
                    None,
                    "ALL",
                    "market_share",
                    scenario,
                )

                if not market_data:
                    continue

                market_series = build_series(
                    market_data,
                    start,
                    end,
                )

                market_share = list(
                    market_series.get("values", [])
                )

                market_share = (
                    market_share[:n]
                    + [0.0] * max(
                        0,
                        n - len(market_share),
                    )
                )

                market_volume = build_volume_from_share(
                    total_vals,
                    market_share,
                )

                market_volume = (
                    market_volume[:n]
                    + [0.0] * max(
                        0,
                        n - len(market_volume),
                    )
                )

                sources = get_sources(
                    cur,
                    ta,
                    market,
                )

                for source in sources:
                    source_data = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            market,
                            source,
                            "ALL",
                            "market_share",
                            scenario,
                        )
                    )

                    if not source_data:
                        continue

                    source_series = build_series(
                        source_data,
                        start,
                        end,
                    )

                    source_share = list(
                        source_series.get("values", [])
                    )

                    source_share = (
                        source_share[:n]
                        + [0.0] * max(
                            0,
                            n - len(source_share),
                        )
                    )

                    source_volume = build_volume_from_share(
                        market_volume,
                        source_share,
                    )

                    source_volume = (
                        source_volume[:n]
                        + [0.0] * max(
                            0,
                            n - len(source_volume),
                        )
                    )

                    product_data = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            market,
                            source,
                            product,
                            "market_share",
                            scenario,
                        )
                    )

                    if not product_data:
                        continue

                    product_series = build_series(
                        product_data,
                        start,
                        end,
                    )

                    product_share = list(
                        product_series.get("values", [])
                    )

                    product_share = (
                        product_share[:n]
                        + [0.0] * max(
                            0,
                            n - len(product_share),
                        )
                    )

                    product_volume = build_volume_from_share(
                        source_volume,
                        product_share,
                    )

                    for index in range(
                        min(n, len(product_volume))
                    ):
                        volume[index] += product_volume[index]

            pm_vol[product][market] = volume

            for index in range(n):
                product_total[index] += volume[index]

        product_totals[product] = product_total

    # ======================================================
    # Build selected chart series
    # ======================================================

    volume_chart_series = []
    share_chart_series = []

    mv_series_data = []
    ms_series_data = []

    for product in products:
        if not is_selected_product(product):
            continue

        product_total = product_totals.get(
            product,
            [0.0] * n,
        )

        available_markets = [
            market
            for market in markets
            if market in pm_vol.get(product, {})
        ]

        market_volumes = [
            pm_vol[product][market]
            for market in available_markets
        ]

        normalized_shares = (
            normalize_shares_to_100(
                market_volumes,
                n,
            )
            if market_volumes
            else []
        )

        for market_index, market in enumerate(
            available_markets
        ):
            if not is_selected_market(market):
                continue

            volume = pm_vol[product][market]
            volume_display = round_volume(volume)

            volume_history, volume_forecast = split_series(
                volume_display,
                split_idx,
            )

            label = f"{product} - {market}"

            volume_chart_series.append(
                {
                    "label": label,
                    "product": product,
                    "market": market,
                    "history": volume_history,
                    "forecast": volume_forecast,
                }
            )

            mv_series_data.append(
                {
                    "label": label,
                    "product": product,
                    "market": market,
                    "monthly_values": volume,
                }
            )

            share_values = normalized_shares[
                market_index
            ]

            share_history, share_forecast = split_series(
                share_values,
                split_idx,
            )

            share_chart_series.append(
                {
                    "label": label,
                    "product": product,
                    "market": market,
                    "history": share_history,
                    "forecast": share_forecast,
                }
            )

            ms_series_data.append(
                {
                    "label": label,
                    "product": product,
                    "market": market,
                    "child_vols": volume,
                    "parent_vols": product_total,
                }
            )

    # ======================================================
    # Build full monthly/yearly hierarchy tables
    # ======================================================

    volume_table_rows = []
    share_table_rows = []

    mv_table_rows = []
    ms_table_rows = []

    for product in products:
        product_total = product_totals.get(
            product,
            [0.0] * n,
        )

        available_markets = [
            market
            for market in markets
            if market in pm_vol.get(product, {})
        ]

        market_volumes = [
            pm_vol[product][market]
            for market in available_markets
        ]

        normalized_shares = (
            normalize_shares_to_100(
                market_volumes,
                n,
            )
            if market_volumes
            else []
        )

        volume_children = [
            {
                "label": market,
                "values": round_volume(
                    pm_vol[product][market]
                ),
            }
            for market in available_markets
        ]

        share_children = [
            {
                "label": market,
                "values": normalized_shares[index],
            }
            for index, market in enumerate(
                available_markets
            )
        ]

        volume_row = {
            "label": product,
            "values": round_volume(product_total),
        }

        share_row = {
            "label": product,
            "values": [100.0] * n,
        }

        if volume_children:
            volume_row["children"] = volume_children

        if share_children:
            share_row["children"] = share_children

        volume_table_rows.append(volume_row)
        share_table_rows.append(share_row)

        yearly_volume_row = {
            "label": product,
            "monthly_values": product_total,
        }

        if available_markets:
            yearly_volume_row["children"] = [
                {
                    "label": market,
                    "monthly_values": (
                        pm_vol[product][market]
                    ),
                }
                for market in available_markets
            ]

        mv_table_rows.append(yearly_volume_row)

        yearly_share_row = {
            "label": product,
            "fixed_values": (
                [100.0] * len(all_years)
            ),
        }

        if available_markets:
            yearly_share_row["children"] = [
                {
                    "label": market,
                    "child_vols": (
                        pm_vol[product][market]
                    ),
                    "parent_vols": product_total,
                }
                for market in available_markets
            ]

        ms_table_rows.append(yearly_share_row)

    mv_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": volume_chart_series,
    }

    mv_table = {
        "type": "hierarchy",
        "rows": volume_table_rows,
    }

    ms_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": share_chart_series,
    }

    ms_table = {
        "type": "hierarchy",
        "rows": share_table_rows,
    }

    # ======================================================
    # Multi-select metadata
    # ======================================================

    selected_volumes = {}

    for product in products:
        if not is_selected_product(product):
            continue

        for market in markets:
            if not is_selected_market(market):
                continue

            if market not in pm_vol.get(product, {}):
                continue

            selected_volumes[
                f"{product} - {market}"
            ] = pm_vol[product][market]

    selected_parent_volumes = {
        product: product_totals[product]
        for product in products
        if product in product_totals
        and is_selected_product(product)
    }

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart,
                mv_table,
                months,
                split_idx,
                mv_series_data,
                mv_table_rows,
                "hierarchy",
            ),
        },

        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart,
                ms_table,
                months,
                split_idx,
                ms_series_data,
                ms_table_rows,
                "hierarchy",
            ),
        },

        "_selected": {
            "months": months,
            "split_idx": split_idx,

            "volumes": selected_volumes,
            "parent_volumes": selected_parent_volumes,

            # Backward compatibility for a single selection
            "volume": (
                next(iter(selected_volumes.values()))
                if len(selected_volumes) == 1
                else [0.0] * n
            ),

            "parent_volume": (
                next(
                    iter(
                        selected_parent_volumes.values()
                    )
                )
                if len(selected_parent_volumes) == 1
                else total_vals
            ),
        },
    }

def normalize_filter_values(values):
    if not values:
        return []

    normalized = []
    seen = set()

    for value in values:
        if value is None:
            continue

        cleaned = str(value).strip()

        if not cleaned:
            continue

        key = cleaned.lower()

        if key not in seen:
            seen.add(key)
            normalized.append(cleaned)

    return normalized

def normalize_dimension_filter(values):
    values = normalize_filter_values(values)

    if any(
        value.lower() in {
            "all",
            "overall",
        }
        for value in values
    ):
        return []

    return values

def resolve_selected_scenarios(
    requested_scenarios,
    available_scenarios,
):
    available_lookup = {
        str(scenario).strip().lower(): scenario
        for scenario in available_scenarios
    }

    requested_scenarios = normalize_filter_values(
        requested_scenarios
    )

    if not requested_scenarios:
        return [available_scenarios[0]]

    resolved = []

    for requested in requested_scenarios:
        key = requested.lower()

        if key not in available_lookup:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Scenario {requested!r} is not available."
                ),
            )

        resolved.append(
            available_lookup[key]
        )

    return resolved

def build_scenario_market_analysis(
    cur,
    ta,
    scenario,
    start,
    end,
    selected_markets,
    selected_products,
):
    total_data = fetch_forecast_scenario(
        cur,
        ta,
        "ALL",
        "ALL",
        "ALL",
        "market_volume",
        scenario,
    )

    if not total_data:
        return {
            "total_market_volume": {
                "market_volume": {},
                "market_share": {},
            },
            "market_distribution": {},
            "product_distribution": {},
            "market_product": {},
            "product_market": {},
        }

    total = build_series(
        total_data,
        start,
        end,
    )

    total_vals = total["values"]
    months = total["months"]
    split_idx = total["split_idx"]

    markets = get_markets(cur, ta)
    products = get_products(cur, ta)

    selected_markets = normalize_filter_values(
        selected_markets
    )

    selected_products = normalize_filter_values(
        selected_products
    )

    market_analysis = {
        "total_market_volume": (
            build_total_market_volume(
                total_vals,
                months,
                split_idx,
                scenario,
            )
        ),

        "market_distribution": (
            build_market_distribution_out(
                cur=cur,
                ta=ta,
                scenario=scenario,
                total_vals=total_vals,
                months=months,
                split_idx=split_idx,
                start=start,
                end=end,
                selected_markets=selected_markets,
            )
        ),

        "product_distribution": (
            build_product_distribution_out(
                cur=cur,
                ta=ta,
                scenario=scenario,
                markets=markets,
                total_vals=total_vals,
                months=months,
                split_idx=split_idx,
                start=start,
                end=end,
                selected_products=selected_products,
            )
        ),

        "market_product": (
            build_market_product_out(
                cur=cur,
                ta=ta,
                scenario=scenario,
                markets=markets,
                products=products,
                total_vals=total_vals,
                months=months,
                split_idx=split_idx,
                start=start,
                end=end,
                selected_markets=selected_markets,
                selected_products=selected_products,
            )
        ),

        "product_market": (
            build_product_market_out(
                cur=cur,
                ta=ta,
                scenario=scenario,
                markets=markets,
                products=products,
                total_vals=total_vals,
                months=months,
                split_idx=split_idx,
                start=start,
                end=end,
                selected_markets=selected_markets,
                selected_products=selected_products,
            )
        ),
    }

    apply_market_analysis_table_filters(
        market_analysis=market_analysis,
        selected_markets=selected_markets,
        selected_products=selected_products,
    )

    return market_analysis

def add_scenario_name_to_rows(
    rows,
    scenario_name,
    *,
    total_market_volume=False,
):
    if not isinstance(rows, list):
        return []

    renamed_rows = []

    total_labels = {
        "overall",
        "total",
        "grand total",
    }

    for row in rows:
        if not isinstance(row, dict):
            continue

        copied_row = deepcopy(row)

        label = str(
            copied_row.get("label", "")
        ).strip()

        normalized_label = label.lower()

        if label:
            if (
                total_market_volume
                and normalized_label in total_labels
            ):
                copied_row["label"] = scenario_name
            else:
                copied_row["label"] = (
                    f"{label} ({scenario_name})"
                )

        children = copied_row.get("children")

        if isinstance(children, list):
            copied_row["children"] = (
                add_scenario_name_to_rows(
                    children,
                    scenario_name,
                    total_market_volume=False,
                )
            )

        renamed_rows.append(copied_row)

    return renamed_rows

def add_scenario_name_to_chart_series(
    series,
    scenario_name,
    *,
    total_market_volume=False,
):
    if not isinstance(series, list):
        return []

    renamed_series = []

    total_labels = {
        "overall",
        "total",
        "grand total",
    }

    for item in series:
        if not isinstance(item, dict):
            continue

        copied_item = deepcopy(item)

        label_key = None

        for candidate in (
            "name",
            "label",
            "series_name",
        ):
            if candidate in copied_item:
                label_key = candidate
                break

        if label_key is not None:
            label = str(
                copied_item.get(label_key, "")
            ).strip()

            normalized_label = label.lower()

            if label:
                if (
                    total_market_volume
                    and normalized_label in total_labels
                ):
                    copied_item[label_key] = (
                        scenario_name
                    )
                else:
                    copied_item[label_key] = (
                        f"{label} ({scenario_name})"
                    )

        renamed_series.append(copied_item)

    return renamed_series

def prepare_scenario_for_merge(
    market_analysis,
    scenario_name,
):
    prepared = deepcopy(market_analysis)

    for tab_name, tab_data in prepared.items():
        if not isinstance(tab_data, dict):
            continue

        is_total_market_volume = (
            tab_name == "total_market_volume"
        )

        for metric_data in tab_data.values():
            if not isinstance(metric_data, dict):
                continue

            for view_data in metric_data.values():
                if not isinstance(view_data, dict):
                    continue

                table = view_data.get("table")

                if isinstance(table, dict):
                    table["rows"] = (
                        add_scenario_name_to_rows(
                            table.get("rows", []),
                            scenario_name,
                            total_market_volume=(
                                is_total_market_volume
                            ),
                        )
                    )

                chart = view_data.get("chart")

                if isinstance(chart, dict):
                    chart["series"] = (
                        add_scenario_name_to_chart_series(
                            chart.get("series", []),
                            scenario_name,
                            total_market_volume=(
                                is_total_market_volume
                            ),
                        )
                    )

    return prepared

def merge_view_data(
    destination_view,
    source_view,
):
    if not isinstance(destination_view, dict):
        return

    if not isinstance(source_view, dict):
        return

    # =====================================================
    # Merge table rows
    # =====================================================

    source_table = source_view.get("table")

    if isinstance(source_table, dict):
        destination_table = destination_view.get(
            "table"
        )

        if not isinstance(destination_table, dict):
            destination_view["table"] = deepcopy(
                source_table
            )
        else:
            destination_table.setdefault(
                "rows",
                [],
            )

            destination_table["rows"].extend(
                deepcopy(
                    source_table.get("rows", [])
                )
            )

    # =====================================================
    # Merge chart series
    # =====================================================

    source_chart = source_view.get("chart")

    if isinstance(source_chart, dict):
        destination_chart = destination_view.get(
            "chart"
        )

        if not isinstance(destination_chart, dict):
            destination_view["chart"] = deepcopy(
                source_chart
            )
        else:
            destination_chart.setdefault(
                "series",
                [],
            )

            destination_chart["series"].extend(
                deepcopy(
                    source_chart.get("series", [])
                )
            )

    # =====================================================
    # Copy missing metadata
    # =====================================================

    for key, value in source_view.items():
        if key in {"table", "chart"}:
            continue

        if key not in destination_view:
            destination_view[key] = deepcopy(value)

def merge_output_tabs(
    destination,
    source,
):
    if not destination:
        return deepcopy(source)

    for tab_name, source_tab in source.items():
        if tab_name not in destination:
            destination[tab_name] = deepcopy(
                source_tab
            )
            continue

        destination_tab = destination[tab_name]

        if not isinstance(source_tab, dict):
            continue

        for metric_name, source_metric in (
            source_tab.items()
        ):
            if metric_name not in destination_tab:
                destination_tab[metric_name] = (
                    deepcopy(source_metric)
                )
                continue

            destination_metric = (
                destination_tab[metric_name]
            )

            if not isinstance(source_metric, dict):
                continue

            for view_name, source_view in (
                source_metric.items()
            ):
                if view_name not in destination_metric:
                    destination_metric[view_name] = (
                        deepcopy(source_view)
                    )
                    continue

                destination_view = (
                    destination_metric[view_name]
                )

                merge_view_data(
                    destination_view,
                    source_view,
                )

    return destination


def merge_total_market_volume(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "total_market_volume",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "total_market_volume",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(source_period, dict):
                continue

            prepare_total_market_period(
                source_period=source_period,
                metric_name=metric_name,
                scenario_name=scenario_name,
                period_name=period_name,
            )

            # First scenario for this metric/period.
            if period_name not in destination_metric:
                destination_metric[period_name] = (
                    source_period
                )
                continue

            destination_period = destination_metric[
                period_name
            ]

            merge_total_market_table(
                destination_period=destination_period,
                source_period=source_period,
            )

            merge_chart_series(
                destination_period=destination_period,
                source_period=source_period,
            )

def prepare_total_market_period(
    source_period,
    metric_name,
    scenario_name,
    period_name,
):
    source_table = source_period.setdefault(
        "table",
        {},
    )

    source_rows = source_table.get(
        "rows",
        [],
    )

    values = extract_total_market_values(
        source_rows
    )

    source_table["type"] = "flat"

    source_table["headers"] = build_table_headers(
        source_period=source_period,
        period_name=period_name,
    )

    source_table["rows"] = [
        {
            "label": build_grand_total_label(
                scenario_name
            ),
            "target_metric": metric_display_name(
                metric_name
            ),
            "values": values,
        }
    ]

    prepare_total_market_chart(
        source_period=source_period,
        scenario_name=scenario_name,
    )

def extract_total_market_values(rows):
    if not isinstance(rows, list):
        return []

    preferred_labels = {
        "overall",
        "total",
        "grand total",
    }

    for row in rows:
        if not isinstance(row, dict):
            continue

        label = str(
            row.get("label", "")
        ).strip().lower()

        values = row.get("values")

        if (
            label in preferred_labels
            and isinstance(values, list)
        ):
            return deepcopy(values)

    # Fallback to the first valid row.
    for row in rows:
        if not isinstance(row, dict):
            continue

        values = row.get("values")

        if isinstance(values, list):
            return deepcopy(values)

    return []

def build_grand_total_label(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    if scenario_name.lower().endswith(
        "scenario"
    ):
        return f"Grand Total ({scenario_name})"

    return (
        f"Grand Total "
        f"({scenario_name})"
    )

def metric_display_name(
    metric_name,
):
    mapping = {
        "market_volume": "Market Volume",
        "market_share": "Market Share (%)",
    }

    return mapping.get(
        metric_name,
        metric_name.replace(
            "_",
            " ",
        ).title(),
    )

def build_table_headers(
    source_period,
    period_name,
):
    chart = source_period.get(
        "chart",
        {},
    )

    if period_name == "monthly":
        periods = chart.get(
            "months",
            [],
        )

        periods = [
            convert_month_header(period)
            for period in periods
        ]

    else:
        periods = (
            chart.get("years")
            or chart.get("months")
            or []
        )

    return [
        "Metric",
        *periods,
    ]

from datetime import datetime


def convert_month_header(
    month_label,
):
    try:
        return datetime.strptime(
            str(month_label),
            "%b-%y",
        ).strftime("%Y-%m")

    except (TypeError, ValueError):
        return month_label

def prepare_total_market_chart(
    source_period,
    scenario_name,
):
    chart = source_period.setdefault(
        "chart",
        {},
    )

    source_series = chart.get(
        "series",
        [],
    )

    if not source_series:
        return

    # Total Market normally contains one series.
    first_series = deepcopy(
        source_series[0]
    )

    first_series["label"] = clean_scenario_label(
        scenario_name
    )

    chart["series"] = [
        first_series
    ]

def clean_scenario_label(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    suffix = " scenario"

    if scenario_name.lower().endswith(
        suffix
    ):
        return scenario_name[
            :-len(suffix)
        ].strip()

    return scenario_name

def merge_total_market_table(
    destination_period,
    source_period,
):
    source_table = source_period.get(
        "table",
        {},
    )

    destination_table = (
        destination_period.setdefault(
            "table",
            {
                "type": "flat",
                "headers": deepcopy(
                    source_table.get(
                        "headers",
                        [],
                    )
                ),
                "rows": [],
            },
        )
    )

    destination_table["type"] = "flat"

    destination_table.setdefault(
        "headers",
        deepcopy(
            source_table.get(
                "headers",
                [],
            )
        ),
    )

    destination_table.setdefault(
        "rows",
        [],
    ).extend(
        deepcopy(
            source_table.get(
                "rows",
                [],
            )
        )
    )


def merge_market_distribution(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "market_distribution",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "market_distribution",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(source_period, dict):
                continue

            prepare_market_distribution_period(
                source_period=source_period,
                metric_name=metric_name,
                scenario_name=scenario_name,
                period_name=period_name,
            )

            # First scenario
            if period_name not in destination_metric:
                destination_metric[period_name] = (
                    source_period
                )
                continue

            destination_period = destination_metric[
                period_name
            ]

            merge_hierarchy_table_rows(
                destination_period=destination_period,
                source_period=source_period,
            )

            merge_chart_series(
                destination_period=destination_period,
                source_period=source_period,
            )

def prepare_market_distribution_period(
    source_period,
    metric_name,
    scenario_name,
    period_name,
):
    source_table = source_period.setdefault(
        "table",
        {},
    )

    original_rows = deepcopy(
        source_table.get(
            "rows",
            [],
        )
    )

    market_rows = remove_total_rows(
        original_rows
    )

    value_length = get_value_length(
        market_rows
    )

    if metric_name == "market_share":
        grand_total_values = [100.0] * value_length
    else:
        grand_total_values = calculate_grand_total_values(
            rows=market_rows,
        )

    target_metric = metric_display_name(
        metric_name
    )

    formatted_market_rows = []

    for row in market_rows:
        formatted_row = deepcopy(row)

        market_label = str(
            formatted_row.get("label", "")
        ).strip()

        formatted_row["label"] = build_scenario_row_label(
            label=market_label,
            scenario_name=scenario_name,
        )

        add_target_metric_to_row_tree(
            row=formatted_row,
            target_metric=target_metric,
        )

        formatted_market_rows.append(
            formatted_row
        )

    source_table["type"] = "hierarchy"

    source_table["headers"] = build_table_headers(
        source_period=source_period,
        period_name=period_name,
    )

    source_table["rows"] = [
        {
            "label": build_grand_total_label(
                scenario_name
            ),
            "target_metric": target_metric,
            "values": grand_total_values,
            "children": formatted_market_rows,
        }
    ]

    prepare_market_distribution_chart(
        source_period=source_period,
        scenario_name=scenario_name,
    )

def add_target_metric_to_row_tree(
    row,
    target_metric,
):
    if not isinstance(row, dict):
        return

    row["target_metric"] = target_metric

    children = row.get("children")

    if not isinstance(children, list):
        return

    for child in children:
        add_target_metric_to_row_tree(
            row=child,
            target_metric=target_metric,
        )

def remove_total_rows(rows):
    excluded_labels = {
        "overall",
        "total",
        "grand total",
        "all",
    }

    cleaned_rows = []

    if not isinstance(rows, list):
        return cleaned_rows

    for row in rows:

        if not isinstance(row, dict):
            continue

        label = str(
            row.get("label", "")
        ).strip().lower()

        if label in excluded_labels:
            continue

        cleaned_rows.append(
            deepcopy(row)
        )

    return cleaned_rows

def merge_hierarchy_table_rows(
    destination_period,
    source_period,
):
    source_table = source_period.get(
        "table",
        {},
    )

    destination_table = destination_period.setdefault(
        "table",
        {
            "type": "hierarchy",
            "headers": deepcopy(
                source_table.get(
                    "headers",
                    [],
                )
            ),
            "rows": [],
        },
    )

    destination_table["type"] = "hierarchy"

    if not destination_table.get("headers"):
        destination_table["headers"] = deepcopy(
            source_table.get(
                "headers",
                [],
            )
        )

    destination_table.setdefault(
        "rows",
        [],
    ).extend(
        deepcopy(
            source_table.get(
                "rows",
                [],
            )
        )
    )

def calculate_grand_total_values(rows):
    value_length = get_value_length(rows)

    totals = [0.0] * value_length

    for row in rows:

        values = row.get("values", [])

        if not isinstance(values, list):
            continue

        for index in range(
            min(value_length, len(values))
        ):
            value = values[index]

            if isinstance(value, (int, float)):
                totals[index] += value

    return [
        round(value)
        for value in totals
    ]

def get_value_length(rows):
    for row in rows:

        if not isinstance(row, dict):
            continue

        values = row.get("values")

        if isinstance(values, list):
            return len(values)

    return 0

def build_scenario_row_label(
    label,
    scenario_name,
):
    scenario_label = ensure_scenario_suffix(
        scenario_name
    )

    return f"{label} ({scenario_label})"

def build_grand_total_label(
    scenario_name,
):
    scenario_label = ensure_scenario_suffix(
        scenario_name
    )

    return f"Grand Total ({scenario_label})"

def ensure_scenario_suffix(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    if scenario_name.lower().endswith(
        "scenario"
    ):
        return scenario_name

    return f"{scenario_name}"

def prepare_market_distribution_chart(
    source_period,
    scenario_name,
):
    chart = source_period.setdefault(
        "chart",
        {},
    )

    scenario_label = clean_scenario_label(
        scenario_name
    )

    chart_series = []

    for series_item in chart.get(
        "series",
        [],
    ):

        if not isinstance(series_item, dict):
            continue

        item = deepcopy(series_item)

        label = str(
            item.get("label", "")
        ).strip()

        if not label:
            continue

        normalized_label = label.lower()

        if normalized_label in {
            "overall",
            "total",
            "grand total",
            "all",
        }:
            continue

        item["label"] = (
            f"{label} ({scenario_label})"
        )

        chart_series.append(item)

    chart["series"] = chart_series

def clean_scenario_label(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    suffix = " scenario"

    if scenario_name.lower().endswith(
        suffix
    ):
        return scenario_name[
            :-len(suffix)
        ].strip()

    return scenario_name

def metric_display_name(
    metric_name,
):
    mapping = {
        "market_volume": "Market Volume",
        "market_share": "Market Share (%)",
    }

    return mapping.get(
        metric_name,
        metric_name.replace(
            "_",
            " ",
        ).title(),
    )

from datetime import datetime


def build_table_headers(
    source_period,
    period_name,
):
    chart = source_period.get(
        "chart",
        {},
    )

    if period_name == "monthly":
        periods = [
            convert_month_header(month)
            for month in chart.get(
                "months",
                [],
            )
        ]

    else:
        periods = (
            chart.get("years")
            or chart.get("months")
            or []
        )

    return [
        "Metric",
        *periods,
    ]

def convert_month_header(
    month_label,
):
    try:
        return datetime.strptime(
            str(month_label),
            "%b-%y",
        ).strftime("%Y-%m")

    except (TypeError, ValueError):
        return month_label
    
def merge_flat_table_rows(
    destination_period,
    source_period,
):
    source_table = source_period.get(
        "table",
        {},
    )

    destination_table = (
        destination_period.setdefault(
            "table",
            {
                "type": "flat",
                "headers": deepcopy(
                    source_table.get(
                        "headers",
                        [],
                    )
                ),
                "rows": [],
            },
        )
    )

    destination_table["type"] = "flat"

    if not destination_table.get("headers"):
        destination_table["headers"] = deepcopy(
            source_table.get(
                "headers",
                [],
            )
        )

    destination_table.setdefault(
        "rows",
        [],
    ).extend(
        deepcopy(
            source_table.get(
                "rows",
                [],
            )
        )
    )

def merge_chart_series(
    destination_period,
    source_period,
):
    source_chart = source_period.get(
        "chart"
    )

    if not isinstance(source_chart, dict):
        return

    destination_chart = (
        destination_period.setdefault(
            "chart",
            {},
        )
    )

    for key, value in source_chart.items():

        if key == "series":
            continue

        destination_chart.setdefault(
            key,
            deepcopy(value),
        )

    destination_chart.setdefault(
        "series",
        [],
    ).extend(
        deepcopy(
            source_chart.get(
                "series",
                [],
            )
        )
    )


def merge_product_distribution(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "product_distribution",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "product_distribution",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in (
            "monthly",
            "yearly",
        ):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(
                source_period,
                dict,
            ):
                continue

            prepare_product_distribution_period(
                source_period=source_period,
                metric_name=metric_name,
                scenario_name=scenario_name,
                period_name=period_name,
            )

            if period_name not in destination_metric:

                destination_metric[
                    period_name
                ] = source_period

                continue

            destination_period = destination_metric[
                period_name
            ]

            merge_flat_table_rows(
                destination_period,
                source_period,
            )

            merge_chart_series(
                destination_period,
                source_period,
            )

def prepare_product_distribution_period(
    source_period,
    metric_name,
    scenario_name,
    period_name,
):
    source_table = source_period.setdefault(
        "table",
        {},
    )

    original_rows = deepcopy(
        source_table.get(
            "rows",
            [],
        )
    )

    product_rows = remove_total_rows(
        original_rows
    )

    value_length = get_value_length(
        product_rows
    )

    if metric_name == "market_share":
        grand_total_values = [100.0] * value_length
    else:
        grand_total_values = calculate_grand_total_values(
            rows=product_rows,
        )

    target_metric = metric_display_name(
        metric_name
    )

    formatted_rows = [
        {
            "label": build_grand_total_label(
                scenario_name
            ),
            "target_metric": target_metric,
            "values": grand_total_values,
        }
    ]

    for row in product_rows:

        product_label = str(
            row.get("label", "")
        ).strip()

        formatted_row = deepcopy(row)

        formatted_row["label"] = build_scenario_row_label(
            label=product_label,
            scenario_name=scenario_name,
        )

        formatted_row["target_metric"] = target_metric

        # Product distribution is always flat
        formatted_row.pop(
            "children",
            None,
        )

        formatted_rows.append(
            formatted_row
        )

    source_table["type"] = "flat"

    source_table["headers"] = build_table_headers(
        source_period=source_period,
        period_name=period_name,
    )

    source_table["rows"] = formatted_rows

    prepare_product_distribution_chart(
        source_period=source_period,
        scenario_name=scenario_name,
    )

def prepare_product_distribution_chart(
    source_period,
    scenario_name,
):
    chart = source_period.setdefault(
        "chart",
        {},
    )

    scenario_label = clean_scenario_label(
        scenario_name
    )

    chart_series = []

    for series in chart.get(
        "series",
        [],
    ):

        if not isinstance(series, dict):
            continue

        item = deepcopy(series)

        label = str(
            item.get(
                "label",
                ""
            )
        ).strip()

        if not label:
            continue

        if label.lower() in {
            "overall",
            "total",
            "grand total",
            "all",
        }:
            continue

        item["label"] = (
            f"{label} ({scenario_label})"
        )

        chart_series.append(item)

    chart["series"] = chart_series



def merge_market_product(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get("market_product", {})
    )

    destination = output_tabs.setdefault(
        "market_product",
        {}
    )

    for metric_name, metric_data in source.items():

        # Example:
        # metric_name = "market_volume"
        # metric_name = "market_share"

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {}
        )

        # Preserve unit at metric level
        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(period_name)

            if not isinstance(source_period, dict):
                continue

            source_table = source_period.get("table", {})
            source_rows = source_table.get("rows", [])

            # Remove synthetic rows such as Overall
            market_rows = remove_overall_rows(
                source_rows
            )

            scenario_root = build_market_product_root(
                rows=market_rows,
                scenario_name=scenario_name,
                metric_name=metric_name,
            )

            source_table["rows"] = [scenario_root]

            # Add required table metadata
            source_table["type"] = "hierarchy"

            add_target_metric_to_hierarchy(
                source_table["rows"],
                metric_name,
            )

            ensure_table_headers(
                table=source_table,
                period=period_name,
                period_data=source_period,
            )

            rename_market_product_chart_series(
                source_period=source_period,
                scenario_name=scenario_name,
            )

            # First scenario
            if period_name not in destination_metric:
                destination_metric[period_name] = source_period
                continue

            destination_period = destination_metric[
                period_name
            ]

            destination_table = destination_period.setdefault(
                "table",
                {
                    "type": "hierarchy",
                    "headers": source_table.get(
                        "headers",
                        [],
                    ),
                    "rows": [],
                },
            )

            destination_table.setdefault(
                "rows",
                []
            ).append(scenario_root)

            merge_chart_series(
                destination_period=destination_period,
                source_period=source_period,
            )
def build_market_product_root(
    rows,
    scenario_name,
    metric_name,
):
    rows = deepcopy(rows)

    value_length = get_hierarchy_value_length(rows)

    if metric_name == "market_volume":
        root_values = sum_top_level_values(
            rows,
            value_length,
        )

    elif metric_name == "market_share":
        root_values = [100.0] * value_length

    else:
        root_values = sum_top_level_values(
            rows,
            value_length,
        )

    return {
        "label": f"Grand Total ({scenario_name})",
        "target_metric": metric_display_name(
            metric_name
        ),
        "values": root_values,
        "children": rows,
    }

def remove_overall_rows(rows):
    excluded_labels = {
        "overall",
        "total",
        "grand total",
        "all",
    }

    cleaned_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        label = str(
            row.get("label", "")
        ).strip().lower()

        if label in excluded_labels:
            continue

        cleaned_rows.append(
            deepcopy(row)
        )

    return cleaned_rows

def sum_top_level_values(
    rows,
    value_length,
):
    totals = [0.0] * value_length

    for row in rows:
        values = row.get("values", [])

        if not isinstance(values, list):
            continue

        for index, value in enumerate(
            values[:value_length]
        ):
            if isinstance(value, (int, float)):
                totals[index] += value

    return [
        round(value)
        for value in totals
    ]

def add_target_metric_to_hierarchy(
    rows,
    metric_name,
):
    target_metric = metric_display_name(
        metric_name
    )

    for row in rows:
        if not isinstance(row, dict):
            continue

        row["target_metric"] = target_metric

        children = row.get("children", [])

        if isinstance(children, list):
            add_target_metric_to_hierarchy(
                children,
                metric_name,
            )
def metric_display_name(metric_name):
    mapping = {
        "market_volume": "Market Volume",
        "market_share": "Market Share",
    }

    return mapping.get(
        metric_name,
        metric_name.replace("_", " ").title(),
    )

def get_hierarchy_value_length(rows):
    for row in rows:
        if not isinstance(row, dict):
            continue

        values = row.get("values")

        if isinstance(values, list):
            return len(values)

    return 0

def ensure_table_headers(
    table,
    period,
    period_data,
):
    if table.get("headers"):
        return

    chart = period_data.get("chart", {})

    if period == "monthly":
        periods = chart.get("months", [])

    else:
        periods = chart.get("years", [])

    table["headers"] = [
        "Metric",
        *periods,
    ]
from datetime import datetime


def convert_month_header(month_label):
    try:
        return datetime.strptime(
            month_label,
            "%b-%y",
        ).strftime("%Y-%m")
    except (TypeError, ValueError):
        return month_label

def ensure_table_headers(
    table,
    period,
    period_data,
):
    if table.get("headers"):
        return

    chart = period_data.get("chart", {})

    if period == "monthly":
        periods = [
            convert_month_header(month)
            for month in chart.get("months", [])
        ]
    else:
        periods = chart.get("years", [])

    table["headers"] = [
        "Metric",
        *periods,
    ]

def rename_market_product_chart_series(
    source_period,
    scenario_name,
):
    chart = source_period.get("chart")

    if not isinstance(chart, dict):
        return

    for series_item in chart.get("series", []):
        if not isinstance(series_item, dict):
            continue

        label = str(
            series_item.get("label", "")
        ).strip()

        if label:
            series_item["label"] = (
                f"{label} ({scenario_name})"
            )
def merge_chart_series(
    destination_period,
    source_period,
):
    source_chart = source_period.get("chart")

    if not isinstance(source_chart, dict):
        return

    destination_chart = destination_period.setdefault(
        "chart",
        {}
    )

    # Preserve months, years and forecast_start_index
    for key, value in source_chart.items():
        if key == "series":
            continue

        destination_chart.setdefault(
            key,
            deepcopy(value),
        )

    destination_chart.setdefault(
        "series",
        []
    ).extend(
        deepcopy(
            source_chart.get("series", [])
        )
    )



def merge_product_market(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "product_market",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "product_market",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(source_period, dict):
                continue

            source_table = source_period.get(
                "table",
                {}
            )

            product_rows = remove_overall_rows(
                source_table.get(
                    "rows",
                    [],
                )
            )

            scenario_root = build_product_market_root(
                rows=product_rows,
                scenario_name=scenario_name,
                metric_name=metric_name,
            )

            source_table["type"] = "hierarchy"
            source_table["rows"] = [scenario_root]

            add_target_metric_to_hierarchy(
                source_table["rows"],
                metric_name,
            )

            ensure_table_headers(
                source_table,
                period_name,
                source_period,
            )

            rename_product_market_chart_series(
                source_period,
                scenario_name,
            )

            if period_name not in destination_metric:

                destination_metric[
                    period_name
                ] = source_period

                continue

            destination_period = destination_metric[
                period_name
            ]

            destination_table = (
                destination_period.setdefault(
                    "table",
                    {
                        "type": "hierarchy",
                        "headers": source_table.get(
                            "headers",
                            [],
                        ),
                        "rows": [],
                    },
                )
            )

            destination_table.setdefault(
                "rows",
                [],
            ).append(
                scenario_root
            )

            merge_chart_series(
                destination_period,
                source_period,
            )
def build_product_market_root(
    rows,
    scenario_name,
    metric_name,
):
    rows = deepcopy(rows)

    value_length = get_hierarchy_value_length(
        rows
    )

    if metric_name == "market_volume":

        values = sum_top_level_values(
            rows,
            value_length,
        )

    elif metric_name == "market_share":

        values = [100.0] * value_length

    else:

        values = sum_top_level_values(
            rows,
            value_length,
        )

    return {
        "label": f"Grand Total ({scenario_name})",
        "target_metric": metric_display_name(
            metric_name
        ),
        "values": values,
        "children": rows,
    }

def rename_product_market_chart_series(
    source_period,
    scenario_name,
):
    chart = source_period.get(
        "chart"
    )

    if not isinstance(chart, dict):
        return

    for series in chart.get(
        "series",
        [],
    ):

        label = str(
            series.get(
                "label",
                "",
            )
        ).strip()

        if label:

            series["label"] = (
                f"{label} ({scenario_name})"
            )

def normalize_filter_values(values):
    if values is None:
        return []

    if isinstance(values, str):
        values = [values]

    return [
        str(value).strip()
        for value in values
        if value
        and str(value).strip().lower() != "all"
    ]


def filter_table_top_level_rows(
    table,
    selected_values,
):
    """
    Filters top-level hierarchy rows while always retaining Overall.

    Children of the selected parent are preserved.
    """

    if not isinstance(table, dict):
        return

    rows = table.get("rows")

    if not isinstance(rows, list):
        return

    if not selected_values:
        return

    selected_keys = {
        str(value).strip().lower()
        for value in selected_values
    }

    filtered_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        label = str(
            row.get("label", "")
        ).strip()

        label_key = label.lower()

        if label_key in {
            "overall",
            "grand total",
        }:
            filtered_rows.append(row)
            continue

        if label_key in selected_keys:
            filtered_rows.append(row)

    table["rows"] = filtered_rows


def filter_section_tables(
    section,
    selected_values,
):
    """
    Applies the same filter to:
      - market_volume monthly table
      - market_volume yearly table
      - market_share monthly table
      - market_share yearly table
    """

    if not isinstance(section, dict):
        return

    for metric_name in (
        "market_volume",
        "market_share",
    ):
        metric_data = section.get(metric_name)

        if not isinstance(metric_data, dict):
            continue

        for period_name in (
            "monthly",
            "yearly",
        ):
            period_data = metric_data.get(period_name)

            if not isinstance(period_data, dict):
                continue

            filter_table_top_level_rows(
                table=period_data.get("table"),
                selected_values=selected_values,
            )


def apply_market_analysis_table_filters(
    market_analysis,
    selected_markets,
    selected_products,
):
    """
    Applies filters to monthly and yearly tables.

    market_distribution:
        filter market rows

    product_distribution:
        filter product rows

    market_product:
        filter market parents
        filter product children

    product_market:
        filter product parents
        filter market children
    """

    # Channel Distribution
    filter_section_tables(
        section=market_analysis.get(
            "market_distribution"
        ),
        selected_values=selected_markets,
    )

    # Product Distribution
    filter_section_tables(
        section=market_analysis.get(
            "product_distribution"
        ),
        selected_values=selected_products,
    )

    # Channel-Product
    filter_hierarchy_section_tables(
        section=market_analysis.get(
            "market_product"
        ),
        selected_parents=selected_markets,
        selected_children=selected_products,
    )

    # Product-Channel
    filter_hierarchy_section_tables(
        section=market_analysis.get(
            "product_market"
        ),
        selected_parents=selected_products,
        selected_children=selected_markets,
    )

    return market_analysis

def filter_hierarchy_table(
    table,
    selected_parents,
    selected_children,
):
    """
    Filters both levels of a hierarchy table.

    Example market_product:
        parent  = market
        children = products

    Example product_market:
        parent  = product
        children = markets
    """

    if not isinstance(table, dict):
        return

    rows = table.get("rows")

    if not isinstance(rows, list):
        return

    parent_keys = {
        str(value).strip().lower()
        for value in (selected_parents or [])
        if value
        and str(value).strip().lower() != "all"
    }

    child_keys = {
        str(value).strip().lower()
        for value in (selected_children or [])
        if value
        and str(value).strip().lower() != "all"
    }

    filtered_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        row_label = str(
            row.get("label", "")
        ).strip()

        row_key = row_label.lower()

        # Keep Overall/Grand Total if present
        if row_key in {
            "overall",
            "grand total",
        }:
            filtered_rows.append(row)
            continue

        # Filter parent
        if parent_keys and row_key not in parent_keys:
            continue

        filtered_row = dict(row)

        children = row.get("children")

        if isinstance(children, list):
            filtered_children = []

            for child in children:
                if not isinstance(child, dict):
                    continue

                child_label = str(
                    child.get("label", "")
                ).strip()

                child_key = child_label.lower()

                if (
                    not child_keys
                    or child_key in child_keys
                ):
                    filtered_children.append(child)

            filtered_row["children"] = (
                filtered_children
            )

        filtered_rows.append(filtered_row)

    table["rows"] = filtered_rows

def filter_hierarchy_section_tables(
    section,
    selected_parents,
    selected_children,
):
    """
    Filters monthly and yearly tables for both metrics.
    """

    if not isinstance(section, dict):
        return

    for metric_name in (
        "market_volume",
        "market_share",
    ):
        metric_data = section.get(
            metric_name
        )

        if not isinstance(metric_data, dict):
            continue

        for period_name in (
            "monthly",
            "yearly",
        ):
            period_data = metric_data.get(
                period_name
            )

            if not isinstance(period_data, dict):
                continue

            filter_hierarchy_table(
                table=period_data.get("table"),
                selected_parents=selected_parents,
                selected_children=selected_children,
            )

