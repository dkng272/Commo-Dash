"""
Prompt Router - Maps report series to appropriate prompt types

This configuration file determines which prompt to use for each report series.
Add new series here as you encounter new report types.
"""

# Series → Prompt Type Mapping
SERIES_PROMPT_MAP = {
    # Multi-sector commodity reports (use commodity prompt)
    'ChemAgri': 'commodity',
    'GlobalCommodities': 'commodity',
    'WeeklyMarkets': 'commodity',
    'DailyMarkets': 'commodity',
    'Commodities': 'commodity',
    'ChinaMetals' : 'commodity',

    # Sector-specific reports (use sector prompt)
    'ContainerShipping': 'sector',
    'Steel': 'sector',
    'Oil': 'sector',
    'Gas': 'sector',
    'Agriculture': 'sector',
    'Banking': 'sector',
    'Chemicals': 'sector',
    'Metals': 'sector',
}

# Configuration for page extraction
SERIES_PAGE_CONFIG = {
    # Multi-sector reports: extract fewer pages
    'commodity': 5,

    # Sector-specific reports: extract more pages
    'sector': 5,
}


def get_prompt_for_series(series_name):
    """
    Get the prompt type for a given report series

    Args:
        series_name: Series name from filename (e.g., 'ChemAgri', 'ContainerShipping')

    Returns:
        str: Prompt type ('commodity' or 'sector')
    """
    # Default to commodity if series not found
    return SERIES_PROMPT_MAP.get(series_name, 'commodity')


def get_max_pages_for_prompt(prompt_type):
    """
    Get the number of pages to extract for a prompt type

    Args:
        prompt_type: Type of prompt ('commodity' or 'sector')

    Returns:
        int: Number of pages to extract
    """
    return SERIES_PAGE_CONFIG.get(prompt_type, 4)


def add_series(series_name, prompt_type):
    """
    Add a new series to the mapping (for dynamic additions)

    Args:
        series_name: Name of the report series
        prompt_type: Type of prompt to use ('commodity' or 'sector')
    """
    SERIES_PROMPT_MAP[series_name] = prompt_type


def list_all_series():
    """
    List all registered report series

    Returns:
        dict: Series grouped by prompt type
    """
    commodity_series = [s for s, p in SERIES_PROMPT_MAP.items() if p == 'commodity']
    sector_series = [s for s, p in SERIES_PROMPT_MAP.items() if p == 'sector']

    return {
        'commodity': commodity_series,
        'sector': sector_series
    }
