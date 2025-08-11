import pytest
import asyncio
from httpx import AsyncClient
from fastapi import status
from app.main import app
from app.core.database import get_async_session
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
class TestAuth:
    """Test authentication endpoints"""
    
    async def test_register_user(self, client: AsyncClient):
        """Test user registration"""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == status.HTTP_201_CREATED
        
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert "hashed_password" not in data
    
    async def test_login_success(self, client: AsyncClient):
        """Test successful login"""
        # First register a user
        user_data = {
            "email": "login@example.com",
            "username": "loginuser",
            "full_name": "Login User",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        await client.post("/api/v1/auth/register", json=user_data)
        
        # Then login
        login_data = {
            "email": "login@example.com",
            "password": "StrongPass123!"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_get_current_user(self, client: AsyncClient, auth_headers: dict):
        """Test getting current user info"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "user" in data
        assert "roles" in data
        assert "permissions" in data
    
    async def test_refresh_token(self, client: AsyncClient):
        """Test token refresh"""
        # Login to get tokens
        user_data = {
            "email": "refresh@example.com",
            "username": "refreshuser",
            "full_name": "Refresh User",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        await client.post("/api/v1/auth/register", json=user_data)
        
        login_data = {
            "email": "refresh@example.com",
            "password": "StrongPass123!"
        }
        
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Refresh token
        refresh_data = {
            "refresh_token": tokens["refresh_token"]
        }
        
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "access_token" in data
    
    async def test_logout(self, client: AsyncClient, auth_headers: dict):
        """Test logout"""
        # Get refresh token first
        login_data = {
            "email": "admin@ai-retail.com",
            "password": "admin123"
        }
        
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()
        
        logout_data = {
            "refresh_token": tokens["refresh_token"]
        }
        
        response = await client.post("/api/v1/auth/logout", json=logout_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
    
    async def test_change_password(self, client: AsyncClient, auth_headers: dict):
        """Test password change"""
        change_data = {
            "current_password": "admin123",
            "new_password": "NewStrongPass123!",
            "confirm_password": "NewStrongPass123!"
        }
        
        response = await client.post("/api/v1/auth/change-password", json=change_data, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK