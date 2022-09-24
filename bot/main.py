import time
import datetime
from typing import List, Dict
import config
import discord
from discord import ButtonStyle, TextStyle
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import TextInput, Select, Button, View
import json
import asyncio
from yt_parser import YTParser
from egs_parser import EGSGamesParser, EGSGame
import mysql

TIME_DELAY = 60 * 60 * 12
SERVER_TASKS = dict()


# bot_settings = dict()
# games_from_file = []
# egs_obj = EGSGamesParser()


def is_user_admin(ctx: commands.Context):
    return ctx.author.guild_permissions.administrator


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

    # @bot
    # async def test_input(interaction: discord.Interaction):
    #     await interaction.response.send_message('Hi')
    @bot.command()
    async def l_start(ctx: commands.Context):
        server = ctx.guild
        task_to_run: tasks.Loop | None = SERVER_TASKS.get(server.id)

        try:
            if task_to_run is None:
                new_task = SERVER_TASKS[server.id] = tasks.loop(minutes=1)(first_loop)
                task_to_run = new_task
            if task_to_run.is_running():
                print(f"Loop task is already running on {server.name}")
            else:
                task_to_run.start(ctx)
                print(f"The loop is alive on {server.name}")
        except TypeError as e:
            print(f"Opps! {e}")

    @bot.command()
    async def l_stop(ctx: commands.Context):
        server = ctx.guild
        task_to_run: tasks.Loop | None = SERVER_TASKS.get(server.id)
        if task_to_run is None:
            print(f"Nothing to stop on {server.name}")
            return
        task_to_run.cancel()
        print(f"The loop is shut down on {server.name}")

    async def first_loop(ctx: commands.Context):
        await ctx.send(f'Hi, looser! **{ctx.author.name}** from **{ctx.guild.name}** server')

    def yt_video_save_to_dbase(server: commands.Context, yt_video=None):
        if yt_video is None:
            print("There's no a video object")
            return

        try:
            MYSQL = mysql.MYSQL()
            MYSQL.get_data(f"SELECT * FROM yt_videos")
            db_videos = MYSQL.data
            if yt_video in db_videos:
                print("The video is already on db.")
                return
            MYSQL.execute(
                user_query="INSERT INTO yt_videos "
                           "(`video_id`, `title`, `author`, `publish_date`, `thumbnail_url`, `watch_url`) "
                           "VALUES (%s, %s, %s, %s, %s, %s)",
                values=(yt_video.video_id, yt_video.title, yt_video.author,
                        yt_video.publish_date, yt_video.thumbnail_url, yt_video.watch_url)
            )
            inserted_video_id = MYSQL.cursor.lastrowid
            MYSQL.commit(True)
            print(f"YT-video has been saved.")
        except Exception as e:
            print(f"Error: [{e}]")

    @bot.command(name='yt_last_video', aliases=['yt-lvideo'])
    async def yt_last_video(ctx):
        yt_channel = YTParser()
        yt_channel.get_last_video()
        video_info, emb, view_ = yt_channel.get_discord_video_card(yt_channel.current_video, True)
        print(f"Fetching video info: {video_info['title']}")
        await ctx.send(embed=emb, view=view_)
        yt_video_save_to_dbase(ctx, yt_channel.current_video)
        print(f"Got video info: {video_info['title']}")

    def egs_games_save_to_dbase(server: commands.Context, games_list: List[EGSGame]):
        if not games_list:
            print("Games list is empty.")
            return

        try:
            MYSQL = mysql.MYSQL()
            MYSQL.get_data(f"SELECT * FROM egs_games")
            db_games = MYSQL.data
            for g in games_list:
                if g in db_games:
                    continue
                MYSQL.execute(
                    user_query="INSERT INTO egs_games "
                               "(`game_id`, `title`, `description`, `url`, `expdate`, `cover_url`) "
                               "VALUES (%s, %s, %s, %s, %s, %s)",
                    values=(g.id, g.title, g.description, g.url, g.exp_date, g.thumbnail)
                )
            MYSQL.commit(True)
            print(f"Games list has been saved.")
        except Exception as e:
            print(f"Error: [{e}]")

    @bot.command(name='get_games', aliases=['epic'])
    async def get_games(ctx: commands.Context):
        egs = EGSGamesParser()
        for egs_game in egs.free_games:
            game_info, emb, view_, file_ = egs_game.get_discord_game_card()
            print(f"Fetching game info: {game_info['title']}")
            await ctx.send(embed=emb, view=view_, file=file_)
            print(f"Got game info: {game_info['title']}")
        egs_games_save_to_dbase(ctx, egs.free_games)

    @bot.command(name="server_info", aliases=['server-info'])
    async def server_info(ctx: commands.Context):
        if is_user_admin(ctx):
            server = ctx.guild
            try:
                MYSQL = mysql.MYSQL()
                MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
                registration = "UN-REGISTERED" if MYSQL.empty else "REGISTERED"
                msg = f"Server info:\n" \
                      f"Name: [**{ctx.guild.name}**]\n" \
                      f"ID: [**{ctx.guild.id}**]\n" \
                      f"Status: [**{registration}**]"
                MYSQL.close()
                await ctx.send(msg)
            except Exception as e:
                await ctx.send(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.command(name="server_signup", aliases=['server-register'])
    async def server_signup(ctx: commands.Context):
        if is_user_admin(ctx):
            server = ctx.guild
            MYSQL = mysql.MYSQL()
            try:
                MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
                if not MYSQL.empty:
                    await ctx.send(f"You're already here [**{server.name}**]:[**{server.id}**]")
                    return
                # Making a registration
                print(f"Creating server row for [**{server.name}**]:[**{server.id}**]...")
                MYSQL.execute(f"INSERT INTO servers (`id`, `name`) VALUES ('{server.id}', '{server.name}');")
                await asyncio.sleep(2)
                print(f"Creating settings for [**{server.name}**]:[**{server.id}**]...")
                MYSQL.get_data(f"SELECT * FROM `settings`")
                features = MYSQL.data
                # user_query = f"INSERT INTO servers (`id`, `name`) VALUES ('{server.id}', '{server.name}');"
                user_query = f"INSERT INTO srv_config (`server_id`, `setting_id`, `value`) VALUES "
                for feature in features:
                    user_query += f"('{server.id}', '{feature['id']}', '')"
                    user_query += ';' if feature == features[-1] else ','
                MYSQL.execute(user_query)
                await asyncio.sleep(2)
                MYSQL.commit(True)
                await ctx.send(f"Your Server [**{server.name}**]:[**{server.id}**] has been registered. Congrats!.")
            except Exception as e:
                await ctx.send(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.command(name="server_delete", aliases=['server-delete'])
    async def server_delete(ctx: commands.Context):
        if is_user_admin(ctx):
            server = ctx.guild
            MYSQL = mysql.MYSQL()
            try:
                MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
                if MYSQL.empty:
                    await ctx.send(
                        f"Your Server [**{server.name}**]:[**{server.id}**] hasn't been registered. Aborted.")
                    return
                MYSQL.execute(f"DELETE FROM servers WHERE `id`='{server.id}'")
                MYSQL.commit(True)
                await ctx.send(f"Your Server [**{server.name}**]:[**{server.id}**] has been deleted.")
            except Exception as e:
                await ctx.send(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.command(name="test_input", aliases=["test-input"])
    async def test_input(ctx: commands.Context):
        if is_user_admin(ctx):
            server = ctx.guild
            setts = dict()
            for c in ['channel', 'is_ready', 'last_run']:
                try:
                    tx_input = TextInput(label="channel", style=TextStyle.short)
                    view_ = View()
                    view_.add_item(tx_input)
                    msg = await view_.wait()
                    # await ctx.send(f"Please, InputText[{c}]", view=view_)
                    # view_.remove_item(tx_input)
                    ##  def check(m):
                # return m.author == ctx.author and m.channel == ctx.channel
                #  msg = await bot.wait_for('message', check=check)

                except Exception as e:
                    print(f"Error: {e}")

    @bot.event
    async def on_ready():
        await bot.wait_until_ready()
        print(f"Logged in as {bot.user.name}({bot.user.id})")
        for server in bot.guilds:
            # Check Discord Server
            # MYSQL_C.connection.connect()
            # MYSQL_C = mysql.MYSQL()
            # MYSQL_C.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
            # if MYSQL_C.empty:
            #     # Create SERVER row
            #     MYSQL_C.execute(f"INSERT INTO servers (`id`, `name`) VALUES ('{server.id}', '{server.name}');")
            #
            #     MYSQL_C.get_data(f"SELECT * FROM `settings`")
            #     features = MYSQL_C.data
            #     # user_query = f"INSERT INTO servers (`id`, `name`) VALUES ('{server.id}', '{server.name}');"
            #     user_query = f"INSERT INTO srv_config (`server_id`, `setting_id`, `value`) VALUES "
            #     for feature in features:
            #         user_query += f"('{server.id}', '{feature['id']}', '')"
            #         user_query += ';' if feature == features[-1] else ','
            #     MYSQL_C.execute(user_query)
            # # MYSQL_C.connection.close()
            #     print(f"Setting for [{server.name}]:[{server.id}] have been made.")
            # else:
            #     MYSQL_C.execute(f"DELETE FROM servers WHERE `id`='{server.id}'")
            #     print(f"Server:[{server.name}]:[{server.id}] is already exist")
            print(f"Server:[{server.name}]:[{server.id}]")
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
