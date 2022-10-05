import asyncio
import config
import db_requests
import discord
import mysql
import random
import logging
import helpers
from datetime import datetime
from functools import wraps
from typing import List

# region DISCORD IMPORTS
from discord import (
    app_commands,
)
from discord.ext import (
    commands, tasks,
)
from egs_parser import EGSGamesParser, EGSGame
from enums import *
from spinwheel_games import *
# endregion
# region MY_FILES
from yt_parser import YTParser, YoutubeStreamStatus

# endregion

BOT_CONFIG = {}
EPHEMERAL_ATTRIBUTE_NAME = 'defer'
DEFER_YES = {EPHEMERAL_ATTRIBUTE_NAME: True}
DEFER_NO = {EPHEMERAL_ATTRIBUTE_NAME: False}
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# region HELPERS CLASSES

# endregion
def simple_try_except_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.info(f"S - Something went wrong [{e}]. Try again or send me a message and we will do something.")

    return wrapper


def discord_async_try_except_decorator(func):
    """
    To be honest, I dunno know what I'm doing. It works (I hope) , I don't touch.
    """

    @wraps(func)
    async def wrapper(interaction, *args, **kwargs):
        is_discord_interaction = isinstance(interaction, discord.Interaction)
        try:
            if is_discord_interaction:
                command_extras = {'extras': None} if interaction.command is None else interaction.command.extras
                defer = kwargs.get('defer', command_extras.get(EPHEMERAL_ATTRIBUTE_NAME, False))
                await interaction.response.defer(ephemeral=defer)
            return await func(interaction, *args, **kwargs)
        except Exception as e:
            if is_discord_interaction:
                await interaction.edit_original_response(
                    content=f"Something went wrong [{e}]. Try again or send me a message and we will do something.",
                    view=None)
            logger.info(f"NS - Something went wrong [{e}]. Try again or send me a message and we will do something.")

    return wrapper


@simple_try_except_decorator
def yt_video_save_to_dbase(server, yt_video=None):
    if yt_video is None:
        print("There's no a video object")
        return

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
    MYSQL.execute(
        user_query="INSERT INTO srv_matching "
                   "(`id`, `server_id`) "
                   "VALUES (%s, %s)",
        values=(yt_video.video_id, server.id)
    )
    BOT_CONFIG[server.id]['match_list'].append(yt_video.video_id)
    # inserted_video_id = MYSQL.cursor.lastrowid
    MYSQL.commit(True)
    print(f"YT-video has been saved.")


@simple_try_except_decorator
def egs_games_save_to_dbase(server, games_list: List[EGSGame]):
    if not games_list:
        print("Games list is empty.")
        return

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
        MYSQL.execute(
            user_query="INSERT INTO srv_matching "
                       "(`id`, `server_id`) "
                       "VALUES (%s, %s)",
            values=(g.id, server.id)
        )
        BOT_CONFIG[server.id]['match_list'].append(g.id)
    MYSQL.commit(True)
    print(f"Games list has been saved.")


# region LOCAL_BOT
def local_flush_server_settings(server_id: int | str = None):
    BOT_CONFIG[server_id]['bot_channel'] = None
    BOT_CONFIG[server_id]['status'] = ServerStatus.UNREGISTERED
    BOT_CONFIG[server_id]['features'] = {
        'egs': {'settings': None, 'task': None, },
        'ytube': {'settings': None, 'task': None, }
    }
    del BOT_CONFIG[server_id]['match_ytube']
    del BOT_CONFIG[server_id]['match_egs']


def local_get_bot_channel(server_id: int | str = None):
    return BOT_CONFIG[server_id].get('bot_channel')


def local_get_status(server_id: int | str = None):
    return BOT_CONFIG[server_id].get('status')


# endregion

def discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    bot = commands.Bot(command_prefix='.', intents=intents)
    bot.remove_command('help')

    commands_group_ytube = app_commands.Group(name="bb_ytube",
                                              description="Commands for interaction with YouTube-Notificator.",
                                              default_permissions=discord.Permissions(administrator=True))
    commands_group_egs = app_commands.Group(name="bb_egs",
                                            description="Commands for interaction with EGS-Notificator.",
                                            default_permissions=discord.Permissions(administrator=True))
    commands_group_spinwheel = app_commands.Group(name="bb_wheel",
                                                  description="Commands for interaction with Spin Wheel",
                                                  default_permissions=discord.Permissions(administrator=True))
    commands_group_server = app_commands.Group(name="bb_server",
                                               description="Commands for interaction with Server",
                                               default_permissions=discord.Permissions(administrator=True))
    commands_allowed_to_user = app_commands.Group(name="bb_user",
                                                  description="Commands allowed to User", default_permissions=None)

    async def discord_has_permission_to_send_messages(ctx: discord.Interaction, channel: discord.TextChannel):
        has_permission = channel.permissions_for(channel.guild.me).send_messages
        if not has_permission:
            await ctx.edit_original_response(
                content=f"I have no rights to send messages here. Channel [**{channel.name}**]")
        return has_permission

    async def discord_channel_is_available(ctx: discord.Interaction, channel_id: int) -> discord.TextChannel | None:
        channel_exist = bot.get_channel(channel_id)
        if channel_exist is None:
            await ctx.edit_original_response(content="Current Channel isn't available.")
        return channel_exist

    async def discord_delete_message(msg: discord.Message | discord.Interaction, delete_after_sec: int = 3):
        if msg.command.extras.get(EPHEMERAL_ATTRIBUTE_NAME) is False:
            await asyncio.sleep(delete_after_sec)
            if isinstance(msg, discord.Message):
                await msg.delete()
            elif isinstance(msg, discord.Interaction):
                await msg.delete_original_response()

    async def discord_is_server_registered(ctx: discord.Interaction, server: discord.Guild, context: str = None,
                                           delete_after: bool = True, delete_after_sec: int = 5) -> bool:
        status = local_get_status(server.id) is ServerStatus.UNREGISTERED
        if status:
            if context is None:
                context = f'Server **{server.name}** Unregistered'
            print(context)
            await ctx.edit_original_response(content=context)
            if delete_after and ctx.command.extras.get(EPHEMERAL_ATTRIBUTE_NAME) is not None:
                await discord_delete_message(ctx, delete_after_sec)
        return not status

    async def discord_is_owner(ctx: discord.Interaction | commands.Context, send_response: bool = True):
        permission = ctx.user.guild_permissions.administrator
        if not permission and send_response:
            if isinstance(ctx, discord.Interaction):
                await ctx.edit_original_response(content="🐰, у тебя лапки.")
            elif isinstance(ctx, commands.Context):
                await ctx.send("🐰, у тебя лапки.")
            await discord_delete_message(ctx, 10)
        return permission

    async def passed_checks_before_start_command(server: discord.Guild = None,
                                                 ctx: discord.Interaction = None,
                                                 channel: discord.TextChannel | str = None,
                                                 checks: List[ChecksBeforeStart] = None):
        if checks is None: checks = []

        if ChecksBeforeStart.OWNER in checks:
            if not await discord_is_owner(ctx): return False
        if ChecksBeforeStart.REGISTRATION in checks:
            if not await discord_is_server_registered(ctx, server): return False
        if ChecksBeforeStart.CHANNEL in checks:
            channel_id = channel.id if isinstance(channel, discord.TextChannel) else channel
            if await discord_channel_is_available(ctx, channel_id) is None: return False

        return True

    async def create_task_ytube(ctx, server: discord.Guild, check_hours: int, check_minutes: int,
                                show_description: SettingYesNo,
                                notification_time_before: int, yt_channel_url: str,
                                notification_channel: discord.TextChannel):

        task_to_run: tasks.Loop | None = BOT_CONFIG[server.id]['features']['ytube'].get('task')

        full_minutes = check_hours * 60 + check_minutes
        if task_to_run is None:
            new_task = BOT_CONFIG[server.id]['features']['ytube']['task'] = tasks.loop(minutes=full_minutes)(
                yt_last_video)
            task_to_run = new_task
        if task_to_run.is_running():
            await ctx.edit_original_response(content=f"YT-Notificator is already running on {server.name}")
            await discord_delete_message(ctx, 5)
            print(f"YT-Notificator is already running on {server.name}")
        else:
            await ctx.edit_original_response(content=f"YT-Notificator is alive on {server.name}")
            await discord_delete_message(ctx, 5)

            BOT_CONFIG[server.id]['features']['ytube']['settings']['enable'] = True
            BOT_CONFIG[server.id]['features']['ytube']['settings']['repeat'] = full_minutes
            BOT_CONFIG[server.id]['features']['ytube']['settings']['notification_time'] = notification_time_before
            BOT_CONFIG[server.id]['features']['ytube']['settings']['yt_channel'] = yt_channel_url
            BOT_CONFIG[server.id]['features']['ytube']['settings']['channel_id'] = notification_channel.id
            BOT_CONFIG[server.id]['features']['ytube']['settings']['show_description'] = bool(
                show_description.value)
            # yt_channel_url = YTParser(channel_id=yt_channel_url, create_channel_object=False)
            # bot_channel = bot.get_channel(ctx.channel_id)
            task_to_run.start(server, notification_channel, yt_channel_url, show_description.value)
            print(f"YT-Notificator is alive on {server.name}")

    async def stop_task_ytube(server: discord.Guild, ctx: discord.Interaction):
        task_to_run: tasks.Loop | None = BOT_CONFIG[server.id]['features']['ytube']['task']

        if task_to_run is None:
            print(f"Nothing to stop on {server.name}")
            await ctx.edit_original_response(content=f"Nothing to stop on {server.name}")
            await discord_delete_message(ctx, 5)
            return
        task_to_run.cancel()

        BOT_CONFIG[server.id]['features']['ytube']['task'] = None
        BOT_CONFIG[server.id]['features']['ytube']['settings']['enable'] = False
        # save to db
        print(f"The loop is shut down on {server.name}")
        await ctx.edit_original_response(content=f"The loop is shut down on {server.name}")
        await discord_delete_message(ctx, 5)

    async def create_task_egsgames(ctx: discord.Interaction, server: discord.Guild,
                                   check_hours: int, check_minutes: int,
                                   notification_channel: discord.TextChannel, egs_games: EGSGamesParser):
        task_to_run: tasks.Loop | None = BOT_CONFIG[server.id]['features']['egs'].get('task')

        full_minutes = check_hours * 60 + check_minutes
        if task_to_run is None:
            new_task = BOT_CONFIG[server.id]['features']['egs']['task'] = tasks.loop(minutes=full_minutes)(
                get_games)
            task_to_run = new_task
        if task_to_run.is_running():
            await ctx.edit_original_response(content=f"EGS-Notificator is already running on {server.name}")
            await discord_delete_message(ctx, 5)
            print(f"EGS-Notificator is already running on {server.name}")
        else:
            await ctx.edit_original_response(content=f"EGS-Notificator is alive on {server.name}")
            await discord_delete_message(ctx, 5)

            # bot_channel = bot.get_channel(ctx.channel_id)
            BOT_CONFIG[server.id]['features']['egs']['settings']['enable'] = True
            BOT_CONFIG[server.id]['features']['egs']['settings']['repeat'] = full_minutes
            BOT_CONFIG[server.id]['features']['egs']['settings']['channel_id'] = notification_channel.id

            task_to_run.start(server, notification_channel, egs_games)
            print(f"EGS-Notificator is alive on {server.name}")

    async def stop_task_egsgames(server: discord.Guild, ctx: discord.Interaction):
        task_to_run: tasks.Loop | None = BOT_CONFIG[server.id]['features']['egs']['task']

        if task_to_run is None:
            print(f"Nothing to stop on {server.name}")
            await ctx.edit_original_response(content=f"Nothing to stop on {server.name}")
            await discord_delete_message(ctx, 5)
            return
        task_to_run.cancel()

        BOT_CONFIG[server.id]['features']['egs']['task'] = None
        BOT_CONFIG[server.id]['features']['egs']['settings']['enable'] = False
        # save to db!!!
        print(f"EGS Notificator is shut down on {server.name}")
        await ctx.edit_original_response(content=f"EGS Notificator is shut down on {server.name}")
        await discord_delete_message(ctx, 5)

    # region Interactions
    # region SLASH_COMMANDS
    @bot.tree.command(name="help", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def custom_help(ctx: discord.Interaction):
        # await ctx.response.defer(ephemeral=False)
        emb = discord.Embed(title="BunnyByte FAQ", description="There are some commands that I can do for you.")
        emb.set_footer(text="After 1 minute I'm leaving|Я скроюсь через миниту :)")
        if not await discord_is_owner(ctx, send_response=False):
            emb.add_field(name="-----[USER]-----",
                          value="\n"
                                "[**.server-register <#service-channel>**]\n"
                                "- Зарегистрировать сервер для работы бота. Нужно создать приватный канал и дать доступ боту.\n"
                                "- Пример: .server-register #приватный-канал\n"
                                f"{'--' * 20}\n",
                          inline=False)
        else:
            emb.add_field(name="-----[SERVER]-----",
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
        await ctx.edit_original_response(embed=emb)
        await discord_delete_message(ctx, 30)

        # LOOPS
        # region PARSER_YOUTUBE

    async def yt_last_video(server, channel_for_notification: discord.TextChannel,
                            yt_channel_url: str, show_description: int = 0):
        yt_channel = await YTParser(yt_channel_url, False).get_last_livestream()
        if yt_channel.currentLiveStream is None:
            print(f"There's no stream. Channel:({yt_channel.author})")
            return

        yt_settings = BOT_CONFIG[server.id]['features']['ytube']['settings']
        notification_time = yt_settings['notification_time']
        stream_is_about_to_start = (yt_channel.upcomingDate - datetime.utcnow()) < notification_time

        current_video = yt_channel.currentVideo
        is_livestream = False
        if yt_channel.currentLiveStream is not None:
            current_video = yt_channel.currentLiveStream
            is_livestream = True
        print(f"Fetching video info: {current_video.title}")
        video_info, emb, view_ = yt_channel.get_discord_video_card(current_video, bool(show_description),
                                                                   is_livestream)
        await channel_for_notification.send(embed=emb, view=view_)
        yt_video_save_to_dbase(server, current_video)
        print(f"Got video info: {current_video.title}")

    @commands_group_ytube.command(name="start", description="Enable YouTube Streams Notificator.", extras=DEFER_YES)
    @app_commands.describe(yt_channel_url="YouTube Channel URL",
                           notification_channel="Discord channel for sending notifications.",
                           show_description="Show full video description in template. Default = Disable",
                           notification_time_before="Send upcoming stream notifications before X-time start. Default = 3",
                           check_hours="Check new stream every X hours. Default = 0",
                           check_minutes="Check new stream every X minutes. Default = 59 | Min = 5")
    @discord_async_try_except_decorator
    async def ytube_service_start(ctx: discord.Interaction,
                                  notification_channel: discord.TextChannel,
                                  yt_channel_url: str,
                                  show_description: SettingYesNo = SettingYesNo.No,
                                  notification_time_before: app_commands.Range[int, 3] = 3,
                                  check_hours: app_commands.Range[int, 0] = 0,
                                  check_minutes: app_commands.Range[int, 5] = 59):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return
        await create_task_ytube(ctx, server, check_hours, check_minutes, show_description, notification_time_before,
                                yt_channel_url, notification_channel)

    @commands_group_ytube.command(name="stop", description="Disable YouTube Notificator.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def ytube_service_stop(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        await stop_task_ytube(server, ctx)

    async def ytube_video_autocomplete(ctx: discord.Interaction, current: str, ) -> List[app_commands.Choice[str]]:
        server = ctx.guild
        if local_get_status(server.id) is ServerStatus.UNREGISTERED:
            return []
        video_list = BOT_CONFIG[server.id]['match_ytube']

        def return_stream_name(item):
            time_left = item['upcoming_date'] - discord.utils.utcnow().replace(tzinfo=None)
            return f"{item['title']} [Time Left: {helpers.strfdelta(tdelta=time_left)}]"

        return [app_commands.Choice(name=return_stream_name(video), value=video['video_id'])
                for video in video_list.values()
                if video['upcoming'] and current.lower() in video['title'].lower()]

    @commands_group_ytube.command(name="edit", description="Edit Stream Description.", extras=DEFER_YES)
    @app_commands.autocomplete(video=ytube_video_autocomplete)
    @app_commands.describe(video="Stream to edit.",
                           description="Greeting message ;) ")
    @discord_async_try_except_decorator
    async def ytube_edit_description(interaction: discord.Interaction, video: str,
                                     description: app_commands.Range[str, 0, 500]):
        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return
        stream = BOT_CONFIG[server.id]['match_ytube'][video]
        stream['description'] = description
        db_requests.ytube_update_upcoming_stream_description(server.id, video, description)
        await interaction.edit_original_response(content=f"Your description has been changed:\n"
                                                         f"Stream: **{stream['title']}**\n"
                                                         f"Description: **{description}**")

    # endregion

    # region PARSER_EGS

    async def get_games(server, notification_channel: discord.TextChannel, egs: EGSGamesParser):
        local_db = BOT_CONFIG[server.id]['match_list']
        for egs_game in egs.free_games:
            if egs_game.id not in local_db:
                print(f"Fetching game info: {egs_game.title}")
                game_info, emb, view_ = egs_game.get_discord_game_card()
                await notification_channel.send(embed=emb, view=view_)
                print(f"Got game info: {egs_game.title}")
                egs_games_save_to_dbase(server, egs.free_games)

    @commands_group_egs.command(name="start", description="Enable EGS Notificator.", extras=DEFER_YES)
    @app_commands.describe(notification_channel="Channel for sending notifications.",
                           check_hours="Check new games every X hours. Default = 0",
                           check_minutes="Check new games every X minutes. Default = 59 | Min = 3")
    @discord_async_try_except_decorator
    async def egs_service_start(ctx: discord.Interaction,
                                notification_channel: discord.TextChannel,
                                check_hours: app_commands.Range[int, 0] = 0,
                                check_minutes: app_commands.Range[int, 3] = 59):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        egs_games = EGSGamesParser()
        if egs_games.empty:
            await ctx.edit_original_response(content=f"EGS data is empty. Aborted.")
            await discord_delete_message(ctx, 5)
            return

        await create_task_egsgames(ctx, server, check_hours, check_minutes, notification_channel, egs_games)

    @commands_group_egs.command(name="stop", description="Disable EGS Notificator.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def egs_service_stop(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return
        await stop_task_egsgames(server, ctx)

    # endregion
    group_test = app_commands.Group(name="bb_test", description="Testing slash groups")

    # region SPINWHEEL
    async def spin_wheel_games_autocomplete(ctx: discord.Interaction, current: str, ) -> List[app_commands.Choice[str]]:
        server = ctx.guild
        if local_get_status(server.id) is ServerStatus.UNREGISTERED:
            return []
        games_list = BOT_CONFIG[server.id]['spin_wheel']
        return [app_commands.Choice(name=game, value=game) for game in games_list if current.lower() in game.lower()]

    async def spinwheel_save_to_db(server, values_row: dict, action: SpinWheelAction):
        MYSQL = mysql.MYSQL()
        if action is SpinWheelAction.Add:
            MYSQL.execute(
                user_query="INSERT INTO spin_wheel "
                           "(`game`, `status`, `url`, `comment`, `server_id`) "
                           "VALUES (%s,%s,%s,%s,%s)",
                values=(
                    values_row['game'], values_row['status'].value, values_row['url'], values_row['comment'],
                    server.id)
            )
        elif action is SpinWheelAction.Edit:
            MYSQL.execute(
                user_query="UPDATE spin_wheel "
                           "SET `status` = %s, `url` = %s, `comment` = %s, `game` = %s"
                           "WHERE `game` = %s and `server_id` = %s",
                values=(
                    values_row['status'].value, values_row['url'], values_row['comment'], values_row['new_game'],
                    values_row['game'], server.id)
            )
        elif action is SpinWheelAction.Delete:
            MYSQL.execute(
                user_query="DELETE FROM spin_wheel WHERE `game` = %s and `server_id` = %s",
                values=(values_row['game'], server.id)
            )
        MYSQL.commit(True)
        if action is SpinWheelAction.Add:
            BOT_CONFIG[server.id]['spin_wheel'][values_row['game']] = {
                "status": values_row['status'], "url": values_row['url'], "comment": values_row['comment']}
        elif action is SpinWheelAction.Edit:
            del BOT_CONFIG[server.id]['spin_wheel'][values_row['game']]
            BOT_CONFIG[server.id]['spin_wheel'][values_row['new_game']] = {
                "status": values_row['status'], "url": values_row['url'], "comment": values_row['comment']}
        elif action is SpinWheelAction.Delete:
            del BOT_CONFIG[server.id]['spin_wheel'][values_row['game']]
        BOT_CONFIG[server.id]['spin_wheel'] = dict(sorted(BOT_CONFIG[server.id]['spin_wheel'].items()))

    @commands_group_spinwheel.command(name="add", description="Add game in Spin Wheel.", extras=DEFER_YES)
    @app_commands.choices(status=game_status_choices)
    @app_commands.describe(game="Game to add into your Spin Wheel List.",
                           status="Game status [In List, In Progress, In Finished List, In Waiting List, In Ban List].",
                           playlist="Save YT-playlist Link.",
                           comment="Comment to current record.")
    @discord_async_try_except_decorator
    async def spinwheel_add(interaction: discord.Interaction, game: str, status: SpinWheelGameStatus,
                            playlist: str = None, comment: str = None):
        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        game_ = BOT_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is not None:
            await interaction.edit_original_response(content=f'This game is already in db **{game}**')
            return
        await spinwheel_save_to_db(server, {"game": game, "status": status, "url": playlist, "comment": comment},
                                   SpinWheelAction.Add)
        await interaction.edit_original_response(content=f'Your game has been added **{game}**')
        await discord_delete_message(interaction, 10)

    @commands_group_spinwheel.command(name="edit", description="Edit game in Spin Wheel.", extras=DEFER_YES)
    @app_commands.autocomplete(game=spin_wheel_games_autocomplete)
    @app_commands.choices(status=game_status_choices)
    @app_commands.describe(game="Game from your Spin Wheel List.",
                           name="Change name of game",
                           status="Game status | Default = Previous Status",
                           playlist="Save YT-playlist Link.",
                           comment="Comment to current record.")
    @discord_async_try_except_decorator
    async def spinwheel_edit(interaction: discord.Interaction, game: str, name: str = None,
                             status: SpinWheelGameStatusEdit = SpinWheelGameStatusEdit.Previous,
                             playlist: str = None, comment: str = None):
        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        game_ = BOT_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is None:
            await interaction.edit_original_response(content=f'I don\'t have this game in db {game}')
            return

        status = game_['status'] if status is SpinWheelGameStatusEdit.Previous else status
        playlist = game_['url'] if playlist is None else playlist
        comment = game_['comment'] if comment is None else comment
        name = game if name is None else name

        await spinwheel_save_to_db(server, {"game": game, "new_game": name, "status": status, "url": playlist,
                                            "comment": comment},
                                   SpinWheelAction.Edit)
        await interaction.edit_original_response(content=f'Your game has been changed **{game}**')

    @commands_group_spinwheel.command(name="delete", description="Delete a game from Spin Wheel.", extras=DEFER_YES)
    @app_commands.autocomplete(game=spin_wheel_games_autocomplete)
    @app_commands.describe(game="Game to delete from your Spin Wheel List.")
    @discord_async_try_except_decorator
    async def spinwheel_delete(interaction: discord.Interaction, game: str):
        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        game_ = BOT_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is None:
            await interaction.edit_original_response(content=f'I don\'t have this game in db {game}')
            return
        await spinwheel_save_to_db(server, {"game": game, "status": None, "url": None}, SpinWheelAction.Delete)
        await interaction.edit_original_response(content=f'Your has been deleted **{game}**')

    @commands_group_spinwheel.command(name="choice", description="Choice a game for playing.")
    @discord_async_try_except_decorator
    async def spinwheel_choice(interaction: discord.Interaction):
        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        game_list = [{"game": game, "status": item['status'], "url": item['url'], "comment": item['comment']}
                     for game, item in BOT_CONFIG[server.id]['spin_wheel'].items()
                     if item['status'] is SpinWheelGameStatus.InList]
        if not game_list:
            await interaction.edit_original_response(content=f'The Game List is empty.')
            return
        game_ = random.choice(game_list)
        await spinwheel_save_to_db(server, {"game": game_['game'], "status": SpinWheelGameStatus.InProgress,
                                            "url": game_["url"], "comment": game_["comment"]}, SpinWheelAction.Edit)
        emb = discord.Embed(
            title="Уразайка-Поиграйка!"
        )
        emb.add_field(name="Пора играть:", value=f"**{game_['game']}**", inline=False)
        emb.set_footer(text=game_["comment"])
        emb.set_thumbnail(url='https://cdn-icons-png.flaticon.com/256/7300/7300049.png')
        await interaction.edit_original_response(embed=emb)

    class Select(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label=x['name'], value=str(x['value']), emoji=x['emoji'])
                for x in game_status_list
            ]
            super().__init__(placeholder="Select an option", max_values=len(game_status_list), min_values=1,
                             options=options)

        async def callback(self, interaction: discord.Interaction):
            # await interaction.response.defer(ephemeral=True)
            params = BOT_CONFIG[interaction.guild.id]['category_filter'][interaction.user.id]
            descript, search, defer = params['descript'], params['search'], params['defer']
            del params
            del BOT_CONFIG[interaction.guild.id]['category_filter'][interaction.user.id]
            await spinwheel_show(interaction, descript=descript, search=search, filter=''.join(self.values),
                                 defer=defer)

    class CategoryFilter(discord.ui.View):
        def __init__(self, *, timeout=180):
            super().__init__(timeout=timeout)
            self.add_item(Select())

    @commands_allowed_to_user.command(name="show_spin_wheel", description="Show Spin the Wheel.", extras=DEFER_YES)
    @app_commands.describe(descript="Show Spin Wheel List Rules.",
                           search="Searching query",
                           category_filter="Show up category filter")
    async def show_spin_wheel(interaction: discord.Interaction,
                              category_filter: SettingYesNo = SettingYesNo.No,
                              search: app_commands.Range[str, 3] = None,
                              descript: SettingYesNo = SettingYesNo.No, ):
        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[ChecksBeforeStart.REGISTRATION]):
            return
        if category_filter is SettingYesNo.Yes:
            await interaction.response.defer(ephemeral=True)
            BOT_CONFIG[server.id]['category_filter'] = {
                interaction.user.id: {"descript": descript, "search": search, "defer": True}}
            await interaction.edit_original_response(view=CategoryFilter())
        else:
            await spinwheel_show(interaction, descript=descript, search=search)

    @commands_group_spinwheel.command(name="show", description="Show Spin the Wheel.")
    @app_commands.describe(descript="Show Spin Wheel List Rules.",
                           search="Searching query",
                           category_filter="Show up category filter",
                           defer="Message is Visible only for you.")
    async def spinwheel_show_wheel(interaction: discord.Interaction,
                                   descript: SettingYesNo = SettingYesNo.No,
                                   defer: bool = True,
                                   category_filter: SettingYesNo = SettingYesNo.No,
                                   search: app_commands.Range[str, 3] = None, ):
        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[ChecksBeforeStart.REGISTRATION]):
            return
        if category_filter is SettingYesNo.Yes:
            await interaction.response.defer(ephemeral=defer)
            BOT_CONFIG[server.id]['category_filter'] = {
                interaction.user.id: {"descript": descript, "search": search, "defer": defer}}
            await interaction.edit_original_response(view=CategoryFilter())
        else:
            await spinwheel_show(interaction, descript=descript, search=search, defer=defer)

    @discord_async_try_except_decorator
    async def spinwheel_show(interaction: discord.Interaction,
                             **kwargs):  # descript: SettingYesNo = SettingYesNo.No, ):
        # if not await is_owner(interaction): return
        server = interaction.guild

        search = kwargs.get('search', None)
        filter_category = kwargs.get('filter', [e.value for e in SpinWheelGameStatus])
        if isinstance(filter_category, str):
            filter_category = [int(char) for char in filter_category]
        filter_category.sort()

        category_list = {emb['value']: emb['embed']
                         for emb in game_status_list
                         if emb['value'] in filter_category}

        games_list = [{"game": game, "status": item['status'], "url": item['url'], "comment": item['comment']}
                      for game, item in BOT_CONFIG[server.id]['spin_wheel'].items()
                      if item['status'].value in category_list
                      and (True if search is None else game.lower().find(search.lower()) != -1)]

        if not games_list:
            await interaction.edit_original_response(content=f'The Games List is empty.')
            return

        descript = kwargs.get('descript')
        description_ = SPINWHEEL_RULES if descript is SettingYesNo.Yes else ''
        emb = discord.Embed(title="Рулетка Уразайки-Поиграйки!", description=description_)
        emb.set_thumbnail(url='http://samyukthascans.com/images/icon/spin.gif')

        def add_field_to_emb(emb_group: discord.Embed, game):
            value_ = f"📺 [Посмотреть]({game['url']})" if game['url'] is not None else "📺 Пока пусто"
            if interaction.user.guild_permissions.administrator:
                value_ += f"\n💬 Comment: {game['comment']}"
            emb_group.add_field(name=f"🕹️ {game['game']}", value=value_, inline=False)

        for game in games_list:
            add_field_to_emb(category_list[game['status'].value], game)

        embeds_list = [emb_item for emb_item in category_list.values()]
        if descript is SettingYesNo.Yes:
            embeds_list.insert(0, emb)
        await interaction.edit_original_response(embeds=embeds_list, view=None)
        # await delete_discord_message(interaction, 120)

    # endregion

    @bot.tree.command(name="test_yt", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def test_yt(ctx: discord.Interaction, channel: discord.TextChannel, url: str):

        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return
        # if await discord_channel_is_available(ctx, BOT_CONFIG[server.id]['bot_channel']) is None: return

        v = await YTParser(channel_id=url, create_channel_object=False).get_last_livestream()
        has_perm = channel.permissions_for(channel.guild.me).send_messages
        emb = discord.Embed(title="Has permission.",
                            description=f"Bot has permission for channel {channel.name}: {has_perm}")
        title = None if v.currentLiveStream is None else v.currentLiveStream.title
        date_at = None if v.currentLiveStream is None else v.upcomingDate
        await ctx.edit_original_response(
            content=f"Title, Live,Upcoming, Date:[{title, v.isLiveContent, v.isUpcoming, date_at}]", embed=emb)

    # region SC_SERVER

    @commands_group_server.command(name="info", description="Show SERVER info.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def server_info(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        bot_channel = local_get_bot_channel(server.id)
        # if bot_channel is not None:
        #     bot_channel = bot.get_channel(bot_channel).name
        emb = discord.Embed(title="SERVER-INFO", )
        emb.add_field(name="Name", value=f"[**{ctx.guild.name}**]")
        emb.add_field(name="ID", value=f"[**{ctx.guild.id}**]")
        emb.add_field(name="Status", value=f"[**{BOT_CONFIG[server.id]['status'].name}**]")
        emb.add_field(name="Service channel", value=f"[**{bot_channel}**]")
        emb.set_thumbnail(url=bot.user.avatar)
        await ctx.edit_original_response(embed=emb)
        await discord_delete_message(ctx, 10)

    @commands_group_server.command(name="change_channel",
                                   description="Change service (private) channel for notifications from bot.",
                                   extras=DEFER_YES)
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @discord_async_try_except_decorator
    async def server_change_channel(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        if bot_channel.id == local_get_bot_channel(server.id):
            await ctx.edit_original_response(
                content="Hey, Bunny! You are giving me the same channel. Are you alright? :)")
            await discord_delete_message(ctx, 5)
            return
        MYSQL = mysql.MYSQL()
        MYSQL.execute("UPDATE bot_config SET `service_channel` = %s WHERE `server_id` = %s",
                      values=(bot_channel.id, server.id))
        MYSQL.commit()
        BOT_CONFIG[server.id]['bot_channel'] = bot_channel.id
        await ctx.edit_original_response(
            content=f"It's done. **{bot_channel.name}** now is your new service channel.")
        await discord_delete_message(ctx, 10)

    @commands_group_server.command(name="signup",
                                   description="Register the bot. You need to create a private channel (mute) & give me permission.",
                                   extras=DEFER_YES)
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @discord_async_try_except_decorator
    async def server_signup(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER]):
            return

        if not discord_has_permission_to_send_messages(ctx, bot_channel): return

        if BOT_CONFIG[server.id]['status'] is ServerStatus.REGISTERED:
            await ctx.edit_original_response(content=f"You're already here [**{server.name}**]:[**{server.id}**]")
            await discord_delete_message(ctx, 10)
            return

        # Making a registration
        print(f"Creating server row for [**{server.name}**]:[**{server.id}**]...")
        MYSQL = mysql.MYSQL()
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
        MYSQL.executemany(user_query, value_list)
        MYSQL.execute('INSERT INTO bot_config (service_channel, server_id) VALUES (%s, %s)',
                      values=(bot_channel.id, server.id))
        await asyncio.sleep(2)
        MYSQL.commit(True)

        BOT_CONFIG[server.id]['status'] = ServerStatus.REGISTERED
        BOT_CONFIG[server.id]['bot_channel'] = bot_channel.id
        BOT_CONFIG[server.id]['features'] = db_requests.server_get_settings(server.id)

        await ctx.edit_original_response(
            content=f"Your Server [**{server.name}**]:[**{server.id}**] has been registered. Congrats!.")
        await discord_delete_message(ctx, 10)

    @commands_group_server.command(name="delete",
                                   description="Delete server from bot' database. **All your setting will be lost.**",
                                   extras=DEFER_YES)
    @app_commands.describe(confirm="In order to check your decision.")
    @discord_async_try_except_decorator
    async def server_delete(ctx: discord.Interaction, confirm: SettingYesNo):
        server = ctx.guild
        if not await passed_checks_before_start_command(server, ctx,
                                                        checks=[ChecksBeforeStart.OWNER,
                                                                ChecksBeforeStart.REGISTRATION]):
            return

        if confirm is SettingYesNo.No:
            await ctx.edit_original_response(
                content=f"Command has been canceled.")
            await discord_delete_message(ctx, 10)

        db_requests.server_delete_bot_registration(server.id)
        local_flush_server_settings(server.id)
        await ctx.edit_original_response(
            content=f"Your Server [**{server.name}**]:[**{server.id}**] has been deleted.")
        await discord_delete_message(ctx, 10)

    # endregion

    async def bot_say_hi_to_registered_server(server: discord.Guild):
        bot_channel_id = BOT_CONFIG[server.id]['bot_channel']
        if bot.is_ready() and local_get_status(server.id) is ServerStatus.REGISTERED and bot_channel_id is not None:
            try:
                if not BOT_CONFIG[server.id]['ready']: return
                bot_channel = bot.get_channel(bot_channel_id)
                if bot_channel is None:
                    bot_channel_id = None
                    owner = server.owner
                    await owner.send(
                        f"**{owner.name}** A зачем канал удалили для сервисных сообщений на **{server.name}**? ")
                    return
                await bot_channel.send(
                    content=f"Hi! **{BOT_CONFIG[server.id]['name']}** SERVER. I'm online!!!")
                print(f"Hi! **{BOT_CONFIG[server.id]['name']}** SERVER. I'm online!!!")
            except discord.errors.Forbidden as e:
                print(
                    f"I have a service channel on {server.id}, but I have no rights. Just skipping this carrotbutt.")

    # endregion
    @bot.event
    async def on_guild_channel_delete(deleted_channel):
        print('hi')
        pass

    @tasks.loop(seconds=10)
    async def loop(servers: List[discord.Guild]):
        for server in servers:
            await asyncio.sleep(2)
            server_obj = discord.Object(server.id)
            await bot.tree.sync(guild=server_obj)
            logger.info(f"trying sync on {server.name}")

    @bot.event
    async def on_ready():
        await bot.wait_until_ready()
        await bot.tree.sync()
        logger.info(f"Logged in as {bot.user.name}({bot.user.id})")
        # BOT_LOCAL_CONFIG['bot_channels'] = server_get_bot_channels()
        for group in [group_test, commands_group_ytube, commands_group_egs, commands_group_spinwheel,
                      commands_group_server, commands_allowed_to_user]:
            bot.tree.add_command(group, guilds=bot.guilds)
            # await loop.start(bot.guilds)
        for server in bot.guilds:
            await asyncio.sleep(2)
            await bot.tree.sync(guild=server)

            bot_channel, bot_ready = db_requests.server_get_bot_settings(server.id)
            BOT_CONFIG[server.id] = {
                'id': server.id,
                'name': server.name,
                'bot_channel': bot_channel,
                'ready': bot_ready,
                'status': db_requests.server_get_status(server.id),
                'features': db_requests.server_get_settings(server.id),
                'match_ytube': db_requests.server_get_matching_ytube_list(server.id),
                'match_egs': db_requests.server_get_matching_egs_list(server.id),
                'spin_wheel': db_requests.server_get_spinwheel_list(server.id),
            }
            if BOT_CONFIG[server.id]['bot_channel'] is not None:
                await bot_say_hi_to_registered_server(server)
            # Check LOOPS here
            print(f"Server:[{server.name}]:[{server.id}]")

    bot.run(token=config.BUNNYBYTE_TOKEN)


if __name__ == "__main__":
    discord_bot()
