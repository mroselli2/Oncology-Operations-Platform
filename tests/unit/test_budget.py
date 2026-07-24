from oncology_pipeline.llm.budget import BudgetGuard


def test_can_afford_under_budget():
    guard = BudgetGuard(budget_usd=0.10)
    can_afford, reason = guard.can_afford_another_call()
    assert can_afford is True
    assert reason is None


def test_zero_budget_blocks_immediately():
    guard = BudgetGuard(budget_usd=0.0)
    can_afford, reason = guard.can_afford_another_call()
    assert can_afford is False
    assert reason == "budget_exceeded"


def test_call_count_cap():
    guard = BudgetGuard(budget_usd=100.0, calls_capped_at=2)
    guard.record_actual_cost(0.001)
    guard.record_actual_cost(0.001)
    can_afford, reason = guard.can_afford_another_call()
    assert can_afford is False
    assert reason == "call_count_cap_reached"


def test_record_actual_cost_accumulates():
    guard = BudgetGuard(budget_usd=1.0)
    guard.record_actual_cost(0.02)
    guard.record_actual_cost(0.03)
    assert guard.spent_usd == 0.05
    assert guard.calls_made == 2
