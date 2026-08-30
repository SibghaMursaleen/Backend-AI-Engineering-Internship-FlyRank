from datetime import datetime, timezone
from app.models import Subscription, Plan, UsageEvent
from app.services.billing import calculate_usage_cost

def test_cost_calculations(client, db_session):
    # Create customer (defaults to Free subscription)
    customer = client.post("/v1/customers", json={"email": "calc@example.com"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    free_plan = db_session.query(Plan).filter(Plan.id == "free").first()
    sub = db_session.query(Subscription).filter_by(customer_id=customer["id"], status="active").first()
    
    # 1. Under quota: log 600 units (free limit 1000) -> cost is 0 cents.
    # Safe to use client.post here since it is under quota.
    client.post("/v1/usage", json={"endpoint": "api_call", "units": 600}, headers=headers)
    
    total_units, cost = calculate_usage_cost(
        db_session, customer["id"], sub.current_period_start, sub.current_period_end, free_plan
    )
    assert total_units == 600
    assert cost == 0
    
    # 2. Over quota: log 500 more units (1100 total) -> cost is: 0 + (100 overage * 5 cents) = 500 cents ($5.00)
    # We must insert directly to database to bypass the API 429 quota rate limiter block.
    event = UsageEvent(
        customer_id=customer["id"],
        endpoint="api_call",
        units=500,
        idempotency_key="idemp_calc_test"
    )
    db_session.add(event)
    db_session.commit()
    
    total_units, cost = calculate_usage_cost(
        db_session, customer["id"], sub.current_period_start, sub.current_period_end, free_plan
    )
    assert total_units == 1100
    assert cost == 500


def test_cost_calculations_pro_plan(client, db_session):
    # Create customer
    customer = client.post("/v1/customers", json={"email": "calc_pro@example.com"}).json()
    
    # Manually upgrade to Pro plan subscription in db
    sub = db_session.query(Subscription).filter_by(customer_id=customer["id"], status="active").first()
    sub.plan_id = "pro"
    db_session.commit()
    
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    pro_plan = db_session.query(Plan).filter(Plan.id == "pro").first()
    
    # Pro plan limit is 50000, base fee is 2900 cents ($29.00), overage is 1 cent per unit
    # 1. Under quota: log 5000 units -> cost should be 2900 cents ($29.00)
    client.post("/v1/usage", json={"endpoint": "api_call", "units": 5000}, headers=headers)
    
    total_units, cost = calculate_usage_cost(
        db_session, customer["id"], sub.current_period_start, sub.current_period_end, pro_plan
    )
    assert total_units == 5000
    assert cost == 2900
    
    # 2. Over quota: log 45100 more units (50100 total) -> cost is: 2900 + (100 overage * 1 cent) = 3000 cents ($30.00)
    # We must insert directly to database to bypass the API 429 quota rate limiter block.
    event = UsageEvent(
        customer_id=customer["id"],
        endpoint="api_call",
        units=45100,
        idempotency_key="idemp_calc_pro_test"
    )
    db_session.add(event)
    db_session.commit()
    
    total_units, cost = calculate_usage_cost(
        db_session, customer["id"], sub.current_period_start, sub.current_period_end, pro_plan
    )
    assert total_units == 50100
    assert cost == 3000


def test_summary_endpoint(client):
    customer = client.post("/v1/customers", json={"email": "summary@example.com"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    # Log 300 units
    client.post("/v1/usage", json={"endpoint": "api_call", "units": 300}, headers=headers)
    
    # Call summary endpoint
    res = client.get("/v1/usage/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["plan_id"] == "free"
    assert data["units_used"] == 300
    assert data["percentage_used"] == 30.0
    assert data["estimated_cost_cents"] == 0


def test_history_endpoint(client):
    customer = client.post("/v1/customers", json={"email": "history@example.com"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    # Log 150 and 250 units
    client.post("/v1/usage", json={"endpoint": "api_call", "units": 150}, headers=headers)
    client.post("/v1/usage", json={"endpoint": "api_call", "units": 250}, headers=headers)
    
    # Hit history API
    res = client.get("/v1/usage/history", headers=headers)
    assert res.status_code == 200
    history = res.json()
    
    assert len(history) > 0
    current_date_str = datetime.now(timezone.utc).replace(tzinfo=None).date().isoformat()
    
    match_day = next((day for day in history if day["date"] == current_date_str), None)
    assert match_day is not None
    assert match_day["units"] == 400
