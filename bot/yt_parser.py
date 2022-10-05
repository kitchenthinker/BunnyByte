from pytube import (
    Channel,
    YouTube,
)
import discord
from discord import ButtonStyle
from discord.ui import Button, View
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from enum import Enum

YT_URL = "https://www.youtube.com/channel"
BUNNY_CHANNEL_ID = "https://www.youtube.com/channel/UCuS7pDu3Pyrk0fXOL_TnCNQ"

NOTIFICATION_IMAGE = "https://icon-icons.com/icons2/1283/PNG/128/1497619898-jd24_85173.png"
LIVESTREAM_IMG = "https://img.informer.com/icons_mac/png/128/448/448535.png"

class YoutubeStreamStatus(Enum):
    UPCOMING = 1
    NOTIFIED = 2
    ONLINE = 3
    NOTIFIED_ONLINE = 4
    FINISHED = 5

class YTParser:

    def __init__(self, channel_id: str = BUNNY_CHANNEL_ID, create_channel_object: bool = True):
        self.channelURL = f"{channel_id}"

        self.channel: Channel = Channel(url=self.channelURL) if create_channel_object else None
        self.author: str | None = None
        self.currentVideo: YouTube | None = None
        self.currentLiveStream: YouTube | None = None
        self.isLivestream: bool = False
        self.isUpcoming: bool = False
        self.isLiveContent: bool = False
        self.channelIsEmpty: bool = self.is_channel_empty()
        self.upcomingDate: datetime | None = None
        if self.channel is not None:
            self.fetch_last_videos()

    def is_channel_empty(self):
        if self.channel is None:
            return None
        return self.channel.__len__() == 0

    def fetch_last_videos(self):
        if not self.channelIsEmpty:
            last_video = self.channel.videos[0]
            self.set_current_video(last_video)
            self.set_is_livestream(last_video)
            # self.get_last_livestream()

    def set_is_livestream(self, video: YouTube):
        self.isLivestream = video.length == 0

    def set_current_video(self, video: YouTube):
        self.currentVideo = video

    # def get_last_livestream(self, max_index: int = 7):
    #     streams_slice = [x for x in self.channel.videos[:max_index] if x.length == 0]
    #     self.current_livestream = streams_slice[0] if streams_slice else None

    @staticmethod
    def get_video_info(video: YouTube):
        return {
            'video_id': video.video_id,
            'title': video.title,
            'author': video.author,
            'description': video.description,
            'publish_date': video.publish_date,
            'thumbnail_url': video.thumbnail_url,
            'watch_url': video.watch_url,
            'livestream': video.length == 0,
            'isUpcoming': video.vid_info['videoDetails'].get('isUpcoming'),
            'isLiveContent': video.vid_info['videoDetails'].get('isLiveContent'),
        }

    def get_discord_video_card(self, video: YouTube, show_description: bool = False, is_livestream: bool = False):
        video_info = self.get_video_info(video)
        video_description = video_info['description'] if show_description else None
        embed_card = discord.Embed(title=video_info['title'],
                                   url=video_info['watch_url'],
                                   description=video_description,
                                   # timestamp=video_info['publish_date'],
                                   colour=discord.Colour.purple())

        # embed_card.set_thumbnail(url='./img/yt_logo.png')
        embed_card.set_author(name=video_info['author'])
        embed_card.set_image(url=video_info['thumbnail_url'])
        if is_livestream:
            embed_card.set_thumbnail(url=LIVESTREAM_IMG)
        video_button = Button(label="🐰 Смотреть 🥕", style=ButtonStyle.red, url=video_info['watch_url'])
        dc_view = View()
        dc_view.add_item(video_button)
        return video_info, embed_card, dc_view

    async def get_last_livestream(self, channel_url: str = None):
        channel_url = self.channelURL if channel_url is None else channel_url

        async with aiohttp.ClientSession() as session:
            channel_url = f"{channel_url}/live"
            async with session.get(channel_url, cookies={'CONSENT': 'YES+42'}) as page:
                if page.status == 200:
                    soup = BeautifulSoup(await page.text(), "html.parser")
                    live = soup.find("link", {"rel": "canonical"})
                    current_livestream = YouTube(live.attrs['href'])
                    if current_livestream.channel_id is not None:
                        self.isUpcoming = current_livestream.vid_info['videoDetails'].get('isUpcoming', False)
                        self.isLiveContent = False if self.isUpcoming else True
                        self.author = current_livestream.author
                        if self.isUpcoming:
                            timestamp = current_livestream.vid_info['playabilityStatus']['liveStreamability'][
                                'liveStreamabilityRenderer']['offlineSlate']['liveStreamOfflineSlateRenderer'][
                                'scheduledStartTime']
                            self.upcomingDate = datetime(1970, 1, 1, 0, 0, 0) + timedelta(seconds=int(timestamp))
                    else:
                        current_livestream = None
                else:
                    current_livestream = None
        self.currentLiveStream = current_livestream
        return self
