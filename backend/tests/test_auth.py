"""Tests for the authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@test.com",
            "password": "securepass123",
            "full_name": "New User",
            "role": "student",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "duplicate@test.com",
        "password": "securepass123",
        "full_name": "User One",
        "role": "student",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@test.com",
            "password": "securepass123",
            "full_name": "Login User",
            "role": "teacher",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.com", "password": "securepass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpw@test.com",
            "password": "correct123",
            "full_name": "WP User",
            "role": "student",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@test.com", "password": "wrong123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, teacher_token: str):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "teacher@test.com"
    assert data["role"] == "teacher"
