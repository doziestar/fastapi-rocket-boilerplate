from unittest import TestCase

import pytest
from fastapi import status

from app.services.user.models import RevokedToken


class TestUserRoutes(TestCase):
    @pytest.fixture(autouse=True)
    def _db_mocked_app_client(
        self, db_mocked_app_client, user_mocked_info, db_mocked
    ):
        self.app = db_mocked_app_client
        self.user_mocked_info = user_mocked_info

    def test_register(self):
        # Register an user
        response = self.app.post(
            url="user/register",
            json={
                "username": "anyemail@anyprovider.com",
                "password": "ultrasecretpassword",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Register the same user
        response = self.app.post(
            url="user/register",
            json={
                "username": "anyemail@anyprovider.com",
                "password": "ultrasecretpassword",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login(self):
        # Login ok
        response = self.app.post(
            url="user/login",
            data={
                "username": self.user_mocked_info["username"],
                "password": self.user_mocked_info["password"],
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Login ko
        response = self.app.post(
            url="user/login",
            data={
                "username": self.user_mocked_info["username"],
                "password": "incorrect password",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_refresh_token(self):
        # Login
        response = self.app.post(
            url="user/login",
            data={
                "username": self.user_mocked_info["username"],
                "password": self.user_mocked_info["password"],
            },
        )

        refresh_token_aux = response.json()["refresh_token"]

        # Clean revoked tokens
        for revoked_token in RevokedToken.get_all():
            revoked_token.delete()
        # Refresh Token ok
        response = self.app.post(
            url="user/refresh-token",
            json={
                "refresh_token": refresh_token_aux,
            },
        )

        assert "access_token" in response.json()
        assert response.status_code == status.HTTP_200_OK

        # Refresh token ko
        response = self.app.post(
            url="user/refresh-token",
            json={
                "refresh_token": "incorrect_refresh_token",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_and_protected(self):
        # Access to protected
        response = self.app.get(
            url="user/protected",
            headers={
                "Authorization": (
                    f"{self.user_mocked_info['token_type']} "
                    f"{self.user_mocked_info['access_token']}"
                )
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Login again
        response = self.app.post(
            url="user/login",
            data={
                "username": self.user_mocked_info["username"],
                "password": self.user_mocked_info["password"],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        refresh_token = response.json()["refresh_token"]

        # Logout and access to protected
        response = self.app.post(
            url="user/logout", json={"refresh_token": refresh_token}
        )

        assert response.status_code == status.HTTP_200_OK

        # Refresh revoked token
        response = self.app.post(
            url="user/refresh-token",
            json={
                "refresh_token": refresh_token,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Access to protected without valid token
        response = self.app.get(
            url="user/protected",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
