import pytest
from fastapi import status
from fastapi.testclient import TestClient


class TestHealthCheckAPI:
    """Test cases for the /health endpoint"""

    def test_get_health_success(self, client: TestClient):
        """Test successful health check endpoint"""
        response = client.get("/health")
        
        # Assert status code
        assert response.status_code == status.HTTP_200_OK
        
        # Assert response body structure
        data = response.json()
        assert "status" in data
        assert data["status"] == "oke"
        assert isinstance(data["status"], str)

    def test_get_health_response_model(self, client: TestClient):
        """Test that health check response matches the expected model"""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify response matches HealthCheck model
        assert data == {"status": "oke"}

    def test_get_health_content_type(self, client: TestClient):
        """Test that health check returns JSON content type"""
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers.get("content-type", "")

    def test_get_health_multiple_requests(self, client: TestClient):
        """Test that health check endpoint is idempotent"""
        # Make multiple requests
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["status"] == "oke"

    def test_get_health_no_authentication_required(self, client: TestClient):
        """Test that health check endpoint doesn't require authentication"""
        # Health endpoint should be publicly accessible
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK

