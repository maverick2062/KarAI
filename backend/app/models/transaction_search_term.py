from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TransactionSearchTerm(Base):
    __tablename__ = "transaction_search_terms"
    __table_args__ = (
        UniqueConstraint("transaction_id", "term_hash", name="uq_transaction_search_term"),
        Index("ix_transaction_search_user_term", "user_id", "term_hash"),
        Index("ix_transaction_search_transaction", "transaction_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_hash: Mapped[str] = mapped_column(String(64), nullable=False)
