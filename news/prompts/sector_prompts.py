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
- Identify the PRIMARY sector(s) covered in this report (e.g., Container Freight, Steel, Chemicals, etc.)
- Extract key developments, trends, price movements, supply/demand dynamics for those sectors
- Map sector news to the most relevant commodity group(s) from the list above
  * Container Freight → "Container Freight"
  * Dry Bulk Shipping → "Dry Bulk Shipping"
  * Crude/Product Tankers → "Crude and Product Tankers"
  * Steel industry → "HRC", "Construction Steel"
  * Chemical plants → "Caustic Soda", "Plastics and Polymers", "Phosphorus Products", etc.
  * Fertilizer → "Urea", "NPK", "DAP"
- For groups NOT relevant to this report's focus, use empty string ""
- Keep summaries concise (2-3 sentences maximum per group)
- Focus on market fundamentals, not individual company stock performance
- Return ONLY the JSON object, no additional text


NOTE
- Plastics and Polymers: Refers to all plastic products (PVC, PE, PP, etc.). Any news about plastics should be included under Plastics and Polymers.
- Classify by shipping type:
  • Container Freight (SCFI, CCFI, WCI, TEU, FEU, Transpacific, Asia–Europe)
  • Dry Bulk Shipping (BDI, Capesize, Panamax, Supramax, Handysize, iron ore, coal, grain, tonne-miles)
  • Crude and Product Tankers (BDTI, BCTI, VLCC, Suezmax, Aframax, LR, MR, crude oil tankers, product tankers)
  Include mentions of freight rates, TCE, fleet growth, and demand-supply balance.

REPORT:
"""
