def test_create_customer_success(client):
    payload = {"email": "test@example.com", "name": "Test User"}
    response = client.post("/v1/customers", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert "api_key" in data
    assert data["api_key"].startswith("sk_live_")


def test_create_customer_duplicate_email(client):
    payload = {"email": "test@example.com", "name": "Test User"}
    client.post("/v1/customers", json=payload)
    
    # Try again with duplicate email
    response = client.post("/v1/customers", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Email is already registered"


def test_auth_success(client):
    # Register customer
    payload = {"email": "auth@example.com", "name": "Auth User"}
    customer_response = client.post("/v1/customers", json=payload)
    api_key = customer_response.json()["api_key"]
    
    # Query profile
    headers = {"Authorization": f"Bearer {api_key}"}
    response = client.get("/v1/customers/me", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "auth@example.com"
    assert len(data["subscriptions"]) == 1
    assert data["subscriptions"][0]["plan_id"] == "free"
    assert data["subscriptions"][0]["status"] == "active"


def test_auth_missing_header(client):
    response = client.get("/v1/customers/me")
    assert response.status_code == 401
    assert "Missing API Key" in response.json()["detail"]


def test_auth_invalid_key(client):
    headers = {"Authorization": "Bearer sk_live_invalidkey"}
    response = client.get("/v1/customers/me", headers=headers)
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]


def test_list_plans(client):
    response = client.get("/v1/plans")
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) == 2
    
    plan_ids = [plan["id"] for plan in plans]
    assert "free" in plan_ids
    assert "pro" in plan_ids
