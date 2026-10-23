from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuleContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer_is_specified_person: bool | None = None
    payer_is_designated_person: bool | None = None
    payee_is_individual_or_huf: bool | None = None
    service_kind: str | None = None
    property_stamp_duty_value: Decimal | None = Field(default=None, gt=0)
    property_consideration_total: Decimal | None = Field(default=None, gt=0)
    property_payment_is_full_consideration: bool | None = None
    payee_is_individual_shareholder: bool | None = None
    dividend_payment_is_non_cash: bool | None = None
    lottery_winnings_kind: Literal[
        "lottery",
        "crossword",
        "card_game",
        "game_show",
        "other_game",
        "gambling_betting",
    ] | None = None
    lottery_winnings_are_cash: bool | None = None
    vda_payer_is_individual_or_huf: bool | None = None
    vda_payer_turnover_within_limit: bool | None = None
    vda_payer_has_business_income: bool | None = None
    vda_consideration_is_cash: bool | None = None
