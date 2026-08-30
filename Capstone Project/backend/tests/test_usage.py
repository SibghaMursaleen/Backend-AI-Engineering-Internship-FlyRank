def test_log_usage_success(client):
    # Register customer
    customer_response = client.post("/v1/customers", json={"email": "usage@example.com"})
    api_key = customer_response.json()["api_key"]
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Log usage
    payload = {"endpoint": "generate_image", "units": 5}
    response = client.post("/v1/usage", json=payload, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "idempotency_key" in data
    assert data["units"] == 5


def test_log_usage_idempotency(client):
    # Register customer
    customer_response = client.post("/v1/customers", json={"email": "idemp@example.com"})
    api_key = customer_response.json()["api_key"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Idempotency-Key": "my-custom-uuid-key-123"
    }
    
    payload = {"endpoint": "transcribe_audio", "units": 10}
    
    # First request
    res1 = client.post("/v1/usage", json=payload, headers=headers)
    assert res1.status_code == 200
    assert "success" in res1.json()["status"]
    assert res1.json()["message"] == "Usage logged successfully."
    assert res1.json()["units"] == 10
    
    # Second request with the same Idempotency-Key
    res2 = client.post("/v1/usage", json=payload, headers=headers)
    assert res2.status_code == 200
    assert "success" in res2.json()["status"]
    assert res2.json()["message"] == "Duplicate request handled idempotently."
    assert res2.json()["idempotency_key"] == "my-custom-uuid-key-123"
    assert res2.json()["units"] == 10  # Returns previous result
