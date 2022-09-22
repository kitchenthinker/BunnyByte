import requests
import json
import datetime


class EGSGamesParser:

    def __init__(self):
        self.API = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
        self.param = {
            "locale": "ru-RU",
            "country": "RU",
            "allowCountries": "RU",

        }
        self.fp_url = 'https://store.epicgames.com/p/'
        self.free_games = dict()
        self.refresh()

    def get_json(self):
        r = requests.get(url=self.API, params=self.param)
        if r.status_code != 200:
            return None
        return r.json()

    def refresh(self):
        self.get_free_games()

    def get_free_games(self):
        data = self.get_json()
        json_data = dict()
        if data is not None:
            free_games_list = [x for x in data['data']['Catalog']['searchStore']['elements'] if
                               x['promotions'] is not None]

            for fg in free_games_list:
                if fg['promotions']['promotionalOffers'].__len__() > 0:
                    title = fg['title']
                    description = fg['description'],
                    url = fg['catalogNs']['mappings'][0]['pageSlug']
                    img = [x['url'] for x in fg['keyImages'] if x['type'] == 'OfferImageWide'][0]
                    str_date = fg['promotions']['promotionalOffers'][0]['promotionalOffers'][0]['endDate'][:10]
                    exp_date = str(datetime.datetime.strptime(str_date, "%Y-%m-%d"))[:10]
                    fg_item = {
                        'title': title,
                        'description': description[0],
                        'url': f'{self.fp_url}{url}',
                        'expdate': exp_date,
                        'img': img,
                    }
                    json_data[fg['id']] = fg_item
        self.free_games = json_data
