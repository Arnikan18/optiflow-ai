from fastapi import FastAPI

from app.database import models
from app.database.base import Base
from app.database.seed import seed_customers
from app.database.session import SessionLocal, engine

Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    seed_customers(db)
finally:
    db.close()

app = FastAPI(
    title="OptiFlow CRM Service",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "service": "CRM Service",
        "message": "OptiFlow CRM Service is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "crm-service"
    }