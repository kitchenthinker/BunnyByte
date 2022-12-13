import requests
import datetime
from discord import ButtonStyle, Embed, Colour, File
from discord.ui import Button, View
from typing import List
from bs4 import BeautifulSoup

EPIC_LOGO_IMG = "https://raw.githubusercontent.com/kitchenthinker/BunnyByte/master/bot/img/i-epic.png"
STEAM_LOGO_IMG = "https://raw.githubusercontent.com/kitchenthinker/BunnyByte/master/bot/img/i-steam.png"
GOG_LOGO_IMG = "https://raw.githubusercontent.com/kitchenthinker/BunnyByte/master/bot/img/i-gog.png"
EMPTY_LOGO_IMG = "https://raw.githubusercontent.com/kitchenthinker/BunnyByte/master/bot/img/i-empty.png"

market_icons_dict = {
    "Steam": STEAM_LOGO_IMG,
    "Epic Games Store": EPIC_LOGO_IMG,
    "GOG": GOG_LOGO_IMG,
}


def get_right_instruction(instruction: str) -> str:
    right_instruction = ''
    rows = BeautifulSoup(instruction, "html.parser").contents
    for row in rows:
        if row.name is None:
            right_instruction += f"{row} "
        else:
            right_instruction += f"[{row.text}]({row.attrs['href']}) "

    return right_instruction


def get_market_icon(platforms: str) -> str:
    for key, value in market_icons_dict.items():
        if key in platforms:
            return value
    return EMPTY_LOGO_IMG


class GamerPowerGame:

    def __init__(self, **game_info):
        self.id = game_info.get('game_id')
        self.title = game_info.get('title')
        self.description = game_info.get('description')
        self.instructions = game_info.get('instructions')
        self.platforms = game_info.get('platforms')
        self.url = game_info.get('url')
        self.exp_date = game_info.get('exp_date')
        self.thumbnail = game_info.get('thumbnail')

    def get_game_info(self):
        return {
            "game_id": self.id,
            "title": self.title,
            "description": self.description,
            "instructions": self.instructions,
            "platforms": self.platforms,
            "url": self.url,
            "exp_date": self.exp_date,
            "thumbnail": self.thumbnail,
        }

    def get_discord_game_card(self):
        game_card_info = self.get_game_info()
        embed_card = Embed(title=self.title,
                           url=self.url,
                           description=self.description,
                           # timestamp=video_info['publish_date'],
                           colour=Colour.purple())
        # thumbnail_file = File(get_market_icon(self.platforms), filename="market_icon.png")
        # embed_card.set_thumbnail(url="attachment://epic_logo.png")
        url_icon_ = get_market_icon(self.platforms)
        embed_card.set_author(name="Зайка 🐰! Успей забрать морковку на халяву 🥕!", icon_url=url_icon_)
        embed_card.set_image(url=self.thumbnail)
        embed_card.add_field(name="Спеши до:", value=datetime.datetime.strftime(self.exp_date, "%d.%m.%y %H:%M"),
                             inline=True)
        instruction = get_right_instruction(self.instructions)
        embed_card.add_field(name="Как забрать:", value=instruction, inline=True)
        embed_card.set_footer(text="Thanks gamerpower.com for API")
        game_button = Button(label="🥕🥕🥕 Забрать 🥕🥕🥕", style=ButtonStyle.red, url=self.url)
        dc_view = View()
        dc_view.add_item(game_button)
        return game_card_info, embed_card, dc_view #, thumbnail_file


class GamerPowerParser:

    def __init__(self):
        self.API = "https://www.gamerpower.com/api/filter?platform=epic-games-store.steam.gog&type=game"
        # self.param = {
        #     "locale": "ru-RU",
        #     "country": "RU",
        #     "allowCountries": "RU",
        #
        # }
        # self.fp_url = 'https://store.epicgames.com/p/'
        self.free_games: List[GamerPowerGame] = []
        self.empty: bool = True
        self.refresh()

    def get_games_data_from_api(self):
        r = requests.get(url=self.API)
        if r.status_code != 200:
            return None
        return r.json()

    def refresh(self):
        self.get_free_games()
        self.empty = self.free_games.__len__() == 0

    def get_free_games(self):
        data = self.get_games_data_from_api()
        if data is not None:
            free_games_list = [x for x in data if x['status'] == "Active"]

            for fg in free_games_list:
                str_date = fg['end_date'] if fg['end_date'] != 'N/A' else '2099-01-01 00:00:00'
                exp_date = datetime.datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S")
                fg_item = {
                    "game_id": str(fg['id']),
                    "title": fg['title'],
                    "description": fg['description'],
                    "instructions": fg['instructions'],
                    "platforms": fg['platforms'],
                    "url": fg['open_giveaway_url'],
                    "exp_date": exp_date,
                    "thumbnail": fg['image'],
                }
                gp_game = GamerPowerGame(**fg_item)
                self.free_games.append(gp_game)
