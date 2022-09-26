from typing import List, Dict, Optional, Literal
from enum import Enum, Flag
import config
import json
import asyncio
import mysql
# region DISCORD IMPORTS
import discord
import discord.ui as ui
from discord import (
    app_commands,
    ButtonStyle, TextStyle, Interaction, SelectMenu, SelectOption,
)
from discord.ext import (
    commands, tasks,
)
# endregion
# region MY_FILES
from yt_parser import YTParser, BUNNY_CHANNEL_ID
from egs_parser import EGSGamesParser, EGSGame

# endregion

TIME_DELAY = 60 * 60 * 12
SERVER_TASKS = dict()
BOT_LOCAL_CONFIG = dict()


# region HELPERS CLASSES
class SettingSwitcher(Enum):
    Enable = 1
    Disable = 0


class ServerStatus(Flag):
    REGISTERED = True
    UNREGISTERED = False


# endregion
def is_user_admin(ctx: commands.Context | Interaction):
    return ctx.author.guild_permissions.administrator


def yt_video_save_to_dbase(yt_video=None):
    if yt_video is None:
        print("There's no a video object")
        return

    try:
        MYSQL = mysql.MYSQL()
        MYSQL.get_data(f"SELECT * FROM yt_videos")
        db_videos = [x['video_id'] for x in MYSQL.data]
        if yt_video.video_id in db_videos:
            print(f"The video {yt_video.title} is already on db.")
            return
        MYSQL.execute(
            user_query="INSERT INTO yt_videos "
                       "(`video_id`, `title`, `author`, `publish_date`, `thumbnail_url`, `watch_url`) "
                       "VALUES (%s, %s, %s, %s, %s, %s)",
            values=(yt_video.video_id, yt_video.title, yt_video.author,
                    yt_video.publish_date, yt_video.thumbnail_url, yt_video.watch_url)
        )
        # inserted_video_id = MYSQL.cursor.lastrowid
        MYSQL.commit(True)
        print(f"YT-video has been saved.")
    except Exception as e:
        print(f"Error: [{e}]")


def egs_games_save_to_dbase(server: commands.Context, games_list: List[EGSGame]):
    if not games_list:
        print("Games list is empty.")
        return

    try:
        MYSQL = mysql.MYSQL()
        MYSQL.get_data(f"SELECT * FROM egs_games")
        db_games = [x['game_id'] for x in MYSQL.data]
        for g in games_list:
            if g.id in db_games:
                print(f"The video {g.title} is already on db.")
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


def server_get_status(server_id: int | str = None):
    try:
        MYSQL = mysql.MYSQL()
        MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`=%s",
                       values=server_id
                       )
        MYSQL.close()
        return ServerStatus(not MYSQL.empty)
    except Exception as e:
        print(e)


def server_get_bot_channel(server_id: int | str = None):
    try:
        MYSQL = mysql.MYSQL()
        MYSQL.get_data(f"SELECT * FROM `bot_config` WHERE `server_id`=%s",
                       values=server_id
                       )
        MYSQL.close()
        if MYSQL.empty:
            return None
        else:
            return int(MYSQL.data[0]['service_channel'])
    except Exception as e:
        print(e)


# region LOCAL_BOT
def local_flush_server_settings(server_id: int | str = None):
    BOT_LOCAL_CONFIG[server_id]['bot_channel'] = None
    BOT_LOCAL_CONFIG[server_id]['tasks'] = list()
    BOT_LOCAL_CONFIG[server_id]['status'] = ServerStatus.UNREGISTERED
    BOT_LOCAL_CONFIG[server_id]['tasks'] = {
        'ytb': None,
        'egs': None,
    }


def local_get_bot_channel(server_id: int | str = None):
    return BOT_LOCAL_CONFIG[server_id].get('bot_channel')


def local_get_tasks(server_id: int | str = None):
    return BOT_LOCAL_CONFIG[server_id].get('tasks')


def local_get_status(server_id: int | str = None):
    return BOT_LOCAL_CONFIG[server_id].get('status')


# endregion

def discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='.', intents=intents)
    bot.remove_command('help')

    async def delete_discord_message(msg: discord.Message | discord.Interaction, delete_after_sec: int = 3):
        await asyncio.sleep(delete_after_sec)
        if isinstance(msg, discord.Message):
            await msg.delete()
        elif isinstance(msg, discord.Interaction):
            await msg.delete_original_response()

    # region Interactions
    @bot.tree.command(name="test1")
    @app_commands.describe(c_status='Enable/Disable Command')
    async def joined(interaction: discord.Interaction, c_status: SettingSwitcher, b: bool = None):
        """Says when a member joined."""
        # If no member is explicitly provided then we use the command user here
        # The format_dt function formats the date time into a human readable representation in the official client
        await interaction.response.send_message(f'You chose option: {c_status}. {b} Are you happy now? ')

    # A Context Menu command is an app command that can be run on a member or on a message by
    # accessing a menu within the client, usually via right clicking.
    # It always takes an interaction as its first parameter and a Member or Message as its second parameter.

    # This context menu command only works on members
    # @bot.tree.context_menu(name='Show Join Date')
    # async def show_join_date(interaction: discord.Interaction, member: discord.Member):
    #     # The format_dt function formats the date time into a human readable representation in the official client
    #     await interaction.response.send_message(f'{member} joined at {discord.utils.format_dt(member.joined_at)}')

    # region SLASH_COMMANDS

    @bot.tree.command(name="help")
    @commands.has_permissions(administrator=True)
    async def custom_help(ctx: discord.Interaction):
        # if not is_user_admin(ctx):
        #     return
        channel_to_response = bot.get_channel(ctx.channel_id)
        emb = discord.Embed(title="BunnyByte FAQ", description="There are some commands that I can do for you.")
        emb.set_footer(text="After 1 minute I'm leaving|Я скроюсь через миниту :)")
        emb.add_field(name="-----SERVER-----",
                      value="\n"
                            "[**.server-register <#service-channel>**]\n"
                            "- Зарегистрировать сервер для работы бота. Нужно создать приватный канал и дать доступ боту.\n"
                            "- Пример: .server-register #приватный-канал\n"
                            f"{'--' * 20}\n"
                            "- Register the bot. You need to create a private channel and give permission to bot.\n"
                            "- Example: .server-register #private-channel\n"
                            "\n"
                            "[**.server-delete**]\n"
                            "- Прекратить работу бота. Все настройки будут удалены!!! Чтобы запустить бота снова, нужно пройти регистрацию.\n"
                            "--------------------------------------------\n"
                            "- Shut down the bot. All bot setting will be deleted!!! You need to register server if you wanna start it again.\n"
                            "\n"
                            "[**.server-csc <#service-channel>**]\n"
                            "- Сменить канал для вывода сервисных сообщений.\n"
                            "--------------------------------------------\n"
                            "- Change service channel for receiving service bots notification.\n"
                            "\n"
                            "[**.server-info**]\n"
                            "- Показать информацию о сервере.\n"
                            "--------------------------------------------\n"
                            "- Show up server info.\n"
                      ,
                      inline=False)
        emb.set_thumbnail(url=bot.user.avatar)
        await ctx.response.send_message(embed=emb)
        await delete_discord_message(ctx, 30)

    # LOOPS
    @bot.tree.command(name="bb_ytube",
                      description="Enable YouTube Notificator.")
    @app_commands.describe(yt_channel_url="YouTube channel ID", yt_minutes_delay="Check new video every X minutes.")
    @commands.has_permissions(administrator=True)
    async def ytube_service_start(ctx: Interaction, yt_channel_url: str, yt_minutes_delay: int = 2):
        try:
            await ctx.response.defer(ephemeral=False)
            server = ctx.guild
            if local_get_status(server.id) == ServerStatus.UNREGISTERED:
                print(f'Server **{server.name}** Unregistered')
                await ctx.edit_original_response(content=f'Server **{server.name}** Unregistered')
                await delete_discord_message(ctx, 5)
                return

            task_to_run: tasks.Loop | None = BOT_LOCAL_CONFIG[server.id]['tasks'].get('ytb')

            if task_to_run is None:
                new_task = BOT_LOCAL_CONFIG[server.id]['tasks']['ytb'] = tasks.loop(minutes=yt_minutes_delay)(
                    yt_last_video)
                task_to_run = new_task
            if task_to_run.is_running():
                await ctx.edit_original_response(content=f"Loop task is already running on {server.name}")
                await delete_discord_message(ctx, 5)
                print(f"Loop task is already running on {server.name}")
            else:
                await ctx.edit_original_response(content=f"The loop is alive on {server.name}")
                await delete_discord_message(ctx, 5)
                task_to_run.start(ctx, yt_channel_url)
                print(f"The loop is alive on {server.name}")
        except Exception as e:
            await ctx.edit_original_response(
                content=f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.tree.command(name="bb_ytube_stop",
                      description="Disable YouTube Notificator.")
    # @app_commands.describe(yt_channel_url="YouTube channel ID", yt_minutes_delay="Check new video every X minutes.")
    @commands.has_permissions(administrator=True)
    async def ytube_service_start(ctx: Interaction):
        try:
            await ctx.response.defer(ephemeral=False)
            server = ctx.guild
            if local_get_status(server.id) == ServerStatus.UNREGISTERED:
                print(f'Server **{server.name}** Unregistered')
                await ctx.edit_original_response(content=f'Server **{server.name}** Unregistered')
                await delete_discord_message(ctx, 5)
                return

            task_to_run: tasks.Loop | None = BOT_LOCAL_CONFIG[server.id]['tasks'].get('ytb')

            if task_to_run is None:
                print(f"Nothing to stop on {server.name}")
                await ctx.edit_original_response(content=f"Nothing to stop on {server.name}")
                await delete_discord_message(ctx, 5)
                return
            task_to_run.cancel()
            print(f"The loop is shut down on {server.name}")
            await ctx.edit_original_response(content=f"The loop is shut down on {server.name}")
            await delete_discord_message(ctx, 5)
        except Exception as e:
            await ctx.edit_original_response(
                content=f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

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

    async def yt_last_video(ctx: discord.Interaction,
                            yt_channel_url: str = BUNNY_CHANNEL_ID,
                            enable_description: int = 0):
        try:
            yt_channel = YTParser(yt_channel_url)
            yt_channel.get_last_video()
            video_info, emb, view_ = yt_channel.get_discord_video_card(yt_channel.current_video,
                                                                       bool(enable_description))
            print(f"Fetching video info: {video_info['title']}")
            bot_channel = bot.get_channel(ctx.channel_id)
            await bot_channel.send(embed=emb, view=view_)
            yt_video_save_to_dbase(yt_channel.current_video)
            print(f"Got video info: {video_info['title']}")
        except Exception as e:
            print(e)

    @bot.command(name='get_games', aliases=['epic'])
    async def get_games(ctx: commands.Context):
        egs = EGSGamesParser()
        for egs_game in egs.free_games:
            game_info, emb, view_, file_ = egs_game.get_discord_game_card()
            print(f"Fetching game info: {game_info['title']}")
            await ctx.send(embed=emb, view=view_, file=file_)
            print(f"Got game info: {game_info['title']}")
        egs_games_save_to_dbase(ctx, egs.free_games)

    # region SC_SERVER
    @bot.tree.command(name="bb_server_info",
                      description="Show SERVER info.")
    @commands.has_permissions(administrator=True)
    async def server_info(ctx: Interaction):
        # if is_user_admin(ctx):
        server = ctx.guild
        try:
            bot_channel = local_get_bot_channel(server.id)
            if bot_channel is not None:
                bot_channel = bot.get_channel(bot_channel).name
            emb = discord.Embed(
                title="SERVER-INFO",
                description=f"Name: [**{ctx.guild.name}**]\n"
                            f"ID: [**{ctx.guild.id}**]\n"
                            f"Status: [**{BOT_LOCAL_CONFIG[server.id]['status'].name}**]\n"
                            f"Service channel: [**{bot_channel}**]\n"
            )
            await ctx.response.send_message(embed=emb)
            await delete_discord_message(ctx, 10)
        except Exception as e:
            await ctx.response.send_message(
                f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.tree.command(name="bb_server_change_channel",
                      description="Change service (private) channel for notifications from bot.")
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @commands.has_permissions(administrator=True)
    async def server_change_channel(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        server = ctx.guild
        await ctx.response.defer(ephemeral=False)
        if bot_channel is None:
            await ctx.edit_original_response(content="Bunny, I need a channel. Stay focused!")
            await delete_discord_message(ctx, 10)
            return

        try:
            server_status = local_get_status(server.id)
            if server_status == ServerStatus.UNREGISTERED:
                await ctx.edit_original_response(
                    content="Hey, Bunny! You need to be registered before changing something :)")
                await delete_discord_message(ctx, 5)
                return
            if bot_channel.id == local_get_bot_channel(server.id):
                await ctx.edit_original_response(
                    content="Hey, Bunny! You are giving me the same channel. Are you alright? :)")
                await delete_discord_message(ctx, 5)
                return
            MYSQL = mysql.MYSQL()
            MYSQL.execute("UPDATE bot_config SET `service_channel` = %s WHERE `server_id` = %s",
                          values=(bot_channel.id, server.id))
            MYSQL.commit()
            BOT_LOCAL_CONFIG[server.id]['bot_channel'] = bot_channel.id
            await ctx.edit_original_response(
                content=f"It's done. **{bot_channel.name}** now is your new service channel.")
            await delete_discord_message(ctx, 10)
        except Exception as e:
            await ctx.edit_original_response(
                content=f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.tree.command(name="bb_server_signup",
                      description="Register the bot. You need to create a private channel (mute) & give me permission.")
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @commands.has_permissions(administrator=True)
    async def server_signup(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        # if is_user_admin(ctx):
        server = ctx.guild
        await ctx.response.defer(ephemeral=False)
        if bot_channel is None:
            await ctx.edit_original_response(content="Bunny, I need a channel. Stay focused!")
            await delete_discord_message(ctx, 10)
            return
        MYSQL = mysql.MYSQL()
        try:
            # MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
            # if not MYSQL.empty:
            if BOT_LOCAL_CONFIG[server.id]['status'] == ServerStatus.REGISTERED:
                await ctx.edit_original_response(content=f"You're already here [**{server.name}**]:[**{server.id}**]")
                await delete_discord_message(ctx, 10)
                return
            # Making a registration
            print(f"Creating server row for [**{server.name}**]:[**{server.id}**]...")
            MYSQL.execute(
                user_query=f"INSERT INTO servers (`id`, `name`) VALUES (%s, %s)",
                values=(server.id, server.name)
            )
            await asyncio.sleep(2)
            print(f"Creating settings for [**{server.name}**]:[**{server.id}**]...")
            MYSQL.get_data(f"SELECT * FROM `settings`")
            features = MYSQL.data
            # user_query = f"INSERT INTO servers (`id`, `name`) VALUES ('{server.id}', '{server.name}');"
            user_query = f"INSERT INTO srv_config (`server_id`, `setting_id`, `value`) VALUES (%s, %s, %s) "
            value_list = []
            for feature in features:
                value = None
                if feature['type'] == 'bool':
                    value = False
                value_list.append((server.id, feature['id'], value))
                # user_query += f"('{server.id}', '{feature['id']}', {value})"
                # user_query += ';' if feature == features[-1] else ','
            MYSQL.executemany(user_query, value_list)
            MYSQL.execute('INSERT INTO bot_config (service_channel, server_id) VALUES (%s, %s)',
                          values=(bot_channel.id, server.id))
            await asyncio.sleep(2)
            MYSQL.commit(True)

            BOT_LOCAL_CONFIG[server.id]['status'] = ServerStatus.REGISTERED
            BOT_LOCAL_CONFIG[server.id]['bot_channel'] = bot_channel.id

            await ctx.edit_original_response(
                content=f"Your Server [**{server.name}**]:[**{server.id}**] has been registered. Congrats!.")
            await delete_discord_message(ctx, 10)
        except Exception as e:
            await ctx.edit_original_response(
                content=f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.tree.command(name="bb_server_delete",
                      description="Delete server from bot' database. **All your setting will be lost.**")
    @commands.has_permissions(administrator=True)
    async def server_delete(ctx: Interaction):
        # if is_user_admin(ctx):
        server = ctx.guild
        await ctx.response.defer(ephemeral=False)
        MYSQL = mysql.MYSQL()
        try:
            SRV_STATUS = BOT_LOCAL_CONFIG[server.id]['status']
            # MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
            # if MYSQL.empty:
            if SRV_STATUS == ServerStatus.UNREGISTERED:
                await ctx.edit_original_response(
                    content=f"Your Server [**{server.name}**]:[**{server.id}**] hasn't been registered. Aborted.")
                await delete_discord_message(ctx)
                return
            MYSQL.execute(f"DELETE FROM servers WHERE `id`='{server.id}'")
            MYSQL.commit(True)
            local_flush_server_settings(server.id)
            await ctx.edit_original_response(
                content=f"Your Server [**{server.name}**]:[**{server.id}**] has been deleted.")
            await delete_discord_message(ctx, 10)
        except Exception as e:
            await ctx.response.edit_original_response(
                content=f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    # endregion

    @bot.command(name="bb_help", aliases=["help"])
    @commands.has_permissions(administrator=True)
    async def custom_help(ctx: commands.Context):
        # if not is_user_admin(ctx):
        #     return
        emb = discord.Embed(title="BunnyByte FAQ", description="There are some commands that I can do for you.")
        emb.set_footer(text="After 1 minute I'm leaving|Я скроюсь через миниту :)")
        emb.add_field(name="-----SERVER-----",
                      value="\n"
                            "[**.server-register <#service-channel>**]\n"
                            "- Зарегистрировать сервер для работы бота. Нужно создать приватный канал и дать доступ боту.\n"
                            "- Пример: .server-register #приватный-канал\n"
                            f"{'--' * 20}\n"
                            "- Register the bot. You need to create a private channel and give permission to bot.\n"
                            "- Example: .server-register #private-channel\n"
                            "\n"
                            "[**.server-delete**]\n"
                            "- Прекратить работу бота. Все настройки будут удалены!!! Чтобы запустить бота снова, нужно пройти регистрацию.\n"
                            "--------------------------------------------\n"
                            "- Shut down the bot. All bot setting will be deleted!!! You need to register server if you wanna start it again.\n"
                            "\n"
                            "[**.server-csc <#service-channel>**]\n"
                            "- Сменить канал для вывода сервисных сообщений.\n"
                            "--------------------------------------------\n"
                            "- Change service channel for receiving service bots notification.\n"
                            "\n"
                            "[**.server-info**]\n"
                            "- Показать информацию о сервере.\n"
                            "--------------------------------------------\n"
                            "- Show up server info.\n"
                      ,
                      inline=False)
        emb.set_thumbnail(url=ctx.bot.user.avatar)
        await ctx.send(embed=emb, delete_after=60)

    async def bot_say_hi_to_registered_server(server_id: int | str):
        if bot.is_ready() and local_get_status(server_id) == ServerStatus.REGISTERED:
            try:
                bot_channel = bot.get_channel(BOT_LOCAL_CONFIG[server_id]['bot_channel'])
                await bot_channel.send(content=f"Hi! **{BOT_LOCAL_CONFIG[server_id]['name']}** SERVER. I'm online!!!")
            except discord.errors.Forbidden as e:
                print(f"I have a service channel on {server_id}, but I have no rights. Just skipping this carrotbutt.")

    # endregion
    @bot.event
    async def on_ready():
        await bot.wait_until_ready()
        await bot.tree.sync()
        print(f"Logged in as {bot.user.name}({bot.user.id})")
        for server in bot.guilds:
            await bot.tree.sync(guild=server)
            BOT_LOCAL_CONFIG[server.id] = {
                'id': server.id,
                'name': server.name,
                'bot_channel': server_get_bot_channel(server.id),
                'status': server_get_status(server.id),
                'tasks': {
                    'ytb': None,
                    'egs': None,
                },
            }
            await bot_say_hi_to_registered_server(server.id)
            print(f"Server:[{server.name}]:[{server.id}]")

    bot.run(token=config.BUNNYBYTE_TOKEN)


if __name__ == "__main__":
    discord_bot()
