"""Stubbed adapter for a real Income Tax portal AIS OAuth pull.

NOT IMPLEMENTED — pulling a taxpayer's actual Annual Information Statement
requires the IT portal's e-filing OAuth flow (the same "registered ERI"
status referenced in app.filing.eri_stub), which this prototype does not
have. A real integration would need to:

1. Register KarAI as an authorized third-party application with the Income
   Tax e-filing portal (separate from, but related to, ERI registration).
2. Implement the OAuth 2.0 authorization-code flow: redirect the user to
   the IT portal login, receive an authorization code, exchange it for an
   access/refresh token pair scoped to AIS/TIS read access.
3. Call the portal's AIS API with the token to fetch the structured
   statement (JSON), map each line item to an ``AISRecordInput`` — the same
   shape ``generate_synthetic_ais`` and ``parse_ais_csv`` already produce, so
   ``app.ais_mock.diffing`` doesn't change at all once this exists.
4. Handle token refresh/expiry and store consent scope/duration per DPDP Act
   2023 requirements, mirroring the Account Aggregator consent handling in
   ``app.sources.account_aggregator_stub``.

Until this exists, AIS data comes from the synthetic generator or a
user-uploaded AIS CSV export (which the IT portal already lets taxpayers
download today).
"""

from app.ais_mock.synthetic_ais import AISRecordInput


def fetch_ais_via_oauth(access_token: str) -> list[AISRecordInput]:
    raise NotImplementedError(
        "IT-portal AIS OAuth integration requires e-filing portal application "
        "registration — not available in this prototype. See module docstring "
        "for the integration spec."
    )
