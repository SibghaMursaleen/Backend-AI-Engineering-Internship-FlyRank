import datetime

def test_quota_enforcement_success(client, mock_redis):
    # Register customer
    customer = client.post("/v1/customers", json={"email": "quota_ok@example.com", "name": "Quota OK User"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    # Log 500 units (Free Plan quota is 1000)
    res = client.post("/v1/usage", json={"endpoint": "api_call", "units": 500}, headers=headers)
    assert res.status_code == 200
    assert res.json()["units"] == 500
    
    # Verify Redis counter increments
    now = datetime.datetime.utcnow()
    redis_key = f"usage:{customer['id']}:{now.year}-{now.month:02d}"
    assert mock_redis.get(redis_key) == "500"


def test_quota_enforcement_blocked(client):
    # Register customer
    customer = client.post("/v1/customers", json={"email": "quota_fail@example.com", "name": "Quota Fail User"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    # Log 990 units (succeeds)
    res1 = client.post("/v1/usage", json={"endpoint": "api_call", "units": 990}, headers=headers)
    assert res1.status_code == 200
    
    # Log 20 units (fails: 990 + 20 = 1010 > 1000 limit)
    res2 = client.post("/v1/usage", json={"endpoint": "api_call", "units": 20}, headers=headers)
    assert res2.status_code == 429
    assert "quota exceeded" in res2.json()["detail"].lower()


def test_quota_cache_rebuild(client, mock_redis):
    # Register customer
    customer = client.post("/v1/customers", json={"email": "quota_rebuild@example.com"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    # Log 400 units
    res1 = client.post("/v1/usage", json={"endpoint": "api_call", "units": 400}, headers=headers)
    assert res1.status_code == 200
    
    now = datetime.datetime.utcnow()
    redis_key = f"usage:{customer['id']}:{now.year}-{now.month:02d}"
    assert mock_redis.get(redis_key) == "400"
    
    # Simulate a cache miss / Redis restart
    mock_redis.flushall()
    assert mock_redis.get(redis_key) is None
    
    # Call endpoint again: should rebuild from Postgres (400) + add new units (200) = 600
    res2 = client.post("/v1/usage", json={"endpoint": "api_call", "units": 200}, headers=headers)
    assert res2.status_code == 200
    assert mock_redis.get(redis_key) == "600"
