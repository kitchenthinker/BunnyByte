from enum import Enum

import discord
from discord.app_commands import Choice
from typing import List
from discord.ui import Button, View
from discord import Embed, Guild, ButtonStyle, Interaction


# region SPINWHEEL
class SpinWheelGameStatus(Enum):
    InList = 0
    InProgress = 1
    InFinishedList = 2
    InWaitingList = 3
    InBanList = 4
    InListStream = 5


game_status_dict = {
    SpinWheelGameStatus.InList: {
        "name": "В Рулетке.",
        "value": SpinWheelGameStatus.InList.value,
        "emoji": "🎡",
        "description": "Список игр, вошедших в рулетку.",
        "show_pl": False},
    SpinWheelGameStatus.InListStream: {
        "name": "1. В Рулетке (Стримы).",
        "value": SpinWheelGameStatus.InListStream.value,
        "emoji": "🌊",
        "description": "Список игр, вошедших в рулетку (стримы).",
        "show_pl": False},
    SpinWheelGameStatus.InProgress: {
        "name": "Проходим.",
        "value": SpinWheelGameStatus.InProgress.value,
        "emoji": "🎮",
        "description": "Список игр в процессе прохождения.",
        "show_pl": True},
    SpinWheelGameStatus.InFinishedList: {
        "name": "Закончили.",
        "value": SpinWheelGameStatus.InFinishedList.value,
        "emoji": "✅",
        "description": "Список уже пройденных игр.",
        "show_pl": True},
    SpinWheelGameStatus.InWaitingList: {
        "name": "Ждем.",
        "value": SpinWheelGameStatus.InWaitingList.value,
        "emoji": "😗",
        "description": "Список предложенных, но ещё не вышедших игр.",
        "show_pl": False},
    SpinWheelGameStatus.InBanList: {
        "name": "Баня.",
        "value": SpinWheelGameStatus.InBanList.value, "emoji": "🥵",
        "description": "Игры из этого списка можно попытаться реабилитировать массовыми уговорами. "
                       "Если очень долго будете пытать УРАЗАЙКУ, возможно, она сдастся. А, возможно, и нет. 😝 "
                       "Возможно, она даже разозлится, но, как говорится ºкто не рискуетº... Удачи, зайка!",
        "show_pl": False},
}
game_status_choices = [
    Choice(name=f"{x['emoji']} {x['name']}", value=x['value'])
    for x in game_status_dict.values()
]


class SpinWheelGameStatusEdit(Enum):
    InList = 0
    InProgress = 1
    InFinishedList = 2
    InWaitingList = 3
    InBanList = 4
    InListStream = 5
    Previous = 6


class SpinWheelAction(Enum):
    Add = 0,
    Edit = 1,
    Delete = 2


class Paginator:
    slice_number = 6

    def __init__(self, guild: Guild, game_list_: List, info: dict,
                 defer_: bool = True, admin_call: bool = False, table_view: bool = False):

        self.guild = guild
        self.game_list = game_list_
        self.info = info
        self.defer = defer_
        self.is_admin = admin_call
        self.table_view = table_view

        self.emb_list: List[Embed] = []
        self.index = 0
        self.max_index = len(self.game_list) - 1
        self.pages_count = 1
        self.current_emb: Embed | None = None
        self.view: CustomView | None = None
        self.generate_embeds()

    def add_align_field(self, embed: Embed):
        if self.table_view:
            if len(embed.fields) > 3:
                while len(embed.fields) % 3 != 0:
                    embed.add_field(name=f"#", value=f"#", inline=True)

    def generate_embeds(self):

        def add_field_to_emb(emb_group: Embed, game):
            value_ = "\u200b"
            if self.info['show_pl']:
                value_ = f"📺 [Посмотреть]({game['url']})" if game['url'] is not None else "📺 Пока пусто"
            if self.is_admin:
                value_ += f"\n💬:{game['comment']}"
            emb_group.add_field(name=f"🕹️ {game['game']}", value=f"{value_}\n\n", inline=bool(self.table_view))

        pages_count = (len(self.game_list) // Paginator.slice_number)
        self.pages_count = pages_count + 1 if (len(self.game_list) % Paginator.slice_number) != 0 else pages_count

        game_slices = [self.game_list[i:i + Paginator.slice_number]
                       for i in range(0, self.max_index + 1, Paginator.slice_number)]

        for game_slice in game_slices:
            embed = Embed(title=f"{self.info['emoji']} {self.info['name']}",
                          description=self.info['description'])
            embed.set_footer(text=f"Page {self.index + 1}/{self.pages_count}")

            for game_ in game_slice:
                add_field_to_emb(embed, game_)
            if self.table_view:
                self.add_align_field(embed)
            self.emb_list.append(embed)
        self.view = CustomView(_paginator=self, defer=self.defer)
        if len(self.game_list) <= Paginator.slice_number:
            self.view.clear_items()
        self.set_current_emb()

    def set_current_emb(self):
        self.current_emb = self.emb_list[self.index]

    def index_reach_edge(self):
        if any([self.index < 0, self.index > self.pages_count - 1]):
            self.index = 0

    def next(self):
        return self.get_current_item(step=1)

    def prev(self):
        return self.get_current_item(step=-1)

    def get_current_item(self, step: int = 0):
        self.index += step
        self.index_reach_edge()
        self.set_current_emb()
        self.current_emb.set_footer(text=f"Page {self.index + 1}/{self.pages_count}")
        return self.emb_list[self.index]

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.


class CustomView(View):

    def __init__(self, _paginator: Paginator, defer: bool = True):
        super().__init__()
        self.value = "\u200b"
        self.defer = defer
        self.paginator: Paginator = _paginator

    @discord.ui.button(label='Page', style=ButtonStyle.red, emoji='⏮')
    async def page_previous(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=self.defer)
        await interaction.edit_original_response(embed=self.paginator.prev())  # ephemeral=True)
        # self.value = False
        # self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label='Page', style=ButtonStyle.green, emoji='⏭')
    async def page_next(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=self.defer)
        await interaction.edit_original_response(embed=self.paginator.next())  # ephemeral=True)
        # self.value = False
        # self.stop()


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
