from discord import ButtonStyle, Embed, Colour
from discord.ui import Button, View
import aiohttp
from enum import Enum
import re
import json


YT_MSG_URL = "http://youtube.com/post/"
CHANNEL_IDENTIFIER = "urazayka"
NOTIFICATION_IMAGE = "https://icon-icons.com/icons2/1283/PNG/128/1497619898-jd24_85173.png"


class YoutubeMessageStatus(Enum):
    ERROR = 0
    NEW = 1
    NOTIFIED = 2


class YouTubeLastMessageTabParser:

    def __init__(self, prev_msg_id: str, channel_ident: str = CHANNEL_IDENTIFIER):
        self.msg_id = prev_msg_id
        self.msg_text = ''
        self.msg_author = ''
        self.msg_url = ''
        self.channel_identifier = channel_ident
        self.status = YoutubeMessageStatus.NOTIFIED

    def get_discord_msg_card(self):
        self.msg_url = f'{YT_MSG_URL}{self.msg_id}' 
        embed_card = Embed(title='Новое объявление на канале!',
                           description=self.msg_text,
                           url=self.msg_url,
                           colour=Colour.purple())
        embed_card.set_author(name=self.msg_author)
        embed_card.set_thumbnail(url=NOTIFICATION_IMAGE)
        
        url_button = Button(label="🐰 Перейти 🥕", 
                            style=ButtonStyle.red, 
                            url=self.msg_url)
        dc_view = View()
        dc_view.add_item(url_button)
        return embed_card, dc_view

    def _safe_get(self, data, keys, default=None):
        """Безопасно извлекает значение из вложенного словаря."""
        temp = data
        for key in keys:
            if isinstance(temp, dict) and key in temp:
                temp = temp[key]
            else:
                return default
        return temp

    async def _process_server_response(self, response):
        """Обрабатывает ответ от сервера и возвращает HTML-контент."""
        response.raise_for_status()
        return await response.text()

    def _extract_post_data(self, data):
        """Извлекает данные о постах из JSON и проверяет наличие новых записей (упрощенная версия)."""
        tabs = self._safe_get(data, ["contents", "twoColumnBrowseResultsRenderer", "tabs"], [])
        for tab in tabs:
            community_tab_url = self._safe_get(tab, ["tabRenderer", "endpoint", "commandMetadata", "webCommandMetadata", "url"])
            if community_tab_url and community_tab_url.endswith(f"/@{self.channel_identifier}/community"):
                sections = self._safe_get(tab, ["tabRenderer", "content", "sectionListRenderer", "contents"], [])
                for section in sections:
                    items = self._safe_get(section, ["itemSectionRenderer", "contents"], [])
                    for item in items:
                        post_thread = self._safe_get(item, ["backstagePostThreadRenderer"])
                        if post_thread:
                            post = self._safe_get(post_thread, ["post", "backstagePostRenderer"])
                            if post:
                                post_id = self._safe_get(post, ["postId"])
                                author_runs = self._safe_get(post, ["authorText", "runs"], [])
                                author_text = author_runs[0].get("text") if author_runs else ""
                                content_runs = self._safe_get(post, ["contentText", "runs"], [])
                                text = "".join([run.get("text", "") for run in content_runs])

                                if post_id == self.msg_id:
                                    print("Новых записей нет.")
                                else:
                                    print(f"Найдена новая запись от {author_text}:\nТекст: {text}")
                                    self.msg_author = author_text
                                    self.msg_text = text
                                    self.msg_id = post_id
                                    self.status = YoutubeMessageStatus.NEW
                break
        print("Записи сообщества не найдены.")


    async def check_new_community_post(self):
        """Проверяет наличие новых записей в сообществе YouTube-канала путем асинхронного скрапинга."""
        community_url = f"https://www.youtube.com/@{self.channel_identifier}/community" # Предполагаем, что используется псевдоним

        try:
            async with aiohttp.ClientSession() as session:
                _headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"}
                _cookies = {"CONSENT": "PENDING+987", "SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmRlIAEaBgiAo_CmBg"}
                async with session.get(community_url, cookies=_cookies, headers=_headers) as response:
                    html_content = await self._process_server_response(response)

                    # Поиск ytInitialData
                    match = re.search(r"var ytInitialData = ({.*?});", html_content)
                    if match:
                        json_str = match.group(1)
                        try:
                            data = json.loads(json_str)
                            self._extract_post_data(data)
                        except json.JSONDecodeError as e:
                            print(f"Ошибка при парсинге JSON: {e}")
                    else:
                        print("Не удалось найти ytInitialData.")

        except aiohttp.ClientError as e:
            print(f"Ошибка при получении страницы (aiohttp): {e}")
        except Exception as e:
            print(f"Произошла непредвиденная ошибка: {e}")