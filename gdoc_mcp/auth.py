"""OAuth 2.0 credential management for the Google Docs/Drive APIs.

Token acquisition (the interactive browser consent flow) only happens via
`authenticate.py`, run once by hand. The MCP server itself only ever loads
and silently refreshes an existing token — it never blocks a tool call on
interactive login.
"""

import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = Path(os.environ.get("GDOC_MCP_CREDENTIALS_PATH", PROJECT_ROOT / "credentials.json"))
TOKEN_PATH = Path(os.environ.get("GDOC_MCP_TOKEN_PATH", PROJECT_ROOT / "token.json"))


class AuthNotConfiguredError(RuntimeError):
    pass


def get_credentials() -> Credentials:
    """Load a cached, valid token. Never triggers an interactive login.

    Raises AuthNotConfiguredError if no token exists yet or it can't be
    refreshed — the caller (an MCP tool) should surface this as a clear
    instruction to run `python authenticate.py`.
    """
    if not TOKEN_PATH.exists():
        raise AuthNotConfiguredError(
            f"No cached token at {TOKEN_PATH}. Run `python authenticate.py` "
            "once to complete the Google OAuth consent flow."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise AuthNotConfiguredError(
                "Cached Google token could not be refreshed (it may have been "
                "revoked). Run `python authenticate.py` again to re-authenticate."
            ) from exc
        TOKEN_PATH.write_text(creds.to_json())
        return creds

    raise AuthNotConfiguredError(
        "Cached Google token is invalid and has no refresh token. Run "
        "`python authenticate.py` again to re-authenticate."
    )


def run_interactive_auth() -> None:
    """Runs the one-time browser consent flow and caches the resulting token."""
    if not CREDENTIALS_PATH.exists():
        raise AuthNotConfiguredError(
            f"Missing OAuth client secrets at {CREDENTIALS_PATH}. Download "
            "the OAuth client JSON from Google Cloud Console and save it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
