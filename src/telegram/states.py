from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    name = State()


class RoomStates(StatesGroup):
    name = State()
    confirming = State()


class TransactionStates(StatesGroup):
    confirming = State()
