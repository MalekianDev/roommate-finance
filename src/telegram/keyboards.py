from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


BACK_BUTTON = [KeyboardButton(text="🔙 Back")]
BACK_KEYBOARD = ReplyKeyboardMarkup(keyboard=[BACK_BUTTON], resize_keyboard=True)


YES_NO_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Yes"), KeyboardButton(text="❌ No")],
    ],
    resize_keyboard=True,
)


def main_menu_keyboard(is_superuser: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📝 Add Transaction")],
        [
            KeyboardButton(text="📊 Report"),
            KeyboardButton(text="⚖️ Balance"),
        ],
        [KeyboardButton(text="👯 Manage Rooms")],
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
                [KeyboardButton(text="🧑‍💻 Rooms list")],
                BACK_BUTTON,
            ]
        )

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )
