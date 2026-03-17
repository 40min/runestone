from runestone.agents.schemas import CoordinatorPlan


def test_coordinator_plan_validation():
    plan = CoordinatorPlan(
        pre_response=[],
        post_response=[],
        audit={"trace": "ok"},
    )

    assert plan.audit["trace"] == "ok"


def test_coordinator_plan_minimal():
    plan = CoordinatorPlan()
    assert plan.pre_response == []
    assert plan.post_response == []
