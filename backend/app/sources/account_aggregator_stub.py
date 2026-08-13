"""Stubbed adapter for a real RBI Account Aggregator (AA) bank/UPI feed.

NOT IMPLEMENTED — this requires a business relationship this prototype does
not have: registration/partnership with an AA (e.g. Finvu, OneMoney, Perfios)
to pull consent-based transaction data on the user's behalf. Implementing the
real integration means:

1. Register KarAI as a Financial Information User (FIU) with an AA sandbox,
   then production, per the Sahamati / ReBIT AA technical specification.
2. Implement the consent flow: redirect the user to their chosen AA, they
   approve a consent artifact (scope: transaction data, purpose, duration),
   AA returns a consent handle.
3. Poll/receive the FI (Financial Information) notification, then call the
   AA's `/FI/fetch` endpoint with the consent handle to retrieve encrypted
   transaction data (encrypted with the FIU's public key, per the AA spec).
4. Decrypt, map each FI entry to a ``RawTransaction`` (this is the only new
   code an integration needs to write — everything downstream of
   ``TransactionSource.fetch()`` already works against that shape).
5. Store the consent artifact ID, scope, and expiry; support revocation
   (DPDP Act 2023 requires the user be able to revoke consent at any time —
   see ``app.routers.users.delete_my_data``).

Until this exists, users connect data via CSV upload, manual entry, or the
synthetic demo feed (``app.sources.synthetic_feed.SyntheticFeedGenerator``).
"""

from app.sources.base import RawTransaction, TransactionSource


class AccountAggregatorSource(TransactionSource):
    def __init__(self, consent_handle: str):
        self.consent_handle = consent_handle

    def fetch(self) -> list[RawTransaction]:
        raise NotImplementedError(
            "Account Aggregator integration requires an AA partnership "
            "(Finvu/OneMoney/Perfios) and FIU registration — not available "
            "in this prototype. See module docstring for the integration spec."
        )
