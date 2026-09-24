import secrets
import httpx
from urllib.parse import urlencode

from config import (
    SERVICENOW_INSTANCE,
    SERVICENOW_CLIENT_ID,
    SERVICENOW_CLIENT_SECRET,
    SERVICENOW_REDIRECT_URI,
)


def generate_state():
    return secrets.token_urlsafe(32)


def get_authorization_url(state: str):

    params = {
        "response_type": "code",
        "client_id": SERVICENOW_CLIENT_ID,
        "redirect_uri": SERVICENOW_REDIRECT_URI,
        "state": state,
        "scope": "table_read",
    }

    return f"{SERVICENOW_INSTANCE}/oauth_auth.do?{urlencode(params)}"


def exchange_code_for_token(code: str):

    token_url = f"{SERVICENOW_INSTANCE}/oauth_token.do"

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SERVICENOW_REDIRECT_URI,
    }

    with httpx.Client() as client:

        response = client.post(
            token_url,
            data=data,
            auth=(
                SERVICENOW_CLIENT_ID,
                SERVICENOW_CLIENT_SECRET
            ),
            headers={
                "Accept": "application/json"
            },
            timeout=30.0,
        )

    if response.status_code != 200:
        raise Exception(
            f"Token exchange failed: "
            f"{response.status_code} - {response.text}"
        )

    return response.json()

def refresh_access_token(refresh_token: str):

    token_url = f"{SERVICENOW_INSTANCE}/oauth_token.do"

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    with httpx.Client() as client:

        response = client.post(
            token_url,
            data=data,
            auth=(
                SERVICENOW_CLIENT_ID,
                SERVICENOW_CLIENT_SECRET
            ),
            headers={
                "Accept": "application/json"
            },
            timeout=30.0,
        )

    if response.status_code != 200:
        raise Exception(
            f"Refresh token request failed: "
            f"{response.status_code} - {response.text}"
        )

    return response.json()