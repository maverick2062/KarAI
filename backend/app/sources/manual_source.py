from app.sources.base import RawTransaction, TransactionSource


class ManualEntryTransactionSource(TransactionSource):
    """Wraps one or more transactions entered directly through the UI form
    (as opposed to a bulk CSV upload)."""

    def __init__(self, entries: list[RawTransaction]):
        self._entries = entries

    def fetch(self) -> list[RawTransaction]:
        return list(self._entries)
