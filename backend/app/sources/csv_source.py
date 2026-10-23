import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.sources.base import RawTransaction, TransactionSource, TransactionSourceError, normalize_pan

MAX_ROWS = 500_000
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB, per FR-07

REQUIRED_FIELDS = ("transaction_date", "amount", "party_name")
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y")


def _parse_date(value: str):
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise TransactionSourceError(f"Unrecognized date format: {value!r}")


def _parse_amount(value: str) -> Decimal:
    cleaned = value.strip().replace(",", "").replace("₹", "")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise TransactionSourceError(f"Unrecognized amount: {value!r}") from exc
    if not amount.is_finite() or amount <= 0:
        raise TransactionSourceError("Amount must be finite and greater than zero.")
    return amount


class CSVTransactionSource(TransactionSource):
    """Parses an uploaded CSV into RawTransactions.

    ``column_mapping`` implements the field-mapping wizard (FR-09): keys are
    the required field names (``transaction_date``, ``amount``, ``party_name``,
    ``description``, ``declared_category``, ``party_gstin``, ``external_ref``),
    values are the actual column headers present in the uploaded file. If
    omitted, column headers are assumed to already match the required names.
    """

    def __init__(self, file_bytes: bytes, column_mapping: dict[str, str] | None = None):
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise TransactionSourceError(
                f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB upload limit."
            )
        self._file_bytes = file_bytes
        self._column_mapping = column_mapping or {}

    def _resolve_column(self, field: str) -> str:
        return self._column_mapping.get(field, field)

    def fetch(self) -> list[RawTransaction]:
        text = self._file_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None:
            raise TransactionSourceError("CSV file has no header row.")

        for field in REQUIRED_FIELDS:
            column = self._resolve_column(field)
            if column not in reader.fieldnames:
                raise TransactionSourceError(
                    f"Required column '{column}' (for field '{field}') not found in CSV header: "
                    f"{reader.fieldnames}. Use column_mapping to map a non-standard header."
                )

        transactions: list[RawTransaction] = []
        for row_index, row in enumerate(reader, start=1):
            if row_index > MAX_ROWS:
                raise TransactionSourceError(
                    f"CSV contains more than {MAX_ROWS:,} rows. Use the REST API for large datasets."
                )

            def get(field: str, default: str = "") -> str:
                return (row.get(self._resolve_column(field)) or default).strip()

            pan = get("party_pan") or None
            try:
                normalized_pan = normalize_pan(pan) if pan else None
            except ValueError as exc:
                raise TransactionSourceError(f"Invalid PAN on CSV row {row_index}: {exc}") from exc

            try:
                amount = _parse_amount(get("amount"))
            except TransactionSourceError as exc:
                raise TransactionSourceError(f"Invalid amount on CSV row {row_index}: {exc}") from exc

            transactions.append(
                RawTransaction(
                    transaction_date=_parse_date(get("transaction_date")),
                    amount=amount,
                    party_name=get("party_name") or "Unknown",
                    description=get("description"),
                    declared_category=get("declared_category") or None,
                    party_gstin=get("party_gstin") or None,
                    party_pan=normalized_pan,
                    party_pan_provided=(
                        normalized_pan is not None if "party_pan" in reader.fieldnames else None
                    ),
                    external_ref=get("external_ref") or None,
                )
            )

        return transactions
