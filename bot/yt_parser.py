from pytubefix import (
    Channel,
    YouTube,
)
from discord import ButtonStyle, Embed, Colour
from discord.ui import Button, View
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from enum import Enum
import re

YT_URL = "https://www.youtube.com/channel"
BUNNY_CHANNEL_ID = "https://www.youtube.com/channel/UCuS7pDu3Pyrk0fXOL_TnCNQ"

NOTIFICATION_IMAGE = "https://icon-icons.com/icons2/1283/PNG/128/1497619898-jd24_85173.png"
LIVESTREAM_IMG = "https://img.informer.com/icons_mac/png/128/448/448535.png"


class YoutubeStreamStatus(Enum):
    ERROR = 0
    UPCOMING = 1
    NOTIFIED = 2
    ONLINE = 3
    NOTIFIED_ONLINE = 4
    FINISHED = 5


class YouTubeLiveStream(YouTube):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.livestream: bool = False
        self.upcoming: bool = False
        self.upcoming_date: datetime | None = None
        self.greeting: str | None = None

    def get_video_info(self, stream_status: YoutubeStreamStatus = None, message_id = ''):
        return {
            'video_id': self.video_id,
            'title': self.title,
            'author': self.author,
            'greeting': self.greeting,
            'publish_date': self.publish_date,
            'upcoming_date': self.upcoming_date,
            'thumbnail_url': self.thumbnail_url,
            'watch_url': self.watch_url,
            'livestream': self.livestream,
            'upcoming': self.upcoming,
            'status': stream_status,
            'message_id': message_id,
        }

    def get_discord_video_card(self):
        video_info = self.get_video_info()
        embed_card = Embed(title=video_info['title'], description=video_info['greeting'],
                           url=video_info['watch_url'], colour=Colour.purple())
        # embed_card.set_thumbnail(url='./img/yt_logo.png')
        embed_card.set_author(name=video_info['author'])
        embed_card.set_image(url=video_info['thumbnail_url'])
        if video_info['livestream']:
            embed_card.set_thumbnail(url=LIVESTREAM_IMG)
        if video_info['upcoming']:
            embed_card.set_thumbnail(url=NOTIFICATION_IMAGE)
        video_button = Button(label="🐰 Смотреть 🥕", style=ButtonStyle.red, url=video_info['watch_url'])
        dc_view = View()
        dc_view.add_item(video_button)
        return video_info, embed_card, dc_view


class YTLiveStreamParser:

    def __init__(self, channel_url: str = BUNNY_CHANNEL_ID):
        self.channel_url = channel_url
        self.current_livestream: YouTubeLiveStream | None = None

    @staticmethod
    def get_video_info(stream: YouTubeLiveStream, stream_status: YoutubeStreamStatus = None):
        return stream.get_video_info(stream_status)

    @staticmethod
    def get_discord_video_card(stream: YouTubeLiveStream):
        return stream.get_discord_video_card()

    async def get_html_page_info(self):
        async with aiohttp.ClientSession() as session:
            channel_url = f"{self.channel_url}/live"
            async with session.get(channel_url, cookies={'CONSENT': 'PENDING+987','SOCS': 'CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmRlIAEaBgiAo_CmBg'}) as page:
                if page.status == 200:
                    return BeautifulSoup(await page.text(), "html.parser")
                else:
                    return None

    async def get_last_livestream(self) -> YouTubeLiveStream:
        current_livestream = self.current_livestream
        livestream_data = await self.get_html_page_info()
        #print(f"{livestream_data[:100]}")
        if livestream_data is not None:
            live = livestream_data.find("link", {"rel": "canonical"})
            print(f"{live=}")
            if live is not None:
                temp_livestream = YouTubeLiveStream(live.get('href'))
                print(f"{temp_livestream=}")
                if temp_livestream.channel_id is not None:
                    temp_livestream.upcoming = temp_livestream.vid_info['videoDetails'].get('isUpcoming', False)
                    temp_livestream.livestream = temp_livestream.vid_info['videoDetails'].get('isLive', False)
                    if temp_livestream.upcoming:
                        #re_result = re.findall(r'scheduledStartTime.+(\d{10}).+mainText', temp_livestream.embed_html)
                        #timestamp = re_result[0]

                        timestamp = temp_livestream.vid_info['playabilityStatus']['liveStreamability']['liveStreamabilityRenderer']['offlineSlate']['liveStreamOfflineSlateRenderer']['scheduledStartTime']
                        temp_livestream.upcoming_date = datetime(1970, 1, 1, 0, 0, 0) + timedelta(
                            seconds=int(timestamp))
                        print(f"{temp_livestream.title} | {temp_livestream.upcoming_date}")
                    current_livestream = temp_livestream
        self.current_livestream = current_livestream
        if self.current_livestream is not None: print(f"{current_livestream.title} | {temp_livestream.upcoming_date}")
        return current_livestream
