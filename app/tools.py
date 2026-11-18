"""PMFBY agent tools for FasalBima Sathi (Days 9 & 10).

Official Reference:
- Revamped Operational Guidelines (Kharif 2020 onwards), Ministry of Agriculture & Farmers Welfare, GoI.
  - Para 13.1 Table 1: Statutory Maximum Premium Rates payable by farmer (% of Sum Insured).
  - Para 15.1.2 & 15.2.2: Localized Calamities & Post-Harvest Losses 72-hour Intimation Rule.
- Verified against pmfby.gov.in guidelines.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Optional
import zoneinfo

from app.records import load_records
from app.vectorstore import query_semantic

ROOT = Path(__file__).resolve().parent.parent
RECORDS_PATH = ROOT / "data" / "records.json"
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# Precise standard agricultural conversions
ACRES_TO_HECTARES = Decimal("0.404686")
HECTARES_TO_ACRES = Decimal("2.471054")

# Statutory PMFBY maximum farmer premium rates (% of Sum Insured)
# Source: Revamped OG, Para 13.1 Table 1
DEFAULT_RATE_MAP = {
    "kharif_foodgrain_oilseed": Decimal("2.0"),    # Kharif food grains, cereals, pulses, and oilseeds
    "rabi_foodgrain_oilseed": Decimal("1.5"),      # Rabi food grains, cereals, pulses, and oilseeds
    "commercial_horticultural": Decimal("5.0"),    # Annual commercial & annual horticultural crops
}

# Verified crop-to-category associations under PMFBY
CROP_CATEGORY_MAP = {
    # Kharif foodgrain / oilseeds
    "soybean": ("kharif", "kharif_foodgrain_oilseed"),
    "soya": ("kharif", "kharif_foodgrain_oilseed"),
    "paddy": ("kharif", "kharif_foodgrain_oilseed"),
    "rice": ("kharif", "kharif_foodgrain_oilseed"),
    "maize": ("kharif", "kharif_foodgrain_oilseed"),
    "corn": ("kharif", "kharif_foodgrain_oilseed"),
    "jowar": ("kharif", "kharif_foodgrain_oilseed"),
    "sorghum": ("kharif", "kharif_foodgrain_oilseed"),
    "bajra": ("kharif", "kharif_foodgrain_oilseed"),
    "pearl millet": ("kharif", "kharif_foodgrain_oilseed"),
    "tur": ("kharif", "kharif_foodgrain_oilseed"),
    "arhar": ("kharif", "kharif_foodgrain_oilseed"),
    "pigeon pea": ("kharif", "kharif_foodgrain_oilseed"),
    "moong": ("kharif", "kharif_foodgrain_oilseed"),
    "urad": ("kharif", "kharif_foodgrain_oilseed"),
    "groundnut": ("kharif", "kharif_foodgrain_oilseed"),
    "peanut": ("kharif", "kharif_foodgrain_oilseed"),
    "sunflower": ("kharif", "kharif_foodgrain_oilseed"),
    "sesamum": ("kharif", "kharif_foodgrain_oilseed"),

    # Rabi foodgrain / oilseeds
    "wheat": ("rabi", "rabi_foodgrain_oilseed"),
    "gram": ("rabi", "rabi_foodgrain_oilseed"),
    "chickpea": ("rabi", "rabi_foodgrain_oilseed"),
    "chana": ("rabi", "rabi_foodgrain_oilseed"),
    "mustard": ("rabi", "rabi_foodgrain_oilseed"),
    "barley": ("rabi", "rabi_foodgrain_oilseed"),
    "rabi jowar": ("rabi", "rabi_foodgrain_oilseed"),

    # Commercial / horticultural
    "cotton": ("annual", "commercial_horticultural"),
    "sugarcane": ("annual", "commercial_horticultural"),
    "onion": ("annual", "commercial_horticultural"),
    "potato": ("annual", "commercial_horticultural"),
    "tomato": ("annual", "commercial_horticultural"),
    "chilli": ("annual", "commercial_horticultural"),
    "banana": ("annual", "commercial_horticultural"),
    "turmeric": ("annual", "commercial_horticultural"),
    "pomegranate": ("annual", "commercial_horticultural"),
}


def load_rate_table_from_records() -> Dict[str, Dict[str, Any]]:
    """Extract official premium rates directly from records.json.

    Strictly refuses to substitute hardcoded rates when records are missing,
    malformed, ambiguous, or conflicting.
    """
    records = load_records()
    if not records:
        raise ValueError(
            "Official PMFBY records are missing or empty in data/records.json. "
            "Cannot verify statutory premium rates from official evidence."
        )

    rate_table: Dict[str, Dict[str, Any]] = {}

    for r in records:
        text = (r.get("rule_topic", "") + " " + r.get("rule_text", "")).lower()
        deadline_or_rate = str(r.get("deadline_or_rate", "")).strip()
        version = r.get("og_version", "Revamped OG (Kharif 2020 onwards)")

        # Only process records that define premium caps or rates
        if "premium cap" not in text and "premium rate" not in text:
            continue

        cat = None
        if "kharif" in text and ("food" in text or "oilseed" in text):
            cat = "kharif_foodgrain_oilseed"
        elif "rabi" in text and ("food" in text or "oilseed" in text):
            cat = "rabi_foodgrain_oilseed"
        elif "commercial" in text or "horticultural" in text:
            cat = "commercial_horticultural"

        if cat:
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", deadline_or_rate)
            if not match:
                raise ValueError(
                    f"Malformed rate evidence in records.json for {cat}: "
                    f"'{deadline_or_rate}' lacks a valid numeric percentage."
                )
            try:
                rate_dec = Decimal(match.group(1))
            except Exception:
                raise ValueError(
                    f"Malformed rate percentage '{match.group(1)}' for {cat} in records.json."
                )

            # Check for conflicting rates in the same category from different records
            if cat in rate_table and rate_table[cat]["rate_percent"] != rate_dec:
                prev_ver = rate_table[cat]["og_version"]
                if prev_ver != version:
                    raise ValueError(
                        f"Conflicting statutory rates found in records.json for {cat}: "
                        f"{rate_table[cat]['rate_percent']}% ({prev_ver}) vs {rate_dec}% ({version}). "
                        "Conflicting guideline versions require explicit notification clarification."
                    )

            rate_table[cat] = {
                "rate_percent": rate_dec,
                "record_id": r.get("id"),
                "rule_topic": r.get("rule_topic"),
                "og_version": version,
                "source_url": r.get("source_url"),
            }

    # Verify that required statutory categories are covered by authentic records
    for key in ("kharif_foodgrain_oilseed", "rabi_foodgrain_oilseed", "commercial_horticultural"):
        if key not in rate_table:
            raise ValueError(
                f"Missing statutory rate evidence for '{key}' in records.json. "
                "Cannot compute farmer premium without official guideline records."
            )

    return rate_table


def _validate_numeric(val: Any, field_name: str, allow_zero: bool = False, max_val: Optional[float] = None) -> Decimal:
    """Validate numeric input rejecting booleans, NaN, Inf, non-numbers, and invalid bounds."""
    if isinstance(val, bool):
        raise ValueError(f"{field_name} must be a number, not a boolean.")
    try:
        f_val = float(val)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid numeric amount.")

    if math.isnan(f_val) or math.isinf(f_val):
        raise ValueError(f"{field_name} cannot be NaN or infinity.")

    if allow_zero:
        if f_val < 0:
            raise ValueError(f"{field_name} cannot be negative.")
    else:
        if f_val <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")

    if max_val is not None and f_val > max_val:
        raise ValueError(f"{field_name} cannot exceed {max_val}.")

    return Decimal(str(val))


def resolve_crop_and_category(
    crop: Optional[str],
    season: Optional[str] = None,
    crop_type: Optional[str] = None,
) -> tuple[str, str, str]:
    """Resolve normalized crop name, season ('kharif'/'rabi'/'annual'), and rate category.

    Raises ValueError if evidence is missing, conflicting, or ambiguous.
    """
    if not crop and not crop_type:
        raise ValueError("Crop name is required. Please specify the crop (e.g. 'soybean', 'wheat', 'cotton').")

    crop_clean = (crop or "").strip().lower()
    season_clean = (season or "").strip().lower()
    type_clean = (crop_type or "").strip().lower()

    # Direct category override if provided
    if type_clean in ("kharif_foodgrain_oilseed", "rabi_foodgrain_oilseed", "commercial_horticultural"):
        resolved_season = season_clean or ("rabi" if "rabi" in type_clean else "kharif")
        return crop_clean or type_clean, resolved_season, type_clean

    # Known crop lookup
    if crop_clean in CROP_CATEGORY_MAP:
        default_season, category = CROP_CATEGORY_MAP[crop_clean]
        if season_clean:
            # Validate season/crop consistency against PMFBY classifications
            if crop_clean in ("wheat", "gram", "mustard", "barley", "chickpea", "chana") and season_clean == "kharif":
                raise ValueError(
                    f"Conflicting season/crop: '{crop.title()}' is classified as a Rabi foodgrain crop under PMFBY guidelines. "
                    "Cannot calculate under Kharif season without official state notification evidence."
                )
            if crop_clean in ("soybean", "soya", "paddy", "rice", "cotton", "tur", "groundnut", "maize") and season_clean == "rabi":
                raise ValueError(
                    f"Conflicting season/crop: '{crop.title()}' is classified as a Kharif/Annual crop under PMFBY guidelines. "
                    "Cannot calculate under Rabi season without official state notification evidence."
                )
            resolved_season = season_clean
        else:
            resolved_season = default_season

        return crop_clean, resolved_season, category

    # Check for category hints in season or crop_type
    if "commercial" in season_clean or "horticultur" in season_clean or "commercial" in type_clean:
        return crop_clean or "commercial crop", "annual", "commercial_horticultural"
    if "rabi" in season_clean or "rabi" in type_clean:
        return crop_clean or "rabi crop", "rabi", "rabi_foodgrain_oilseed"
    if "kharif" in season_clean or "kharif" in type_clean:
        return crop_clean or "kharif crop", "kharif", "kharif_foodgrain_oilseed"

    raise ValueError(
        f"Unable to determine statutory rate: crop '{crop}' not found in official PMFBY records.json. "
        "Please specify season ('kharif', 'rabi', or 'annual commercial/horticultural')."
    )


def pmfby_premium(
    scale_of_finance: Any,
    area: Any,
    crop: Optional[str] = None,
    season: Optional[str] = None,
    crop_type: Optional[str] = None,
    area_unit: str = "ha",
    scale_of_finance_unit: str = "per_ha",
    actuarial_rate: Optional[Any] = None,
    unit: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculates sum insured (scale of finance x area) and farmer's premium share

    using season and crop-type rates stored in records.json.
    Uses pure arithmetic with Python Decimal and ROUND_HALF_UP rounding.

    Args:
        scale_of_finance: Scale of finance amount.
        area: Insured crop area.
        crop: Crop name (e.g. 'soybean', 'wheat', 'cotton').
        season: Season ('kharif', 'rabi', 'annual').
        crop_type: Specific category key.
        area_unit: Area unit ('ha', 'hectare', 'hectares', 'acre', 'acres').
        scale_of_finance_unit: Scale of finance unit ('per_ha', 'per_hectare', 'per_acre').
        actuarial_rate: Total actuarial premium rate percent (must be > 0 if provided).
        unit: Backward-compatibility alias for area_unit.

    Returns:
        Dict with exact Decimal results, calculation breakdown, and rule reference.
    """
    if unit is not None:
        area_unit = unit
    if scale_of_finance is None:
        raise ValueError("scale_of_finance is required. Please specify the scale of finance in ₹.")
    if area is None:
        raise ValueError("area is required. Please specify the insured crop area.")

    sof_raw_dec = _validate_numeric(scale_of_finance, "scale_of_finance", allow_zero=False)
    area_raw_dec = _validate_numeric(area, "area", allow_zero=False)

    actuarial_dec: Optional[Decimal] = None
    if actuarial_rate is not None:
        # Actuarial rate in PMFBY must be a positive percentage > 0
        if isinstance(actuarial_rate, bool):
            raise ValueError("actuarial_rate must be a number, not a boolean.")
        try:
            act_val = float(actuarial_rate)
        except (TypeError, ValueError):
            raise ValueError("actuarial_rate must be a valid numeric percentage.")
        if act_val <= 0:
            raise ValueError("Actuarial rate must be a positive percentage greater than 0%.")
        if act_val > 100:
            raise ValueError("Actuarial rate cannot exceed 100%.")
        actuarial_dec = Decimal(str(actuarial_rate))

    # Normalize units
    a_unit = (area_unit or "ha").strip().lower()
    sof_unit = (scale_of_finance_unit or "per_ha").strip().lower()

    if a_unit not in {"ha", "hectare", "hectares", "acre", "acres"}:
        raise ValueError(
            f"Unsupported area unit '{area_unit}'. Supported units are hectares ('ha', 'hectare') or acres ('acre', 'acres')."
        )
    if sof_unit not in {"per_ha", "per_hectare", "ha", "per_acre", "acre"}:
        raise ValueError(
            f"Unsupported scale of finance unit '{scale_of_finance_unit}'. Supported units are 'per_ha' or 'per_acre'."
        )

    # Unit conversion arithmetic:
    # 1. Normalize area to hectares
    is_acre_area = a_unit in {"acre", "acres"}
    is_per_acre_sof = sof_unit in {"per_acre", "acre"}

    if is_acre_area:
        area_ha_dec = (area_raw_dec * ACRES_TO_HECTARES).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        area_ha_dec = area_raw_dec

    # 2. Compute Sum Insured matching units
    if is_acre_area and is_per_acre_sof:
        # Both in acres: scale_of_finance (₹/acre) * area (acres)
        sum_insured_dec = (sof_raw_dec * area_raw_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sof_per_ha_dec = (sof_raw_dec * HECTARES_TO_ACRES).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        conversion_desc = f"{area_raw_dec} acres @ ₹{sof_raw_dec:,.2f}/acre"
    elif is_acre_area and not is_per_acre_sof:
        # Area in acres, SOF in ₹/ha: convert area to ha
        sum_insured_dec = (sof_raw_dec * area_ha_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sof_per_ha_dec = sof_raw_dec
        conversion_desc = f"{area_raw_dec} acres ({area_ha_dec} ha converted at 1 acre = 0.404686 ha) @ ₹{sof_raw_dec:,.2f}/ha"
    elif not is_acre_area and is_per_acre_sof:
        # Area in ha, SOF in ₹/acre: convert SOF to ₹/ha
        sof_per_ha_dec = (sof_raw_dec * HECTARES_TO_ACRES).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sum_insured_dec = (sof_per_ha_dec * area_raw_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        conversion_desc = f"{area_raw_dec} ha @ ₹{sof_raw_dec:,.2f}/acre (converted to ₹{sof_per_ha_dec:,.2f}/ha)"
    else:
        # Standard: Both in hectares
        sum_insured_dec = (sof_raw_dec * area_raw_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sof_per_ha_dec = sof_raw_dec
        conversion_desc = f"{area_raw_dec} ha @ ₹{sof_raw_dec:,.2f}/ha"

    # 3. Resolve crop and rate category from records.json
    crop_name, resolved_season, category = resolve_crop_and_category(crop, season, crop_type)
    rate_table = load_rate_table_from_records()
    category_info = rate_table.get(category)
    if not category_info:
        raise ValueError(
            f"Statutory rate evidence for category '{category}' could not be verified in official records.json."
        )
    statutory_cap = category_info["rate_percent"]

    # 4. Determine applicable rate and estimate vs exact
    if actuarial_dec is not None:
        farmer_rate = min(statutory_cap, actuarial_dec)
        is_estimated_maximum = False
        rate_note = (
            f"Exact farmer premium rate = {farmer_rate:.2f}% (actuarial tender rate {actuarial_dec:.2f}% "
            f"vs statutory cap {statutory_cap:.2f}% under PMFBY Para 13.1)."
        )
    else:
        farmer_rate = statutory_cap
        is_estimated_maximum = True
        rate_note = (
            f"Estimated maximum farmer premium (capped at {farmer_rate:.1f}% statutory ceiling under PMFBY Para 13.1). "
            "Actual farmer premium may be lower if district tender actuarial rate is lower."
        )

    # 5. Pure arithmetic for Farmer's Premium Share
    farmer_premium_dec = (sum_insured_dec * (farmer_rate / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    total_premium_dec: Optional[Decimal] = None
    subsidy_dec: Optional[Decimal] = None
    if actuarial_dec is not None:
        total_premium_dec = (sum_insured_dec * (actuarial_dec / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        subsidy_dec = total_premium_dec - farmer_premium_dec

    breakdown = (
        f"Sum Insured = Scale of Finance × Area ({conversion_desc}) = ₹{sum_insured_dec:,.2f}. "
        f"Farmer Premium Rate = {farmer_rate:.2f}% ({resolved_season.title()} {category.replace('_', ' ')}). "
        f"{'Estimated Maximum ' if is_estimated_maximum else ''}Farmer Premium Share = ₹{sum_insured_dec:,.2f} × {farmer_rate:.2f}% = ₹{farmer_premium_dec:,.2f}."
    )

    return {
        "status": "success",
        "crop": crop_name,
        "season": resolved_season,
        "category": category,
        "area_raw": float(area_raw_dec),
        "area_unit": "acre" if is_acre_area else "ha",
        "area_ha": float(area_ha_dec),
        "scale_of_finance_raw": float(sof_raw_dec),
        "scale_of_finance_unit": "per_acre" if is_per_acre_sof else "per_ha",
        "scale_of_finance_per_ha": float(sof_per_ha_dec),
        "sum_insured": float(sum_insured_dec),
        "farmer_rate_percent": float(farmer_rate),
        "farmer_premium": float(farmer_premium_dec),
        "is_estimated_maximum": is_estimated_maximum,
        "rate_note": rate_note,
        "actuarial_rate_percent": float(actuarial_dec) if actuarial_dec is not None else None,
        "total_premium": float(total_premium_dec) if total_premium_dec is not None else None,
        "govt_subsidy": float(subsidy_dec) if subsidy_dec is not None else None,
        "breakdown": breakdown,
        "rule_reference": {
            "record_id": category_info.get("record_id"),
            "rule_topic": category_info.get("rule_topic"),
            "og_version": category_info.get("og_version"),
            "source_url": category_info.get("source_url"),
        },
    }


def parse_loss_timestamp(loss_input: Any, now: Optional[datetime] = None) -> datetime:
    """Parse actual supplied loss date/time into an Asia/Kolkata timezone-aware datetime.

    Requires both date and approximate time; rejects future timestamps and invalid formats.
    """
    if now is None:
        clock_now = datetime.now(tz=IST)
    elif now.tzinfo is None:
        clock_now = now.replace(tzinfo=IST)
    else:
        clock_now = now.astimezone(IST)

    if isinstance(loss_input, datetime):
        dt = loss_input if loss_input.tzinfo else loss_input.replace(tzinfo=IST)
        if dt > clock_now:
            raise ValueError("Loss event date cannot be in the future. Please provide when the calamity occurred.")
        return dt

    s = str(loss_input).strip()
    if not s:
        raise ValueError("Loss date/time is required. Please provide when the loss occurred.")

    low = s.lower()

    # Relative expressions
    if "yesterday" in low:
        loss_date = (clock_now - timedelta(days=1)).date()
        t_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
        if t_match:
            hr = int(t_match.group(1))
            mn = int(t_match.group(2)) if t_match.group(2) else 0
            meridiem = t_match.group(3)
            if meridiem == "pm" and hr < 12:
                hr += 12
            elif meridiem == "am" and hr == 12:
                hr = 0
            loss_time = time(hr, mn)
        else:
            raise ValueError("Please provide the approximate time of loss (e.g. 'yesterday at 9 pm') to calculate the 72-hour window.")
        dt = datetime.combine(loss_date, loss_time, tzinfo=IST)
        if dt > clock_now:
            raise ValueError("Loss event date cannot be in the future.")
        return dt

    if "today" in low:
        loss_date = clock_now.date()
        t_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
        if t_match:
            hr = int(t_match.group(1))
            mn = int(t_match.group(2)) if t_match.group(2) else 0
            meridiem = t_match.group(3)
            if meridiem == "pm" and hr < 12:
                hr += 12
            elif meridiem == "am" and hr == 12:
                hr = 0
            loss_time = time(hr, mn)
        else:
            raise ValueError("Please provide the approximate time of loss (e.g. 'today at 10 am') to calculate the 72-hour window.")
        dt = datetime.combine(loss_date, loss_time, tzinfo=IST)
        if dt > clock_now:
            raise ValueError("Loss event date cannot be in the future.")
        return dt

    # Relative hours ago
    hrs_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s+ago", low)
    if hrs_match:
        delta_hrs = float(hrs_match.group(1))
        return clock_now - timedelta(hours=delta_hrs)

    # Date-only check: if format matches YYYY-MM-DD or DD-MM-YYYY without time, ask for time!
    date_only_match = re.match(r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})$", s)
    if date_only_match:
        raise ValueError(
            f"Date '{s}' provided without time. Please provide the approximate time of loss "
            "(e.g. '2026-11-16 21:00' or 'yesterday at 9 pm') to accurately calculate the 72-hour window."
        )

    # Explicit timestamp formats with date and time
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
    ):
        try:
            d = datetime.strptime(s, fmt).replace(tzinfo=IST)
            if d > clock_now:
                raise ValueError("Loss event date cannot be in the future. Please provide when the calamity occurred.")
            return d
        except ValueError as e:
            if "future" in str(e):
                raise

    raise ValueError(
        f"Invalid loss timestamp '{s}'. Please provide a valid date and time "
        "(e.g. 'YYYY-MM-DD HH:MM', 'yesterday at 9 pm', or '12 hours ago')."
    )


def pmfby_claim_deadline_check(
    loss_timestamp: Any,
    window_hours: int = 72,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calculates PMFBY 72-hour localized calamity / post-harvest intimation deadline.

    Official Source: Revamped Operational Guidelines (Kharif 2020 onwards), Para 15.1.2 & 15.2.2.
    """
    if now is None:
        clock_now = datetime.now(tz=IST)
    elif now.tzinfo is None:
        clock_now = now.replace(tzinfo=IST)
    else:
        clock_now = now.astimezone(IST)

    loss_dt = parse_loss_timestamp(loss_timestamp, now=clock_now)
    deadline_dt = loss_dt + timedelta(hours=window_hours)
    remaining_seconds = (deadline_dt - clock_now).total_seconds()
    remaining_hours = round(remaining_seconds / 3600.0, 1)

    return {
        "status": "success",
        "loss_timestamp": loss_dt.isoformat(),
        "deadline_timestamp": deadline_dt.isoformat(),
        "clock_timestamp": clock_now.isoformat(),
        "window_hours": window_hours,
        "remaining_hours": remaining_hours,
        "is_expired": remaining_hours <= 0,
        "reporting_channels": [
            "Crop Insurance App (National Crop Insurance Portal)",
            "Krishi Rakshak Helpline: 14447",
            "Concerned Insurance Company Toll-Free Number",
            "Bank Branch / PACS where premium was debited",
            "Local Agriculture Officer / Revenue Authority",
        ],
        "og_version": "Revamped OG (Kharif 2020 onwards), Para 15.1.2 & 15.2.2",
        "disclaimer": (
            "Note: The 72-hour notification clock applies specifically to localized calamities "
            "(hailstorm, landslide, inundation, cloudburst, natural fire) and post-harvest losses "
            "(up to 14 days for cut-and-spread crops). Widespread yield losses are assessed at season end "
            "via Crop Cutting Experiments (CCEs). This app calculates the deadline and does not file a formal claim."
        ),
    }


def pmfby_knowledge_search(query: str, top_k: int = 3, collection_name: Optional[str] = None) -> Dict[str, Any]:
    """RAG semantic search tool over PMFBY official guidelines chunks."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")
    hits = query_semantic(query, top_k=top_k, collection_name=collection_name or "fasalbima_sathi_chunks")
    return {
        "query": query,
        "count": len(hits),
        "hits": hits,
    }


AVAILABLE_TOOLS = {
    "pmfby_premium": pmfby_premium,
    "pmfby_knowledge_search": pmfby_knowledge_search,
    "pmfby_claim_deadline_check": pmfby_claim_deadline_check,
}
