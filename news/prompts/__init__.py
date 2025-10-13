"""
Prompts package for PDF report summarization
"""

from .prompt_router import get_prompt_for_series, SERIES_PROMPT_MAP
from .commodity_prompts import get_commodity_prompt
from .sector_prompts import get_sector_prompt

__all__ = [
    'get_prompt_for_series',
    'SERIES_PROMPT_MAP',
    'get_commodity_prompt',
    'get_sector_prompt'
]
