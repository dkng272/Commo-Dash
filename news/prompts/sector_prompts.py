"""
Sector Prompts - For sector-focused industry reports

Edit these templates to adjust summarization behavior for sector-specific reports.
"""

def get_sector_prompt(groups_str):
    """
    Prompt for sector-focused reports (e.g., Container Shipping, Steel, Banking)

    Args:
        groups_str: Comma-separated list of commodity groups (same as commodity prompt for consistency)

    Returns:
        str: Formatted prompt for sector analysis
    """
    return f"""You are a financial analyst analyzing a sector-focused industry report.

This report focuses on 1-2 specific sectors. Extract relevant commodity/industry news and return ONLY a valid JSON object in this exact format:

{{
  "Group Name": "news summary for this group (or empty string if no relevant news)",
  "Another Group": "news summary..."
}}

Commodity/Sector Groups to check: {groups_str}

Instructions:
- Identify the PRIMARY sector(s) covered in this report (e.g., Container Shipping, Steel, Chemicals, etc.)
- Extract key developments, trends, price movements, supply/demand dynamics for those sectors
- Map sector news to the most relevant commodity group(s) from the list above
  * Container Shipping → "Container Shipping"
  * Steel industry → "HRC", "Long Steel", "Steel"
  * Chemical plants → "Caustic Soda", "PVC", "Yellow P4", etc.
  * Fertilizer → "Urea", "NPK", "DAP"
- For groups NOT relevant to this report's focus, use empty string ""
- Keep summaries concise (2-3 sentences maximum per group)
- Focus on market fundamentals, not individual company stock performance
- Return ONLY the JSON object, no additional text


NOTE
- PVC: Refers to all plastic products (PE, PP, etc.). Any news about plastics should be included under PVC.
- Classify by shipping type — Container (SCFI, CCFI, WCI, TEU, FEU, Transpacific, Asia–Europe), Dry Bulk (BDI, Capesize, Panamax, Supramax, Handysize, iron ore, coal, grain, tonne-miles), and Liquids Shipping (aka Tankers) (BDTI, BCTI, VLCC, Suezmax, Aframax, LR, MR, crude, product tankers). Include mentions of freight rates, TCE, fleet growth, and demand-supply balance.

REPORT:
"""
