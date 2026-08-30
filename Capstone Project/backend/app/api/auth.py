from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.billing import Customer

# Setup the Bearer HTTP security dependency (non-blocking auto_error to custom handle 401s)
security_scheme = HTTPBearer(auto_error=False)

def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Customer:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Please provide Bearer <api_key> in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    api_key = credentials.credentials
    customer = db.query(Customer).filter(Customer.api_key == api_key).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key. Access Denied.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return customer
