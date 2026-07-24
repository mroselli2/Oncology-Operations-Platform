"""Hard per-run USD budget guard. A ceiling, not a spending target: no call
may begin if it could push cumulative spend past the configured limit, and
nothing here ever waits on the OpenRouter account balance to enforce it."""

from __future__ import annotations

from dataclasses import dataclass

# Conservative worst-case cost estimate for the pre-call affordability check,
# scaled to the token cap. Actual cost is reconciled from reported usage
# after each call; the hard budget (LLM_RUN_BUDGET_USD) is the real ceiling.
ASSUMED_MAX_COST_PER_CALL_USD = 0.02


@dataclass
class BudgetGuard:
    budget_usd: float
    spent_usd: float = 0.0
    calls_made: int = 0
    calls_capped_at: int = 17

    def can_afford_another_call(self) -> tuple[bool, str | None]:
        if self.calls_made >= self.calls_capped_at:
            return False, "call_count_cap_reached"
        if self.spent_usd + ASSUMED_MAX_COST_PER_CALL_USD > self.budget_usd:
            return False, "budget_exceeded"
        return True, None

    def record_actual_cost(self, cost_usd: float) -> None:
        self.spent_usd += max(0.0, cost_usd)
        self.calls_made += 1
