"""Parses a user-uploaded mock AIS export (CSV) into AISRecordInput rows.
This is the realistic near-term path until real IT-portal OAuth access
exists (see ``oauth_stub.py``): the IT portal already lets a taxpayer
download their own AIS as a CSV/PDF/JSON today, so accepting a user upload
is a genuine, working feature, not a placeholder.
"""

import csv
import io
from decimal import Decimal, InvalidOperation

from app.ais_mock.synthetic_ais import AISRecordInput
from app.sources.base import TransactionSourceError

REQUIRED_COLUMNS = ("reporting_entity", "amount", "category")


def parse_ais_csv(file_bytes: bytes) -> list[AISRecordInput]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise TransactionSourceError("AIS CSV file has no header row.")

    for column in REQUIRED_COLUMNS:
        if column not in reader.fieldnames:
            raise TransactionSourceError(f"Required column '{column}' not found in AIS CSV header.")

    records: list[AISRecordInput] = []
    for row in reader:
        try:
            amount = Decimal(row["amount"].strip().replace(",", "").replace("₹", ""))
        except InvalidOperation as exc:
            raise TransactionSourceError(f"Unrecognized AIS amount: {row['amount']!r}") from exc

        records.append(
            AISRecordInput(
                reporting_entity=row["reporting_entity"].strip(),
                amount=amount,
                category=row["category"].strip(),
            )
        )
    return records
