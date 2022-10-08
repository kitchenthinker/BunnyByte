from enum import Enum
from discord.app_commands import Choice


# region SPINWHEEL
class SpinWheelGameStatus(Enum):
    InList = 0
    InProgress = 1
    InFinishedList = 2
    InWaitingList = 3
    InBanList = 4


game_status_list = [
    {"name": "1. Рулетке.", "value": SpinWheelGameStatus.InList.value, "emoji": "🎡",
     "description": "Список игр, вошедших в рулетку."},
    {"name": "2. Проходим.", "value": SpinWheelGameStatus.InProgress.value, "emoji": "🎮",
     "description": "Список игр в процессе прохождения."},
    {"name": "3. Закончили.", "value": SpinWheelGameStatus.InFinishedList.value, "emoji": "✅",
     "description": "Список уже пройденных игр."},
    {"name": "4. Ждем.", "value": SpinWheelGameStatus.InWaitingList.value, "emoji": "😗",
     "description": "Список предложенных, но ещё не вышедших игр."},
    {"name": "5. Баня.", "value": SpinWheelGameStatus.InBanList.value, "emoji": "🥵",
     "description": "Игры из этого списка можно попытаться реабилитировать массовыми уговорами. "
                    "Если очень долго будете пытать УРАЗАЙКУ, возможно, она сдастся. А, возможно, и нет. 😝 "
                    "Возможно, она даже разозлится, но, как говорится ºкто не рискуетº... Удачи, зайка!"},
]
game_status_choices = [
    Choice(name=f"{x['emoji']} {x['name']}", value=x['value'])
    for x in game_status_list
]


class SpinWheelGameStatusEdit(Enum):
    InList = 0
    InProgress = 1
    InFinishedList = 2
    InWaitingList = 3
    InBanList = 4
    Previous = 5


class SpinWheelAction(Enum):
    Add = 0,
    Edit = 1,
    Delete = 2


# endregion

SPINWHEEL_RULES = 'Правила рулетки\n' \
                  '1. Рулетка будет запускаться всякий раз, как на YouTube будет заканчиваться очередное прохождение.\n' \
                  '2. Предложить игру можно в разделе #🙏пройди-ка🙏\n' \
                  '3. УРАЗАЙКА оставляет за собой право отказаться добавлять игру в рулетку.\n' \
                  '4. УРАЗАЙКА оставляет за собой право добавлять в рулетку игры, которые никто не предлагал.\n' \
                  '5. УРАЗАЙКА оставляет за собой право проходить игры вне очереди.\n' \
                  '6. Если игра ещё не попала в рулетку, скоро она в неё попадёт. Либо она уже в списке не попавших в рулетку игр.\n' \
                  '7. Одновременно в прохождении могут находиться 2 - 3 игры.\n' \
                  '8. Правила рулетки могут изменяться или дополняться с течением времени.'
