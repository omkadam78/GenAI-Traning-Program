"""PMFBY agent tools for FasalBima Sathi (Day 9).

Tool:
- pmfby_premium: Calculates sum insured (scale of finance x area) and
  the farmer's premium share using the season and crop-type rates stored
  in records.json. Pure arithmetic.
- pmfby_knowledge_search: RAG semantic search over PMFBY official guidelines.
- pmfby_claim_deadline_check: Computes the 72-hour reporting intimation deadline.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from app.records import load_records
from app.vectorstore import query_semantic

ROOT = Path(__file__).resolve().parent.parent
RECORDS_PATH = ROOT / "data" / "records.json"

# Default statutory premium caps under Revamped PMFBY guidelines
DEFAULT_RATE_MAP = {
    "kharif_foodgrain_oilseed": 2.0,       # Cereals, millets, pulses, oilseeds (e.g. soybean)
    "rabi_foodgrain_oilseed": 1.5,         # Wheat, gram, mustard, rabi pulses
    "commercial_horticultural": 5.0,       # Annual commercial / horticultural (e.g. cotton, sugarcane)
}

# Common crop category mappings for farmers
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
            rate = float(match.group(1)) if match else 2.0
            rate_table["kharif_foodgrain_oilseed"] = {
                "rate_percent": rate,
                "record_id": r.get("id"),
                "rule_topic": r.get("rule_topic"),
                "og_version": r.get("og_version"),
                "source_url": r.get("source_url"),
            }
        elif "rabi" in text and ("food" in text or "oilseed" in text):
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", deadline_or_rate)
            rate = float(match.group(1)) if match else 1.5
            rate_table["rabi_foodgrain_oilseed"] = {
                "rate_percent": rate,
                "record_id": r.get("id"),
                "rule_topic": r.get("rule_topic"),
                "og_version": r.get("og_version"),
                "source_url": r.get("source_url"),
            }
        elif "commercial" in text or "horticultural" in text:
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", deadline_or_rate)
            rate = float(match.group(1)) if match else 5.0
            rate_table["commercial_horticultural"] = {
                "rate_percent": rate,
                "record_id": r.get("id"),
                "rule_topic": r.get("rule_topic"),
                "og_version": r.get("og_version"),
                "source_url": r.get("source_url"),
            }

    # Ensure all three exist
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


def resolve_crop_and_season(
    crop: Optional[str] = None,
    season: Optional[str] = None,
    crop_type: Optional[str] = None,
) -> tuple[str, str, str]:
    """Resolve normalized crop name, season ('kharif'/'rabi'/'annual'), and rate category."""
    crop_clean = (crop or "").strip().lower()
    season_clean = (season or "").strip().lower()

    if crop_clean in CROP_CATEGORY_MAP:
        default_season, category = CROP_CATEGORY_MAP[crop_clean]
        resolved_season = season_clean if season_clean in {"kharif", "rabi", "summer", "annual"} else default_season
        # If farmer explicitly says rabi for a grain/pulse, adjust category
        if resolved_season == "rabi" and category == "kharif_foodgrain_oilseed":
            category = "rabi_foodgrain_oilseed"
        return crop_clean, resolved_season, category

    # Fallback heuristic based on season or crop_type
    if crop_type:
        type_clean = crop_type.strip().lower()
        if "commercial" in type_clean or "horticultur" in type_clean:
            return crop_clean or "commercial crop", season_clean or "annual", "commercial_horticultural"
        if "rabi" in type_clean:
            return crop_clean or "rabi crop", "rabi", "rabi_foodgrain_oilseed"
        return crop_clean or "kharif crop", "kharif", "kharif_foodgrain_oilseed"

    if season_clean == "rabi":
        return crop_clean or "rabi crop", "rabi", "rabi_foodgrain_oilseed"
    if "commercial" in season_clean or "horticultur" in season_clean:
        return crop_clean or "commercial crop", "annual", "commercial_horticultural"

    # Default is Kharif foodgrain/oilseed (e.g. soybean)
    return crop_clean or "foodgrain/oilseed", "kharif", "kharif_foodgrain_oilseed"


def pmfby_premium(
    scale_of_finance: float,
    area: float,
    crop: Optional[str] = None,
    season: Optional[str] = None,
    crop_type: Optional[str] = None,
    actuarial_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Calculates sum insured (scale of finance x area) and the farmer's premium share

    using the season and crop-type rates stored in records.json. Pure arithmetic.

    Args:
        scale_of_finance: Scale of finance in INR per hectare (e.g. 49000 for Soybean).
        area: Insured crop area in hectares (e.g. 1.2).
        crop: Crop name (e.g. 'soybean', 'wheat', 'cotton').
        season: Season ('kharif', 'rabi', 'annual').
        crop_type: Specific category ('kharif_foodgrain_oilseed', 'rabi_foodgrain_oilseed', 'commercial_horticultural').
        actuarial_rate: Total actuarial premium rate percent (optional, e.g. 12.0%).

    Returns:
        Dict with pure arithmetic calculation results, rate breakdown, and rule reference.
    """
    if scale_of_finance <= 0:
        raise ValueError("scale_of_finance must be greater than 0")
    if area <= 0:
        raise ValueError("area must be greater than 0")

    # 1. Pure arithmetic for Sum Insured
    sum_insured = round(float(scale_of_finance) * float(area), 2)

    # 2. Resolve category and rate from records.json
    crop_name, resolved_season, category = resolve_crop_and_season(crop, season, crop_type)
    rate_table = load_rate_table_from_records()
    category_info = rate_table.get(category, rate_table["kharif_foodgrain_oilseed"])

    statutory_cap_percent = category_info["rate_percent"]

    # Under PMFBY: Farmer pays min(statutory_cap, actuarial_rate)
    if actuarial_rate is not None and actuarial_rate > 0:
        farmer_rate_percent = min(statutory_cap_percent, actuarial_rate)
    else:
        farmer_rate_percent = statutory_cap_percent

    # 3. Pure arithmetic for Farmer's Premium Share
    farmer_premium = round(sum_insured * (farmer_rate_percent / 100.0), 2)

    # Subsidy calculation if actuarial rate is known
    total_premium: Optional[float] = None
    govt_subsidy: Optional[float] = None
    if actuarial_rate is not None and actuarial_rate > 0:
        total_premium = round(sum_insured * (actuarial_rate / 100.0), 2)
        govt_subsidy = round(total_premium - farmer_premium, 2)

    breakdown = (
        f"Sum Insured = Scale of Finance (₹{scale_of_finance:,.2f}/ha) × Area ({area:.2f} ha) = ₹{sum_insured:,.2f}. "
        f"Farmer Premium Rate = {farmer_rate_percent:.1f}% ({resolved_season.title()} {category.replace('_', ' ')}). "
        f"Farmer Premium Share = ₹{sum_insured:,.2f} × {farmer_rate_percent:.1f}% = ₹{farmer_premium:,.2f}."
    )

    return {
        "status": "success",
        "crop": crop_name,
        "season": resolved_season,
        "category": category,
        "scale_of_finance_per_ha": float(scale_of_finance),
        "area_ha": float(area),
        "sum_insured": sum_insured,
        "farmer_rate_percent": farmer_rate_percent,
        "farmer_premium": farmer_premium,
        "actuarial_rate_percent": actuarial_rate,
        "total_premium": total_premium,
        "govt_subsidy": govt_subsidy,
        "breakdown": breakdown,
        "rule_reference": {
            "record_id": category_info.get("record_id"),
            "rule_topic": category_info.get("rule_topic"),
            "og_version": category_info.get("og_version"),
            "source_url": category_info.get("source_url"),
        },
    }


def pmfby_knowledge_search(query: str, top_k: int = 3) -> Dict[str, Any]:
    """RAG semantic search tool over PMFBY official guidelines chunks."""
    hits = query_semantic(query, top_k=top_k)
    return {
        "query": query,
        "count": len(hits),
        "hits": hits,
    }


def pmfby_claim_deadline_check(
    loss_timestamp: str | datetime,
    window_hours: int = 72,
) -> Dict[str, Any]:
    """Calculates PMFBY 72-hour localized calamity / post-harvest intimation deadline."""
    if isinstance(loss_timestamp, str):
        # Support basic ISO or YYYY-MM-DD HH:MM formats
        ts_clean = loss_timestamp.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(ts_clean, fmt)
                break
            except ValueError:
                pass
        else:
            # Fallback to current time if parsing fails
            dt = datetime.now()
    else:
        dt = loss_timestamp

    deadline = dt + timedelta(hours=window_hours)
    now = datetime.now()
    remaining_hours = round((deadline - now).total_seconds() / 3600.0, 1)

    return {
        "loss_timestamp": dt.isoformat(),
        "window_hours": window_hours,
        "deadline_timestamp": deadline.isoformat(),
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


AVAILABLE_TOOLS = {
    "pmfby_premium": pmfby_premium,
    "pmfby_knowledge_search": pmfby_knowledge_search,
    "pmfby_claim_deadline_check": pmfby_claim_deadline_check,
}

