"""The TransactionSource abstraction.

Every way transaction data enters KarAI — CSV upload, manual entry, a
synthetic demo feed, or (eventually) a live bank/UPI feed via the RBI Account
Aggregator framework — implements this same interface and returns the same
``RawTransaction`` shape. This is what lets a real AA integration slot in
later as a new adapter, not a rewrite of the ingestion pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re


PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def normalize_pan(value: str) -> str:
    """Normalize a PAN and reject values that do not match its basic format."""
    pan = value.strip().upper()
    if not PAN_PATTERN.fullmatch(pan):
        raise ValueError("PAN must be 10 characters in the format AAAAA9999A.")
    return pan


@dataclass(frozen=True)
class RawTransaction:
    transaction_date: date
    amount: Decimal
    party_name: str
    description: str = ""
    declared_category: str | None = None
    party_gstin: str | None = None
    party_pan: str | None = None
    party_is_non_resident: bool = False
    external_ref: str | None = None
    party_pan_provided: bool | None = None


class TransactionSource(ABC):
    """A source of transactions for a single ingestion run."""

    @abstractmethod
    def fetch(self) -> list[RawTransaction]:
        """Return all transactions this source has to offer for this run."""
        raise NotImplementedError


class TransactionSourceError(ValueError):
    """Raised for any malformed/rejected input from a TransactionSource."""
