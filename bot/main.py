import time
import datetime
import config
import discord
import json
from discord.ext import commands
import asyncio
import pymysql
import pymysql.cursors

from egs_parser import (
    EGSGamesParser,
)

TIME_DELAY = 60 * 60 * 12
bot_settings = dict()
games_from_file = []
egs_obj = EGSGamesParser()


def read_games():
    try:
        with open('games.json', mode="r") as f:
            games = json.load(f)
    except FileNotFoundError as E:
        return False
    else:
        for key, setting in games.items():
            games_from_file.append(key)
        return True


def read_settings():
    try:
        with open('settings.json', mode="r") as f:
            settings = json.load(f)
    except FileNotFoundError as E:
        return False
    else:
        for key, setting in settings.items():
            bot_settings[key] = setting
        return True


def save_to_file(items, file_path):
    try:
        with open(file_path, mode="r") as f:
            data = json.load(f)
    except FileNotFoundError as E:
        with open(file_path, mode="w") as f:
            json.dump(items, f, indent=4)
            # save_games_list(games_list)
    else:
        data.update(items)
        with open(file_path, mode="w") as f:
            json.dump(data, f, indent=4)


def save_bot_setting(settings):
    save_to_file(settings, 'settings.json')


def save_games_list(games_list):
    save_to_file(games_list, 'games.json')


def main_func():
    # Read settings and games
    # if not read_settings():
    #     bot_settings['is_ready'] = False
    #     bot_settings['channel_id'] = None
    #     bot_settings['last_run'] = None
    #     save_bot_setting(bot_settings)
    # read_games()
    #
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='.', intents=intents)

    # @bot.command()
    # async def channel_info(ctx):
    #     channel_id = bot_settings.get('channel_id')
    #     if channel_id is None:
    #         msg = await ctx.send(f"There's nothing to show.")
    #         time.sleep(5)
    #         await msg.delete()
    #         return
    #     channel = bot.get_channel(channel_id)
    #     msg = await ctx.send(f"Channel name is: {channel.name}, id: {channel.id} ")
    #     time.sleep(5)
    #     await msg.delete()
    #
    # @bot.command()
    # async def bot_start(ctx):
    #     if ctx.author.bot or ctx.author.guild_permissions.administrator:
    #         bot_settings['is_ready'] = True
    #         save_bot_setting(bot_settings)
    #         # d_msg = await ctx.send('Bot has been started.')
    #         # await asyncio.sleep(1)
    #         # await d_msg.delete()
    #         while bot_settings['is_ready']:
    #             if bot_settings['is_ready']:
    #                 await get_games(ctx)
    #             await asyncio.sleep(TIME_DELAY)
    #
    # @bot.command()
    # async def show_sets(ctx):
    #     if ctx.author.bot or ctx.author.guild_permissions.administrator:
    #         msg = ""
    #         msg += "||"
    #         for key, setting in bot_settings.items():
    #             msg += f"**{key}**:{setting}\n"
    #         msg += "||"
    #         d_msg = await ctx.send(msg)
    #         await asyncio.sleep(10)
    #         await d_msg.delete()
    #
    # @bot.command()
    # async def bot_stop(ctx):
    #     if ctx.author.bot or ctx.author.guild_permissions.administrator:
    #         bot_settings['is_ready'] = False
    #         save_bot_setting(bot_settings)
    #         msg = await ctx.send('Bot has been stopped', ephemeral=True)
    #         time.sleep(1)
    #         await msg.delete()
    #
    # @bot.command()
    # async def get_games(ctx):
    #     channel_id = bot_settings.get('channel_id')
    #     if not ctx.author.bot and not ctx.author.guild_permissions.administrator:
    #         msg = await ctx.send('Sorry, but this command can be used only by bot..or administrator.', ephemeral=True)
    #         time.sleep(1)
    #         await msg.delete()
    #         return
    #     if channel_id is None:
    #         msg = await ctx.send('At first you should set up a channel. Use command "..set_channel #your_channel".',
    #                              ephemeral=True)
    #         bot_settings['is_ready'] = False
    #         save_bot_setting(bot_settings)
    #         time.sleep(1)
    #         await msg.delete()
    #         return
    #
    #     channel = bot.get_channel(int(channel_id))
    #     if channel is None:
    #         await ctx.send("Opps, I can't find the channel for sending data. "
    #                        "Please, set a channel again [!set_channel #channel].")
    #         return
    #     egs_obj.refresh()
    #     egs_free_games = egs_obj.free_games
    #     for game_id, game in egs_free_games.items():
    #         if game_id in games_from_file:
    #             # await ctx.send("Already exists")
    #             continue
    #         dt_var = game['expdate']
    #         msg = ""
    #         msg += f"\nЗайка🐰! Успей забрать до: **{dt_var}**\n"
    #         link_image = game['img']
    #         url_link = discord.Embed(title=game['title'],
    #                                  url=game['url'],
    #                                  description=game['description'],
    #                                  )
    #         url_link.set_image(url=link_image)
    #         games_from_file.append(game_id)
    #         await channel.send(msg, embed=url_link)
    #     # for game_id in games_from_file:
    #     #     egs_free_games.pop(game_id)
    #     if len(egs_free_games) > 0:
    #         save_games_list(egs_free_games)
    #     bot_settings['last_run'] = datetime.date.today().strftime("%d/%m/%Y")
    #     save_bot_setting(bot_settings)
    #
    # @bot.command()
    # async def set_channel(ctx):
    #     channel_id = bot_settings.get('channel_id')
    #     if not ctx.author.guild_permissions.administrator:
    #         await ctx.send("Opps, you have no rights here, mate.")
    #         return
    #     if ctx.message.channel_mentions.__len__() == 0:
    #         await ctx.send("At least one channel should be mentioned.")
    #         return
    #     # get the only first mentioned channel.
    #     channel = ctx.message.channel_mentions[0]
    #     bot_settings['channel_id'] = channel.id
    #     bot_settings['is_ready'] = True
    #     msg = await ctx.send(f"Channel **{channel.name}** has been set.")
    #     time.sleep(5)
    #     await msg.delete()
    #     save_bot_setting(bot_settings)
    #
    # @bot.command()
    # async def set_day_refresh(ctx):
    #     if not ctx.author.guild_permissions.administrator:
    #         await ctx.send("Opps, you have no rights here, mate.")
    #         return
    #     if ctx.message.channel_mentions.__len__() == 0:
    #         await ctx.send("At least one channel should be mentioned.")
    #         return
    #     # get the only first mentioned channel.
    #     day_refresh = ctx.message
    #     bot_settings['day_refresh'] = day_refresh
    #     msg = await ctx.send(f"Update time is set to **{day_refresh}** days.")
    #     time.sleep(5)
    #     await msg.delete()
    #     save_bot_setting(bot_settings)

    @bot.command()
    async def say_hello(ctx):
        await ctx.send("Opps, you have no rights here, mate.")

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user.name}({bot.user.id})")
        # is_ready = bot_settings.get('is_ready')
        # if is_ready is not None and is_ready:
        #     channel_id = bot_settings['channel_id']
        #     d_msg = await bot.get_channel(int(channel_id)).send('Running...')
        #     ctx = discord.ext.commands.context.Context(message=d_msg, bot=None, view=None)
        #     await asyncio.sleep(1)
        #     await d_msg.delete()
        #     await bot_start(ctx)

    bot.run(token=config.BUNNYBYTE_TOKEN)


if __name__ == "__main__":
    main_func()
