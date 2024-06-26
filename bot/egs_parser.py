import requests
import datetime
from discord import ButtonStyle, Embed, Colour
from discord.ui import Button, View
from typing import List

EPICLOGO_IMG = "https://cdn.icon-icons.com/icons2/2428/PNG/128/epic_games_black_logo_icon_147139.png"


class EGSGame:

    def __init__(self, **game_info):
        self.id = game_info.get('game_id')
        self.title = game_info.get('title')
        self.description = game_info.get('description')
        self.url = game_info.get('url')
        self.exp_date = game_info.get('exp_date')
        self.thumbnail = game_info.get('thumbnail')

    def get_game_info(self):
        return {
            "game_id": self.id,
            "title": self.title,
            "description": self.description,
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

        embed_card.set_author(name="Зайка 🐰! Успей забрать морковку на халяву 🥕!")
        embed_card.set_image(url=self.thumbnail)
        # thumbnail_file = discord.File("./img/epic_logo.png", filename="epic_logo.png")
        embed_card.set_thumbnail(url=EPICLOGO_IMG)
        # embed_card.set_thumbnail(url="attachment://epic_logo.png")
        embed_card.add_field(name="Спеши до:", value=datetime.datetime.strftime(self.exp_date, "%d.%m.%y %H:%M"))
        game_button = Button(label="🥕🥕🥕 Забрать 🥕🥕🥕", style=ButtonStyle.red, url=self.url)
        dc_view = View()
        dc_view.add_item(game_button)
        return game_card_info, embed_card, dc_view  # , thumbnail_file


class EGSGamesParser:

    def __init__(self):
        self.API = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
        self.param = {
            "locale": "ru-RU",
            "country": "RU",
            "allowCountries": "RU",

        }
        self.fp_url = 'https://store.epicgames.com/p/'
        self.free_games: List[EGSGame] = []
        self.empty: bool = True
        self.refresh()

    def get_games_data_from_api(self):
        r = requests.get(url=self.API, params=self.param)
        if r.status_code != 200:
            return None
        return r.json()

    def refresh(self):
        self.get_free_games()
        self.empty = self.free_games.__len__() == 0

    def get_free_games(self):
        data = self.get_games_data_from_api()
        if data is not None:
            free_games_list = [x for x in data['data']['Catalog']['searchStore']['elements'] if
                               x['promotions'] is not None and x['price']['totalPrice']['discountPrice'] == 0]

            for fg in free_games_list:
                if fg['promotions']['promotionalOffers'].__len__() > 0:
                    title = fg['title']
                    description = fg['description'],
                    url = fg['catalogNs']['mappings'][0]['pageSlug']
                    img = [x['url'] for x in fg['keyImages'] if x['type'] == 'OfferImageWide'][0]
                    str_date = fg['promotions']['promotionalOffers'][0]['promotionalOffers'][0]['endDate']
                    # r_date = parser.isoparse(str_date)
                    exp_date = datetime.datetime.strptime(str_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    fg_item = {
                        "game_id": fg['id'],
                        "title": title,
                        "description": description[0],
                        "url": f'{self.fp_url}{url}',
                        "exp_date": exp_date,
                        "thumbnail": img,
                    }
                    egs_game = EGSGame(**fg_item)
                    self.free_games.append(egs_game)
