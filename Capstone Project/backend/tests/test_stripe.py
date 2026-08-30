from unittest.mock import patch, MagicMock
from app.models import Subscription, Customer

def test_checkout_session_success(client):
    # Register customer
    customer = client.post("/v1/customers", json={"email": "checkout@example.com"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    # Mock stripe.checkout.Session.create API call
    with patch("stripe.checkout.Session.create") as mock_create:
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test_session_123"
        mock_create.return_value = mock_session
        
        response = client.post("/v1/billing/checkout", headers=headers)
        assert response.status_code == 200
        assert response.json()["checkout_url"] == "https://checkout.stripe.com/test_session_123"


def test_webhook_invalid_signature(client):
    # Webhook signature validation failure should return HTTP 400
    response = client.post(
        "/v1/webhooks/stripe",
        data="{}",
        headers={"Stripe-Signature": "t=123,v1=invalid_signature_checksum"}
    )
    assert response.status_code == 400


def test_webhook_checkout_completed(client, db_session):
    # Register customer
    customer = client.post("/v1/customers", json={"email": "stripe_up@example.com"}).json()
    
    # Mock checkout completed event payload
    fake_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": customer["id"],
                "customer": "cus_stripe_id_456",
                "subscription": "sub_stripe_id_789"
            }
        }
    }
    
    # Mock webhook signature validation to bypass signature check and return our event dict
    with patch("stripe.Webhook.construct_event", return_value=fake_event):
        # Mock stripe subscription retrieve call to get details
        with patch("stripe.Subscription.retrieve") as mock_sub_retrieve:
            mock_sub = MagicMock()
            mock_sub.current_period_start = 1770000000
            mock_sub.current_period_end = 1772592000
            mock_sub_retrieve.return_value = mock_sub
            
            response = client.post(
                "/v1/webhooks/stripe",
                json=fake_event,
                headers={"Stripe-Signature": "t=123,v1=valid_mock_signature"}
            )
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            
            # Check customer table maps stripe customer ID
            cust = db_session.query(Customer).filter_by(id=customer["id"]).first()
            assert cust.stripe_customer_id == "cus_stripe_id_456"
            
            # Check subscription table is upgraded to Pro
            sub = db_session.query(Subscription).filter_by(customer_id=customer["id"], status="active").first()
            assert sub.plan_id == "pro"
            assert sub.stripe_subscription_id == "sub_stripe_id_789"


def test_webhook_subscription_deleted(client, db_session):
    # Create customer
    customer = client.post("/v1/customers", json={"email": "stripe_down@example.com"}).json()
    
    # Upgrade subscription to Pro in the DB to simulate active Stripe plan
    sub = db_session.query(Subscription).filter_by(customer_id=customer["id"], status="active").first()
    sub.plan_id = "pro"
    sub.stripe_subscription_id = "sub_pro_active"
    db_session.commit()
    
    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_pro_active"
            }
        }
    }
    
    with patch("stripe.Webhook.construct_event", return_value=fake_event):
        response = client.post(
            "/v1/webhooks/stripe",
            json=fake_event,
            headers={"Stripe-Signature": "t=123,v1=valid_mock_signature"}
        )
        assert response.status_code == 200
        
        # Verify customer downgraded back to Free plan tier
        db_session.refresh(sub)
        assert sub.plan_id == "free"
        assert sub.stripe_subscription_id is None
