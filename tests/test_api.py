import pytest
from fastapi.testclient import TestClient
from app import app
from db import Base, engine, SessionLocal

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # Base.metadata.drop_all(bind=engine) # Optional: keep data for manual check

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200

def test_list_monitors_unauthorized():
    # Attempt to list without token
    response = client.get("/api/v1/monitors")
    assert response.status_code == 401

def test_login_success():
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
