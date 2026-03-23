"""Synthetic company emission profiles for demo and eval.

Each company dict contains:
  scope_1/2/3_tco2e: tCO2e emissions per scope
  scope_2_method:     'market_based' or 'location_based'
  primary_sources:    top emission sources
  revenue_musd:       revenue in $M (for emission intensity)
  sector:             industry sector
  sector_avg_intensity: sector average tCO2e/$M revenue
  sbti_target:        True if company has SBTi-approved target
  employees:          headcount (for CSRD threshold check)
"""
from __future__ import annotations

_COMPANIES: dict[str, dict] = {
    "COMPANY-001": {
        "company_id": "COMPANY-001",
        "name": "Acme Tech Ltd",
        "sector": "Technology",
        "scope_1_tco2e": 1250.0,
        "scope_2_tco2e": 3847.0,
        "scope_3_tco2e": 28400.0,
        "scope_2_method": "market_based",
        "primary_sources": ["Scope 3 Cat 1 purchased goods", "Scope 2 grid electricity"],
        "revenue_musd": 150.0,
        "sector_avg_intensity": 120.0,  # tCO2e / $M revenue
        "sbti_target": False,
        "employees": 420,
    },
    "COMPANY-002": {
        "company_id": "COMPANY-002",
        "name": "Meridian Manufacturing",
        "sector": "Manufacturing",
        "scope_1_tco2e": 45000.0,
        "scope_2_tco2e": 12000.0,
        "scope_3_tco2e": 85000.0,
        "scope_2_method": "location_based",
        "primary_sources": ["Scope 1 industrial combustion", "Scope 3 Cat 1 raw materials"],
        "revenue_musd": 500.0,
        "sector_avg_intensity": 350.0,
        "sbti_target": True,
        "employees": 2100,
    },
    "COMPANY-003": {
        "company_id": "COMPANY-003",
        "name": "Verdant Retail Group",
        "sector": "Retail",
        "scope_1_tco2e": 2100.0,
        "scope_2_tco2e": 8500.0,
        "scope_3_tco2e": 125000.0,
        "scope_2_method": "market_based",
        "primary_sources": ["Scope 3 Cat 1 purchased goods", "Scope 3 Cat 11 product use"],
        "revenue_musd": 800.0,
        "sector_avg_intensity": 200.0,
        "sbti_target": False,
        "employees": 5800,
    },
}


def get_company_data(company_id: str) -> dict:
    """Return synthetic emission profile for a company_id.

    Raises KeyError with clear message if company_id not found.
    """
    if company_id not in _COMPANIES:
        raise KeyError(
            f"Company '{company_id}' not found. "
            f"Available: {list(_COMPANIES.keys())}"
        )
    return _COMPANIES[company_id]
