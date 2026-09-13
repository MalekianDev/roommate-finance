from pydantic import BaseModel, Field


class Payment(BaseModel):
    id: int | None = None
    user_id: int = Field(description="ID of the user who paid")
    amount: float = Field(description="Amount paid by this user")


class Split(BaseModel):
    id: int | None = None
    user_id: int = Field(description="ID of the user who owes this amount")
    amount: float = Field(description="Amount owed by this user")


class Transaction(BaseModel):
    id: int | None = None
    room_id: int | None = Field(
        description="ID of the selected room from the user's rooms. Use the matching room, or the only room if the user has one."
    )
    created_by_id: int = Field(description="ID of the user who created this transaction")
    description: str = Field(description="Short description of the transaction, in the same language as the input")
    category_id: int | None = Field(
        default=None,
        description="Matched category ID from the provided category list, or null if no good match",
    )
    total_amount: float = Field(description="Total amount of the transaction")
    payments: list[Payment] = Field(description="List of who paid how much. Must include at least one payment.")
    splits: list[Split] = Field(
        default_factory=list,
        description=(
            "List of who owes how much. If the user does not specify splits, divide total_amount equally "
            "across every member of the selected room. Do not leave this empty."
        ),
    )
