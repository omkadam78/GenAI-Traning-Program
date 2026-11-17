"""PMFBY agent tools for FasalBima Sathi (Day 9).

Tools:
- pmfby_premium: Calculates sum insured (scale of finance x area) and
  the farmer's premium share using season and crop-type rates stored in records.json.
  Uses Python Decimal for exact monetary arithmetic and documented rounding.
- pmfby_knowledge_search: RAG semantic search over PMFBY official guidelines chunks.
- pmfby_claim_deadline_check: Computes the 72-hour localized calamity intimation deadline
  with injectable clock and Asia/Kolkata timezone support.
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

# 1 acre = 0.404686 hectares (standard Indian land measurement conversion)
ACRES_TO_HECTARES = Decimal("0.404686")

# Statutory PMFBY maximum premium caps payable by farmer (% of Sum Insured)
DEFAULT_RATE_MAP = {
    "kharif_foodgrain_oilseed": Decimal("2.0"),    # Kharif food grains and oilseeds
    "rabi_foodgrain_oilseed": Decimal("1.5"),      # Rabi food grains and oilseeds
    "commercial_horticultural": Decimal("5.0"),    # Annual commercial / horticultural
}

# Known crop-to-category associations under PMFBY
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
    """Extract official premium rates directly from records.json."""
    records = load_records()
    rate_table: Dict[str, Dict[str, Any]] = {}

    for r in records:
        text = (r.get("rule_topic", "") + " " + r.get("rule_text", "")).lower()
        deadline_or_rate = r.get("deadline_or_rate", "")

        if "kharif" in text and ("food" in text or "oilseed" in text):
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", deadline_or_rate)
            rate_dec = Decimal(match.group(1)) if match else Decimal("2.0")
            rate_table["kharif_foodgrain_oilseed"] = {
                "rate_percent": rate_dec,
                "record_id": r.get("id"),
                "rule_topic": r.get("rule_topic"),
                "og_version": r.get("og_version"),
                "source_url": r.get("source_url"),
            }
        elif "rabi" in text and ("food" in text or "oilseed" in text):
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", deadline_or_rate)
            rate_dec = Decimal(match.group(1)) if match else Decimal("1.5")
            rate_table["rabi_foodgrain_oilseed"] = {
                "rate_percent": rate_dec,
                "record_id": r.get("id"),
                "rule_topic": r.get("rule_topic"),
                "og_version": r.get("og_version"),
                "source_url": r.get("source_url"),
            }
        elif "commercial" in text or "horticultural" in text:
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", deadline_or_rate)
            rate_dec = Decimal(match.group(1)) if match else Decimal("5.0")
            rate_table["commercial_horticultural"] = {
                "rate_percent": rate_dec,
                "record_id": r.get("id"),
                "rule_topic": r.get("rule_topic"),
                "og_version": r.get("og_version"),
                "source_url": r.get("source_url"),
            }

    # Fallback to standard defaults if any record was missing
    for key, default_rate in DEFAULT_RATE_MAP.items():
        if key not in rate_table:
            rate_table[key] = {
                "rate_percent": default_rate,
                "record_id": None,
                "rule_topic": key.replace("_", " ").title(),
                "og_version": "Revamped OG (Kharif 2020), Para 13.1 Table 1",
                "source_url": "https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf",
            }

    return rate_table


def _validate_numeric(val: Any, field_name: str, allow_zero: bool = False, max_val: Optional[float] = None) -> Decimal:
    """Validate numeric input rejecting booleans, NaN, Inf, and non-numbers."""
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

    Raises ValueError if evidence is missing or ambiguous.
    """
    if not crop and not crop_type:
        raise ValueError("Crop name is required. Please specify the crop (e.g. 'soybean', 'wheat', 'cotton').")

    crop_clean = (crop or "").strip().lower()
    season_clean = (season or "").strip().lower()
    type_clean = (crop_type or "").strip().lower()

    # Direct category override if provided
    if type_clean in DEFAULT_RATE_MAP:
        resolved_season = season_clean or ("rabi" if "rabi" in type_clean else "kharif")
        return crop_clean or type_clean, resolved_season, type_clean

    # Known crop lookup
    if crop_clean in CROP_CATEGORY_MAP:
        default_season, category = CROP_CATEGORY_MAP[crop_clean]
        # Respect explicit season override
        resolved_season = season_clean if season_clean in {"kharif", "rabi", "annual", "summer"} else default_season
        if resolved_season == "rabi" and category == "kharif_foodgrain_oilseed":
            category = "rabi_foodgrain_oilseed"
        elif resolved_season == "kharif" and category == "rabi_foodgrain_oilseed":
            category = "kharif_foodgrain_oilseed"
        return crop_clean, resolved_season, category

    # Check for category hints in season or crop_type
    if "commercial" in season_clean or "horticultur" in season_clean or "commercial" in type_clean:
        return crop_clean or "commercial crop", "annual", "commercial_horticultural"
    if "rabi" in season_clean or "rabi" in type_clean:
        return crop_clean or "rabi crop", "rabi", "rabi_foodgrain_oilseed"
    if "kharif" in season_clean or "kharif" in type_clean:
        return crop_clean or "kharif crop", "kharif", "kharif_foodgrain_oilseed"

    # Ambiguous / unverified crop without season
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
    unit: str = "ha",
    actuarial_rate: Optional[Any] = None,
) -> Dict[str, Any]:
    """Calculates sum insured (scale of finance x area) and farmer's premium share

    using season and crop-type rates stored in records.json.
    Uses pure arithmetic with Python Decimal and ROUND_HALF_UP rounding.

    Args:
        scale_of_finance: Scale of finance in INR per hectare (or per acre).
        area: Insured crop area.
        crop: Crop name (e.g. 'soybean', 'wheat', 'cotton').
        season: Season ('kharif', 'rabi', 'annual').
        crop_type: Specific category key.
        unit: Area unit ('ha', 'hectare', 'hectares', 'acre', 'acres').
        actuarial_rate: Total actuarial premium rate percent if known.

    Returns:
        Dict with exact Decimal results, calculation breakdown, and rule reference.
    """
    # 1. Validate numeric inputs
    sof_dec = _validate_numeric(scale_of_finance, "scale_of_finance", allow_zero=False)
    area_raw_dec = _validate_numeric(area, "area", allow_zero=False)

    actuarial_dec: Optional[Decimal] = None
    if actuarial_rate is not None:
        actuarial_dec = _validate_numeric(actuarial_rate, "actuarial_rate", allow_zero=True, max_val=100.0)

    # 2. Handle area units (hectares vs acres)
    unit_norm = unit.strip().lower()
    if unit_norm in {"ha", "hectare", "hectares"}:
        area_ha_dec = area_raw_dec
        conversion_note = f"{area_raw_dec} ha"
    elif unit_norm in {"acre", "acres"}:
        # Convert acres to hectares: 1 acre = 0.404686 ha
        area_ha_dec = (area_raw_dec * ACRES_TO_HECTARES).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        conversion_note = f"{area_raw_dec} acres ({area_ha_dec} ha converted at 1 acre = 0.404686 ha)"
    else:
        raise ValueError(
            f"Unsupported area unit '{unit}'. Supported units are hectares ('ha', 'hectare') or acres ('acre', 'acres')."
        )

    # 3. Resolve crop and applicable rate from records.json
    crop_name, resolved_season, category = resolve_crop_and_category(crop, season, crop_type)
    rate_table = load_rate_table_from_records()
    category_info = rate_table.get(category, rate_table["kharif_foodgrain_oilseed"])
    statutory_cap = category_info["rate_percent"]

    # 4. Pure arithmetic for Sum Insured
    sum_insured_dec = (sof_dec * area_ha_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 5. Determine applicable rate and estimate vs exact
    if actuarial_dec is not None and actuarial_dec > Decimal("0"):
        # Under PMFBY: Farmer pays min(statutory_cap, actuarial_rate)
        farmer_rate = min(statutory_cap, actuarial_dec)
        is_estimated_maximum = False
        rate_note = (
            f"Exact farmer rate = {farmer_rate:.2f}% (actuarial tender rate {actuarial_dec:.2f}% "
            f"vs statutory cap {statutory_cap:.2f}%)"
        )
    else:
        farmer_rate = statutory_cap
        is_estimated_maximum = True
        rate_note = (
            f"Estimated maximum farmer premium (capped at {farmer_rate:.1f}% statutory ceiling under PMFBY). "
            "Actual farmer premium may be lower if tender actuarial rate is lower."
        )

    # 6. Pure arithmetic for Farmer's Premium Share
    farmer_premium_dec = (sum_insured_dec * (farmer_rate / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    total_premium_dec: Optional[Decimal] = None
    subsidy_dec: Optional[Decimal] = None
    if actuarial_dec is not None and actuarial_dec > Decimal("0"):
        total_premium_dec = (sum_insured_dec * (actuarial_dec / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        subsidy_dec = total_premium_dec - farmer_premium_dec

    breakdown = (
        f"Sum Insured = Scale of Finance (₹{sof_dec:,.2f}/ha) × Area ({conversion_note}) = ₹{sum_insured_dec:,.2f}. "
        f"Farmer Premium Rate = {farmer_rate:.1f}% ({resolved_season.title()} {category.replace('_', ' ')}). "
        f"{'Estimated Maximum ' if is_estimated_maximum else ''}Farmer Premium = ₹{sum_insured_dec:,.2f} × {farmer_rate:.1f}% = ₹{farmer_premium_dec:,.2f}."
    )

    return {
        "status": "success",
        "crop": crop_name,
        "season": resolved_season,
        "category": category,
        "unit": unit_norm,
        "area_raw": float(area_raw_dec),
        "area_ha": float(area_ha_dec),
        "scale_of_finance_per_ha": float(sof_dec),
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

    Supports ISO formats, standard strings, and relative dates with injectable clock.
    Raises ValueError on missing, empty, or unparseable input.
    """
    if now is None:
        clock_now = datetime.now(tz=IST)
    elif now.tzinfo is None:
        clock_now = now.replace(tzinfo=IST)
    else:
        clock_now = now.astimezone(IST)

    if isinstance(loss_input, datetime):
        return loss_input if loss_input.tzinfo else loss_input.replace(tzinfo=IST)

    s = str(loss_input).strip()
    if not s:
        raise ValueError("Loss date/time is required. Please provide when the loss occurred.")

    low = s.lower()

    # Relative expressions
    if "yesterday" in low:
        loss_date = (clock_now - timedelta(days=1)).date()
        # Parse time if specified
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
            loss_time = time(21, 0)  # Default evening if time omitted
        return datetime.combine(loss_date, loss_time, tzinfo=IST)

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
            loss_time = clock_now.time()
        return datetime.combine(loss_date, loss_time, tzinfo=IST)

    # Relative hours ago
    hrs_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s+ago", low)
    if hrs_match:
        delta_hrs = float(hrs_match.group(1))
        return clock_now - timedelta(hours=delta_hrs)

    # Standard explicit formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            d = datetime.strptime(s, fmt)
            return d.replace(tzinfo=IST)
        except ValueError:
            pass

    raise ValueError(
        f"Invalid loss timestamp '{s}'. Please provide a valid date/time "
        "(e.g. 'YYYY-MM-DD HH:MM', 'yesterday at 9 pm', or '12 hours ago')."
    )


def pmfby_claim_deadline_check(
    loss_timestamp: Any,
    window_hours: int = 72,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calculates PMFBY 72-hour localized calamity / post-harvest intimation deadline.

    Args:
        loss_timestamp: Supplied loss date/time string or datetime.
        window_hours: Statutory intimation window (default 72 hours).
        now: Injectable current clock for deterministic evaluation and testing.

    Returns:
        Dict with exact loss and deadline timestamps, remaining hours, and official channels.
    """
    if now is None:
        clock_now = datetime.now(tz=IST)
    elif now.tzinfo is None:
        clock_now = now.replace(tzinfo=IST)
    else:
        clock_now = now.astimezone(IST)

    loss_dt = parse_loss_timestamp(loss_timestamp, now=clock_now)
    deadline_dt = loss_dt + timedelta(hours=window_hours)
    remaining_hours = round((deadline_dt - clock_now).total_seconds() / 3600.0, 1)

    return {
        "status": "success",
        "loss_timestamp": loss_dt.isoformat(),
        "deadline_timestamp": deadline_dt.isoformat(),
        "clock_timestamp": clock_now.isoformat(),
        "window_hours": window_hours,
        "remaining_hours": remaining_hours,
        "is_expired": remaining_hours <= 0,
        "reporting_channels": [
            "Crop Insurance App",
            "Krishi Rakshak Helpline: 14447",
            "Concerned Insurance Company Toll-Free",
            "Bank Branch / PACS where premium was debited",
            "Local Agriculture Officer / Revenue Authority",
        ],
        "og_version": "Revamped OG (Kharif 2020), Para 15.1.2 & 15.2.2 (72 hours rule)",
    }


def pmfby_knowledge_search(query: str, top_k: int = 3) -> Dict[str, Any]:
    """RAG semantic search tool over PMFBY official guidelines chunks."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")
    hits = query_semantic(query, top_k=top_k)
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
