from pytube import (
    Channel,
    YouTube,
)
import discord
from discord import ButtonStyle
from discord.ui import Button, View

YT_URL = "https://www.youtube.com/channel"
BUNNY_CHANNEL_ID = "https://www.youtube.com/channel/UCuS7pDu3Pyrk0fXOL_TnCNQ"


class YTParser:

    def __init__(self, channel_id: str = BUNNY_CHANNEL_ID):
        self.channel_url = f"{channel_id}"
        self.channel: Channel = Channel(url=self.channel_url)
        self.last_video: YouTube | None = None
        self.current_video: YouTube | None = None
        self.current_livestream: YouTube | None = None
        self.is_livestream: bool = False
        self.fetch_last_video()

    def fetch_last_video(self):
        if self.channel.__len__() > 0:
            self.last_video = self.channel.videos[0]
            self.set_current_video(self.last_video)
            self.set_is_livestream(self.last_video)

    def set_is_livestream(self, video: YouTube):
        self.is_livestream = video.length == 0

    def set_current_video(self, video: YouTube):
        self.current_video = video

    async def get_last_livestream(self, max_index: int = 7):
        streams_slice = [x for x in self.channel.videos[:max_index] if x.length == 0]
        self.current_livestream = streams_slice[0] if streams_slice else None
        # streams_slice = [x for x in self.channel.videos[:max_index] if x.length == 0]
        # self.current_livestream = streams_slice[0] if not streams_slice
        # count = len(self.channel.videos)
        # if count == 0:
        #     return
        # end_ = count if count <= max_index else max_index
        # self.current_livestream = None if count == 0 else [x for x in self.channel.videos[:end_] if x.length == 0][0]

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
            # video.vid_info['videoDetails'].get('IsLive') not is None
        }

    def get_discord_video_card(self, video: YouTube, show_description: bool = False):
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
        video_button = Button(label="🐰 Смотреть 🥕",
                              style=ButtonStyle.red,
                              url=video_info['watch_url'])
        dc_view = View()
        dc_view.add_item(video_button)
        # video_card = {
        #     'embed_': embed_card,
        #     'component_': video_button,
        # }
        return video_info, embed_card, dc_view
