"""
FoodParserAgent State — LangGraph state for natural language food parsing.
"""

from dataclasses import dataclass, field


@dataclass
class FoodParserState:
    # Input
    text: str = ""
    meal_type: str | None = None

    # Parse (LLM)
    raw_llm_output: str = ""
    parsed_items: list[dict] = field(default_factory=list)

    # Search (pgvector foods DB)
    matched_foods: list[dict] = field(default_factory=list)

    # Calculate
    calculated_items: list[dict] = field(default_factory=list)
    total_kcal: float = 0.0

    # Output
    final_items: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parse_time_ms: int | None = None

    # Error
    error: str | None = None
