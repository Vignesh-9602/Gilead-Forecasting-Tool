def normalize_market_share_months(
    edited_brand: str,
    months: list,
    precision: int = 2
):
    """
    Normalize each month so total = 100.
    Edited brand stays fixed.
    """

    normalized = []

    for entry in months:
        month = entry.month
        shares = {bs.brand: bs.value for bs in entry.market_share}

        if edited_brand not in shares:
            raise ValueError(f"{edited_brand} missing in {month}")

        edited_value = shares[edited_brand]
        remaining = 100.0 - edited_value

        others = {b: v for b, v in shares.items() if b != edited_brand}
        original_sum = sum(others.values())

        new_month = {
            "month": month,
            "market_share": []
        }

        if original_sum <= 0:
            new_month["market_share"].append({
                "brand": edited_brand,
                "value": round(edited_value, precision)
            })
            normalized.append(new_month)
            continue

        scale = remaining / original_sum

        total = edited_value
        temp = []

        for brand, value in others.items():
            new_val = round(value * scale, precision)
            total += new_val
            temp.append({"brand": brand, "value": new_val})

        # Fix rounding drift
        drift = round(100.0 - total, precision)
        if abs(drift) > 0 and temp:
            temp[0]["value"] = round(temp[0]["value"] + drift, precision)

        new_month["market_share"].append({
            "brand": edited_brand,
            "value": round(edited_value, precision)
        })
        new_month["market_share"].extend(temp)

        normalized.append(new_month)

    return normalized