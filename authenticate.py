"""Run this once by hand to complete the Google OAuth consent flow.

Opens a browser for login/consent, then caches the resulting token to
token.json so the MCP server can use it non-interactively afterwards.
"""

from gdoc_mcp import auth


def main() -> None:
    auth.run_interactive_auth()
    print(f"Authenticated. Token cached at {auth.TOKEN_PATH}")


if __name__ == "__main__":
    main()
