import json

from google import genai
from google.genai import types

from db.models import Category
from repositories import CategoryRepository, RoomRepository
from schemas.transaction import Payment, Split
from schemas.transaction import Transaction as TransactionDraft
from settings import Settings


def _merge_by_user(entries: list[Payment] | list[Split], model: type[Payment] | type[Split]):
    totals: dict[int, float] = {}
    for entry in entries:
        totals[entry.user_id] = round(totals.get(entry.user_id, 0) + entry.amount, 2)
    return [model(user_id=user_id, amount=amount) for user_id, amount in totals.items()]


def _equal_splits(total_amount: float, user_ids: list[int]) -> list[Split]:
    count = len(user_ids)
    share = round(total_amount / count, 2)
    splits = [Split(user_id=user_id, amount=share) for user_id in user_ids]
    splits[-1].amount = round(total_amount - share * (count - 1), 2)
    return splits


def normalize_transaction_draft(
    draft: TransactionDraft,
    *,
    created_by_id: int,
    rooms: list,
    category_ids: set[int],
) -> TransactionDraft:
    """Force LLM output into a persistable transaction for one of the user's rooms."""
    draft.created_by_id = created_by_id

    if draft.category_id not in category_ids:
        draft.category_id = None

    rooms_by_id = {room.id: room for room in rooms}
    if draft.room_id not in rooms_by_id:
        if len(rooms) != 1:
            raise ValueError("Could not determine a valid room for this transaction.")
        draft.room_id = rooms[0].id

    room = rooms_by_id[draft.room_id]
    member_ids = list(dict.fromkeys(member.user_id for member in room.members))
    member_id_set = set(member_ids)
    if created_by_id not in member_id_set:
        raise ValueError("Creator is not a member of the selected room.")

    if not draft.splits:
        if not member_ids:
            raise ValueError("Selected room has no members.")
        draft.splits = _equal_splits(draft.total_amount, member_ids)

    draft.payments = _merge_by_user(draft.payments, Payment)
    draft.splits = _merge_by_user(draft.splits, Split)

    payment_ids = {payment.user_id for payment in draft.payments}
    split_ids = {split.user_id for split in draft.splits}
    if not draft.payments or not draft.splits:
        raise ValueError("A transaction must include payments and splits.")
    if not payment_ids <= member_id_set or not split_ids <= member_id_set:
        raise ValueError("Payments and splits must use members of the selected room.")

    return draft


async def build_transaction_draft(
    message: str,
    created_by_id: int,
) -> tuple[TransactionDraft, dict[int, str]]:
    categories = await CategoryRepository().find_all(columns=[Category.id, Category.name])
    rooms = await RoomRepository().get_rooms_with_members_for_user(created_by_id)

    users_map: dict[int, str] = {}
    rooms_context = []
    for room in rooms:
        members = []
        for member in room.members:
            users_map[member.user_id] = member.user.name
            members.append({"user_id": member.user_id, "name": member.user.name})
        rooms_context.append(
            {
                "room_id": room.id,
                "name": room.name,
                "members": members,
            }
        )
    categories_context = [{"id": category_id, "name": category_name} for category_id, category_name in categories]

    prompt = f"""Parse the following expense message into a structured transaction.

User message: {message}

Available categories:
{json.dumps(categories_context, ensure_ascii=False)}

User's rooms and members (use user_id values in payments and splits):
{json.dumps(rooms_context, ensure_ascii=False)}

Rules:
- Set created_by_id to {created_by_id}
- Match category_id from the categories list when possible, otherwise null
- Set room_id to the matching room, or the only room if the user has one room
- payments must account for the full total_amount
- If splits are not specified, split the total equally among all room members
- Never leave splits empty
- Only use room_id and user_id values from the lists above
- Use the same language as the input for the description
"""

    client = genai.Client(api_key=Settings().gemini_api_key)
    draft = TransactionDraft.model_validate_json(
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=TransactionDraft.model_json_schema(),
            ),
        ).text
    )

    return (
        normalize_transaction_draft(
            draft,
            created_by_id=created_by_id,
            rooms=rooms,
            category_ids={category_id for category_id, _ in categories},
        ),
        users_map,
    )
