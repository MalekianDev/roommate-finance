import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from schemas.transaction import Payment
from services.transaction import build_transaction_draft, normalize_transaction_draft


def _mock_llm(monkeypatch, transaction_draft, room_with_members, categories):
    category_repo = MagicMock()
    category_repo.find_all = AsyncMock(return_value=categories)
    room_repo = MagicMock()
    room_repo.get_rooms_with_members_for_user = AsyncMock(return_value=[room_with_members])
    response = MagicMock()
    response.text = transaction_draft.model_dump_json()
    client = MagicMock()
    client.models.generate_content.return_value = response

    monkeypatch.setattr("services.transaction.CategoryRepository", lambda: category_repo)
    monkeypatch.setattr("services.transaction.RoomRepository", lambda: room_repo)
    monkeypatch.setattr("services.transaction.genai.Client", lambda **_: client)
    monkeypatch.setattr("services.transaction.Settings", lambda: SimpleNamespace(gemini_api_key="test-key"))
    return category_repo, room_repo, client


@pytest.mark.asyncio
async def test_build_transaction_draft_builds_context_and_enforces_creator(
    monkeypatch,
    transaction_draft,
    users_map,
    room_with_members,
):
    categories = [(1, "Food"), (2, "Transport")]
    category_repo, room_repo, client = _mock_llm(monkeypatch, transaction_draft, room_with_members, categories)

    draft, users = await build_transaction_draft("Dinner was 42.5", created_by_id=7)

    assert draft.created_by_id == 7
    assert draft.description == "Dinner"
    assert users == users_map
    category_repo.find_all.assert_awaited_once()
    room_repo.get_rooms_with_members_for_user.assert_awaited_once_with(7)

    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert '"name": "Food"' in prompt
    assert '"room_id": 10' in prompt
    assert "Set created_by_id to 7" in prompt
    assert json.dumps({"user_id": 7, "name": "Sam"}, ensure_ascii=False) in prompt


@pytest.mark.asyncio
async def test_build_transaction_draft_overrides_model_created_by_id(monkeypatch, transaction_draft, room_with_members):
    transaction_draft.created_by_id = 999
    _mock_llm(monkeypatch, transaction_draft, room_with_members, [])

    draft, users = await build_transaction_draft("Dinner", created_by_id=7)

    assert draft.created_by_id == 7
    assert draft.category_id is None
    assert users == {7: "Sam", 8: "Alex"}


@pytest.mark.asyncio
async def test_build_transaction_draft_fills_missing_splits(monkeypatch, transaction_draft, room_with_members):
    transaction_draft.splits = []
    _mock_llm(monkeypatch, transaction_draft, room_with_members, [(1, "Food")])

    draft, _ = await build_transaction_draft("Dinner was 42.5", created_by_id=7)

    assert {(split.user_id, split.amount) for split in draft.splits} == {(7, 21.25), (8, 21.25)}


def test_normalize_fills_room_when_user_has_only_one(transaction_draft, room_with_members):
    transaction_draft.room_id = None

    draft = normalize_transaction_draft(
        transaction_draft,
        created_by_id=7,
        rooms=[room_with_members],
        category_ids={1},
    )

    assert draft.room_id == 10


def test_normalize_rejects_room_that_user_does_not_belong_to(transaction_draft, room_with_members):
    transaction_draft.room_id = 99
    second_room = SimpleNamespace(id=11, members=room_with_members.members)

    with pytest.raises(ValueError, match="valid room"):
        normalize_transaction_draft(
            transaction_draft,
            created_by_id=7,
            rooms=[room_with_members, second_room],
            category_ids={1},
        )


def test_normalize_rejects_splits_for_users_outside_the_room(transaction_draft, room_with_members):
    transaction_draft.splits[1].user_id = 99

    with pytest.raises(ValueError, match="members of the selected room"):
        normalize_transaction_draft(
            transaction_draft,
            created_by_id=7,
            rooms=[room_with_members],
            category_ids={1},
        )


def test_normalize_merges_duplicate_payers(transaction_draft, room_with_members):
    transaction_draft.payments = [
        Payment(user_id=7, amount=20),
        Payment(user_id=7, amount=22.5),
    ]

    draft = normalize_transaction_draft(
        transaction_draft,
        created_by_id=7,
        rooms=[room_with_members],
        category_ids={1},
    )

    assert len(draft.payments) == 1
    assert draft.payments[0].user_id == 7
    assert draft.payments[0].amount == 42.5
