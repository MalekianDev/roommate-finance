from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


BACK_BUTTON = [KeyboardButton(text="🔙 Back")]


def main_menu_keyboard(is_superuser: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📝 Add Transaction")],
        [
            KeyboardButton(text="📊 Report"),
            KeyboardButton(text="⚖️ Balance"),
        ],
    ]

    if is_superuser:
        buttons.append([KeyboardButton(text="⚙️ Settings")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )


def manage_rooms_keyboard(has_active_room: bool = True) -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="🤝 Create Room"),
            KeyboardButton(text="🧳 Join Room"),
        ],
    ]

    if has_active_room:
        buttons.extend(
            [
                [KeyboardButton(text="🧑‍💻 Manage Rooms")],
                BACK_BUTTON,
            ]
        )

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )
