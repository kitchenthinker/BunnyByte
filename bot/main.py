import random
from typing import List, Dict, Optional, Literal, Union
from enum import Enum, Flag
import config
import functools
import asyncio
import mysql
# region DISCORD IMPORTS
import discord
import discord.ui as ui
from discord import (
    app_commands,
    ButtonStyle, TextStyle, SelectMenu, SelectOption,
)
from discord.ext import (
    commands, tasks,
)
# endregion
# region MY_FILES
from yt_parser import YTParser, BUNNY_CHANNEL_ID
from egs_parser import EGSGamesParser, EGSGame

# endregion

BOT_LOCAL_CONFIG = {"g": ['None']}


# region HELPERS CLASSES
class SpinWheelGameStatus(Enum):
    InList = 0
    InProgress = 1
    InFinishedList = 2
    InWaitingList = 3
    InBanList = 4


class SpinWheelGameStatusEdit(Enum):
    InList = 0
    InProgress = 1
    InFinishedList = 2
    InWaitingList = 3
    InBanList = 4
    Previous = 5


class SettingSwitcher(Enum):
    Enable = 1
    Disable = 0


class ServerStatus(Flag):
    REGISTERED = True
    UNREGISTERED = False


# endregion
def simple_try_except_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    return wrapper


def discord_async_try_except_decorator(func):
    """
    To be honest, I dunno know what I'm doing. It works (I hope) , I don't touch.
    :param func:
    :return:
    """

    @functools.wraps(func)
    async def wrapper(interaction, *args, **kwargs):
        is_discord_interaction = isinstance(interaction, discord.Interaction)
        try:
            if is_discord_interaction:
                await interaction.response.defer(ephemeral=False)
            return await func(interaction, *args, **kwargs)
        except Exception as e:
            if is_discord_interaction:
                await interaction.edit_original_response(
                    content=f"Something went wrong [{e}]. Try again or send me a message and we will do something.")
            print(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

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
    BOT_LOCAL_CONFIG[server.id]['match_list'].append(yt_video.video_id)
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
        BOT_LOCAL_CONFIG[server.id]['match_list'].append(g.id)
    MYSQL.commit(True)
    print(f"Games list has been saved.")


@simple_try_except_decorator
def server_get_status(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`=%s",
                   values=server_id
                   )
    MYSQL.close()
    return ServerStatus(not MYSQL.empty)


@simple_try_except_decorator
def server_get_bot_channel(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(f"SELECT * FROM `bot_config` WHERE `server_id`=%s",
                   values=server_id
                   )
    MYSQL.close()
    if MYSQL.empty:
        return None
    else:
        return int(MYSQL.data[0]['service_channel'])


@simple_try_except_decorator
def server_get_settings(server_id: int | str = None):
    def return_setting_dict(feature_name: str):
        return {x['name']: {"v": x['value'], "t": x['type']} for x in
                (item for item in MYSQL.data if item['fname'] == feature_name)}

    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT settings.name, srv_config.value, settings.`type`, settings.description, features.name AS fname\n"
                   "FROM srv_config\n"
                   "LEFT JOIN settings\n"
                   "ON srv_config.setting_id = settings.id\n"
                   "LEFT JOIN features\n"
                   "ON settings.feature_id = features.id\n"
                   "WHERE srv_config.server_id = %s",
        values=server_id
    )
    settings_egs, settings_ytube = None, None
    if not MYSQL.empty:
        settings_egs = return_setting_dict('egs')
        settings_ytube = return_setting_dict('ytube')
    MYSQL.close()
    return {
        'egs': {'settings': settings_egs, 'task': None, },
        'ytube': {'settings': settings_ytube, 'task': None, }
    }


@simple_try_except_decorator
def server_get_matching_list(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT id FROM srv_matching WHERE server_id = %s",
        values=server_id
    )
    MYSQL.close()
    return list() if MYSQL.empty else list(MYSQL.data)


@simple_try_except_decorator
def server_get_spinwheel_list(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT game, status, url FROM spin_wheel WHERE server_id = %s",
        values=server_id
    )
    MYSQL.close()
    return dict() if MYSQL.empty else {x['game']: {"status": SpinWheelGameStatus(x['status']), "url": x['url']} for x in
                                       MYSQL.data}


# region LOCAL_BOT
def local_flush_server_settings(server_id: int | str = None):
    BOT_LOCAL_CONFIG[server_id]['bot_channel'] = None
    BOT_LOCAL_CONFIG[server_id]['status'] = ServerStatus.UNREGISTERED
    BOT_LOCAL_CONFIG[server_id]['features'] = {
        'egs': {'settings': None, 'task': None, },
        'ytube': {'settings': None, 'task': None, }
    }
    BOT_LOCAL_CONFIG[server_id]['match_list'] = ServerStatus.UNREGISTERED


def local_get_bot_channel(server_id: int | str = None):
    return BOT_LOCAL_CONFIG[server_id].get('bot_channel')


def local_get_status(server_id: int | str = None):
    return BOT_LOCAL_CONFIG[server_id].get('status')


# endregion

def discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='.', intents=intents)
    bot.remove_command('help')

    commands_group_ytube = app_commands.Group(name="bb_ytube",
                                              description="Commands for interaction with YouTube-Notificator.")
    commands_group_egs = app_commands.Group(name="bb_egs",
                                            description="Commands for interaction with EGS-Notificator.")
    commands_group_spinwheel = app_commands.Group(name="bb_wheel",
                                                  description="Commands for interaction with Spin Wheel")

    async def delete_discord_message(msg: discord.Message | discord.Interaction, delete_after_sec: int = 3):
        await asyncio.sleep(delete_after_sec)
        if isinstance(msg, discord.Message):
            await msg.delete()
        elif isinstance(msg, discord.Interaction):
            await msg.delete_original_response()

    async def is_server_registered(ctx: discord.Interaction, server: discord.Guild, context: str = None,
                                   delete_after: bool = True, delete_after_sec: int = 5) -> bool:
        status = local_get_status(server.id) == ServerStatus.UNREGISTERED
        if status:
            if context is None:
                context = f'Server **{server.name}** Unregistered'
            print(context)
            await ctx.edit_original_response(content=context)
            if delete_after:
                await delete_discord_message(ctx, delete_after_sec)
        return not status

    # region Interactions

    # region SLASH_COMMANDS
    @bot.tree.command(name="help")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def custom_help(ctx: discord.Interaction):
        # await ctx.response.defer(ephemeral=False)
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
        await ctx.edit_original_response(embed=emb)
        await delete_discord_message(ctx, 30)

    # LOOPS
    # region PARSER_YOUTUBE

    async def yt_last_video(server, channel_for_notification: discord.TextChannel,
                            yt_channel: YTParser = YTParser(BUNNY_CHANNEL_ID),
                            show_description: int = 0):

        current_video = yt_channel.current_video
        is_livestream = False
        if yt_channel.current_livestream is not None:
            current_video = yt_channel.current_livestream
            is_livestream = True
        print(f"Fetching video info: {current_video.title}")
        video_info, emb, view_ = yt_channel.get_discord_video_card(current_video, bool(show_description), is_livestream)
        await channel_for_notification.send(embed=emb, view=view_)
        yt_video_save_to_dbase(server, current_video)
        print(f"Got video info: {current_video.title}")

    @commands_group_ytube.command(name="start", description="Enable YouTube Notificator.")
    @app_commands.describe(yt_channel_url="YouTube Channel URL",
                           notification_channel="Channel for sending notifications.",
                           show_description="Show full video description in template. Default = Disable",
                           check_hours="Check new video every X hours. Default = 0",
                           check_minutes="Check new video every X minutes. Default = 59 | Min = 3")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def ytube_service_start(ctx: discord.Interaction,
                                  notification_channel: discord.TextChannel,
                                  yt_channel_url: str,
                                  show_description: SettingSwitcher = SettingSwitcher.Disable,
                                  check_hours: app_commands.Range[int, 0] = 0,
                                  check_minutes: app_commands.Range[int, 3] = 59):
        server = ctx.guild
        yt_channel = YTParser(yt_channel_url)
        if yt_channel.channel_is_empty:
            await ctx.edit_original_response(content=f"Channel is empty:{yt_channel_url}. Aborted.")
            await delete_discord_message(ctx, 5)
            return
        if not await is_server_registered(ctx, server):
            return

        task_to_run: tasks.Loop | None = BOT_LOCAL_CONFIG[server.id]['features']['ytube'].get('task')

        full_minutes = check_hours * 60 + check_minutes
        if task_to_run is None:
            new_task = BOT_LOCAL_CONFIG[server.id]['features']['ytube']['task'] = tasks.loop(minutes=full_minutes)(
                yt_last_video)
            task_to_run = new_task
        if task_to_run.is_running():
            await ctx.edit_original_response(content=f"YT-Notificator is already running on {server.name}")
            await delete_discord_message(ctx, 5)
            print(f"YT-Notificator is already running on {server.name}")
        else:
            await ctx.edit_original_response(content=f"YT-Notificator is alive on {server.name}")
            await delete_discord_message(ctx, 5)

            BOT_LOCAL_CONFIG[server.id]['features']['ytube']['settings']['enable'] = True
            BOT_LOCAL_CONFIG[server.id]['features']['ytube']['settings']['repeat'] = full_minutes
            BOT_LOCAL_CONFIG[server.id]['features']['ytube']['settings']['yt_channel'] = yt_channel_url
            BOT_LOCAL_CONFIG[server.id]['features']['ytube']['settings']['channel_id'] = notification_channel.id
            BOT_LOCAL_CONFIG[server.id]['features']['ytube']['settings']['show_description'] = bool(
                show_description.value)

            # bot_channel = bot.get_channel(ctx.channel_id)
            task_to_run.start(server, notification_channel, yt_channel, show_description.value)
            print(f"YT-Notificator is alive on {server.name}")

    @commands_group_ytube.command(name="stop", description="Disable YouTube Notificator.")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def ytube_service_stop(ctx: discord.Interaction):
        # await ctx.response.defer(ephemeral=False)
        server = ctx.guild
        if not await is_server_registered(ctx, server):
            return

        task_to_run: tasks.Loop | None = BOT_LOCAL_CONFIG[server.id]['features']['ytube']['task']

        if task_to_run is None:
            print(f"Nothing to stop on {server.name}")
            await ctx.edit_original_response(content=f"Nothing to stop on {server.name}")
            await delete_discord_message(ctx, 5)
            return
        task_to_run.cancel()

        BOT_LOCAL_CONFIG[server.id]['features']['ytube']['task'] = None
        BOT_LOCAL_CONFIG[server.id]['features']['ytube']['settings']['enable'] = False
        # save to db
        print(f"The loop is shut down on {server.name}")
        await ctx.edit_original_response(content=f"The loop is shut down on {server.name}")
        await delete_discord_message(ctx, 5)

    # endregion

    # region PARSER_EGS

    async def get_games(server, notification_channel: discord.TextChannel, egs: EGSGamesParser):
        local_db = BOT_LOCAL_CONFIG[server.id]['match_list']
        for egs_game in egs.free_games:
            if egs_game.id not in local_db:
                print(f"Fetching game info: {egs_game.title}")
                game_info, emb, view_ = egs_game.get_discord_game_card()
                await notification_channel.send(embed=emb, view=view_)
                print(f"Got game info: {egs_game.title}")
                egs_games_save_to_dbase(server, egs.free_games)

    @commands_group_egs.command(name="start", description="Enable EGS Notificator.")
    @app_commands.describe(notification_channel="Channel for sending notifications.",
                           check_hours="Check new games every X hours. Default = 0",
                           check_minutes="Check new games every X minutes. Default = 59 | Min = 3")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def egs_service_start(ctx: discord.Interaction,
                                notification_channel: discord.TextChannel,
                                check_hours: app_commands.Range[int, 0] = 0,
                                check_minutes: app_commands.Range[int, 3] = 59):
        server = ctx.guild
        egs = EGSGamesParser()
        if egs.empty:
            await ctx.edit_original_response(content=f"EGS data is empty. Aborted.")
            await delete_discord_message(ctx, 5)
            return
        if not await is_server_registered(ctx, server):
            return

        task_to_run: tasks.Loop | None = BOT_LOCAL_CONFIG[server.id]['features']['egs'].get('task')

        full_minutes = check_hours * 60 + check_minutes
        if task_to_run is None:
            new_task = BOT_LOCAL_CONFIG[server.id]['features']['egs']['task'] = tasks.loop(minutes=full_minutes)(
                get_games)
            task_to_run = new_task
        if task_to_run.is_running():
            await ctx.edit_original_response(content=f"EGS-Notificator is already running on {server.name}")
            await delete_discord_message(ctx, 5)
            print(f"EGS-Notificator is already running on {server.name}")
        else:
            await ctx.edit_original_response(content=f"EGS-Notificator is alive on {server.name}")
            await delete_discord_message(ctx, 5)

            # bot_channel = bot.get_channel(ctx.channel_id)
            BOT_LOCAL_CONFIG[server.id]['features']['egs']['settings']['enable'] = True
            BOT_LOCAL_CONFIG[server.id]['features']['egs']['settings']['repeat'] = full_minutes
            BOT_LOCAL_CONFIG[server.id]['features']['egs']['settings']['channel_id'] = notification_channel.id

            task_to_run.start(server, notification_channel, egs)
            print(f"EGS-Notificator is alive on {server.name}")

    @commands_group_egs.command(name="stop", description="Disable EGS Notificator.")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def egs_service_stop(ctx: discord.Interaction):
        # await ctx.response.defer(ephemeral=False)
        server = ctx.guild
        if not await is_server_registered(ctx, server):
            return

        task_to_run: tasks.Loop | None = BOT_LOCAL_CONFIG[server.id]['features']['egs']['task']

        if task_to_run is None:
            print(f"Nothing to stop on {server.name}")
            await ctx.edit_original_response(content=f"Nothing to stop on {server.name}")
            await delete_discord_message(ctx, 5)
            return
        task_to_run.cancel()

        BOT_LOCAL_CONFIG[server.id]['features']['egs']['task'] = None
        BOT_LOCAL_CONFIG[server.id]['features']['egs']['settings']['enable'] = False
        # save to db!!!
        print(f"EGS Notificator is shut down on {server.name}")
        await ctx.edit_original_response(content=f"EGS Notificator is shut down on {server.name}")
        await delete_discord_message(ctx, 5)

    # endregion
    group_test = app_commands.Group(name="bb_test", description="Testing slash groups")

    # region SPINWHEEL
    async def spin_wheel_games(
            interaction: discord.Interaction,
            current: str,
    ) -> List[app_commands.Choice[str]]:
        server = interaction.guild
        games_list = BOT_LOCAL_CONFIG[server.id]['spin_wheel']
        return [
            app_commands.Choice(name=game, value=game)
            for game in games_list if current.lower() in game.lower()
        ]

    class SpinWheelAction(Enum):
        Add = 0,
        Edit = 1,
        Delete = 2

    async def spinwheel_save_to_db(server, values_row: dict, action: SpinWheelAction):
        MYSQL = mysql.MYSQL()
        if action == SpinWheelAction.Add:
            MYSQL.execute(
                user_query="INSERT INTO spin_wheel (`game`, `status`, `url`, `server_id`) VALUES (%s,%s,%s,%s)",
                values=(values_row['game'], values_row['status'].value, values_row['url'], server.id)
            )
        elif action == SpinWheelAction.Edit:
            MYSQL.execute(
                user_query="UPDATE spin_wheel SET `status` = %s, `url` = %s WHERE `game` = %s and `server_id` = %s",
                values=(values_row['status'].value, values_row['url'], values_row['game'], server.id)
            )
        elif action == SpinWheelAction.Delete:
            MYSQL.execute(
                user_query="DELETE FROM spin_wheel WHERE `game` = %s and `server_id` = %s",
                values=(values_row['game'], server.id)
            )
        MYSQL.commit(True)
        if action in [SpinWheelAction.Add, SpinWheelAction.Edit]:
            BOT_LOCAL_CONFIG[server.id]['spin_wheel'][values_row['game']] = {
                "status": values_row['status'], "url": values_row['url']}
        elif action == SpinWheelAction.Delete:
            del BOT_LOCAL_CONFIG[server.id]['spin_wheel'][values_row['game']]

    @commands_group_spinwheel.command(name="add", description="Add game in Spin Wheel.")
    @app_commands.describe(game="Game to add into your Spin Wheel List.",
                           status="Game status [In List, In Progress, In Finished List, In Waiting List, In Ban List].",
                           playlist="Save YT-playlist Link.")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def spinwheel_add(interaction: discord.Interaction, game: str, status: SpinWheelGameStatus,
                            playlist: str = None):
        server = interaction.guild
        game_ = BOT_LOCAL_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is not None:
            await interaction.edit_original_response(content=f'This game is already in db **{game}**')
            return
        await spinwheel_save_to_db(server, {"game": game, "status": status, "url": playlist}, SpinWheelAction.Add)
        await interaction.edit_original_response(content=f'Your game is added **{game}**')

    @commands_group_spinwheel.command(name="edit", description="Edit game in Spin Wheel.")
    @app_commands.autocomplete(game=spin_wheel_games)
    @app_commands.describe(game="Game from your Spin Wheel List.",
                           status="Game status [In List, In Progress, In Finished List, In Waiting List, In Ban List].",
                           playlist="Save YT-playlist Link.")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def spinwheel_edit(interaction: discord.Interaction, game: str,
                             status: SpinWheelGameStatusEdit,
                             playlist: str = None):
        server = interaction.guild
        game_ = BOT_LOCAL_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is None:
            await interaction.edit_original_response(content=f'I don\'t have this game in db {game}')
            return
        if status == SpinWheelGameStatusEdit.Previous:
            status = game_['status']
        if playlist is None:
            playlist = game_['url']
        await spinwheel_save_to_db(server, {"game": game, "status": status, "url": playlist}, SpinWheelAction.Edit)
        await interaction.edit_original_response(content=f'Your game is changed **{game}**')

    @commands_group_spinwheel.command(name="delete", description="Delete a game from Spin Wheel.")
    @app_commands.autocomplete(game=spin_wheel_games)
    @app_commands.describe(game="Game to delete from your Spin Wheel List.")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def spinwheel_delete(interaction: discord.Interaction, game: str):
        server = interaction.guild
        game_ = BOT_LOCAL_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is None:
            await interaction.edit_original_response(content=f'I don\'t have this game in db {game}')
            return
        await spinwheel_save_to_db(server, {"game": game, "status": None, "url": None}, SpinWheelAction.Delete)
        await interaction.edit_original_response(content=f'Your game is deleted **{game}**')

    @commands_group_spinwheel.command(name="choice", description="Choice a game for playing.")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def spinwheel_choice(interaction: discord.Interaction):
        server = interaction.guild
        game_list = [{"game": game, "status": item['status'], "url": item['url']}
                     for game, item in BOT_LOCAL_CONFIG[server.id]['spin_wheel'].items()
                     if item['status'] == SpinWheelGameStatus.InList]
        if not game_list:
            await interaction.edit_original_response(content=f'The Game List is empty.')
            return
        game_ = random.choice(game_list)
        await spinwheel_save_to_db(server, {"game": game_['game'], "status": SpinWheelGameStatus.InProgress, "url": game_["url"]}, SpinWheelAction.Edit)
        emb = discord.Embed(
            title="Уразайка-Поиграйка!"
        )
        emb.add_field(name="Пора играть:", value=f"**{game_['game']}**", inline=False)
        emb.set_thumbnail(url='https://cdn-icons-png.flaticon.com/256/7300/7300049.png')
        await interaction.edit_original_response(embed=emb)

    # endregion

    @bot.tree.command()
    async def test_yt(ctx: discord.Interaction):
        emb = discord.Embed(title="1",
                            description=BOT_LOCAL_CONFIG[ctx.guild.id])
        emb.add_field(name="Psychonauts", value="[Playlist](https://www.youtube.com/watch?v=SAdv2JSPrf4)")
        await ctx.response.send_message(embed=emb)

    # region SC_SERVER
    @bot.tree.command(name="bb_server_info", description="Show SERVER info.")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def server_info(ctx: discord.Interaction):
        # await ctx.response.defer(ephemeral=False)
        server = ctx.guild

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
        await ctx.edit_original_response(embed=emb)
        await delete_discord_message(ctx, 10)

    @bot.tree.command(name="bb_server_change_channel",
                      description="Change service (private) channel for notifications from bot.")
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def server_change_channel(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        server = ctx.guild
        # await ctx.response.defer(ephemeral=False)

        if not await is_server_registered(ctx, server,
                                          f"Hey, Bunny from **{server.name}**! You need to be registered before changing something :)"):
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

    @bot.tree.command(name="bb_server_signup",
                      description="Register the bot. You need to create a private channel (mute) & give me permission.")
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def server_signup(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        server = ctx.guild
        # await ctx.response.defer(ephemeral=False)

        if BOT_LOCAL_CONFIG[server.id]['status'] == ServerStatus.REGISTERED:
            await ctx.edit_original_response(content=f"You're already here [**{server.name}**]:[**{server.id}**]")
            await delete_discord_message(ctx, 10)
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

        BOT_LOCAL_CONFIG[server.id]['status'] = ServerStatus.REGISTERED
        BOT_LOCAL_CONFIG[server.id]['bot_channel'] = bot_channel.id
        BOT_LOCAL_CONFIG[server.id]['features'] = server_get_settings(server.id)

        await ctx.edit_original_response(
            content=f"Your Server [**{server.name}**]:[**{server.id}**] has been registered. Congrats!.")
        await delete_discord_message(ctx, 10)

    @bot.tree.command(name="bb_server_delete",
                      description="Delete server from bot' database. **All your setting will be lost.**")
    @commands.has_permissions(administrator=True)
    @discord_async_try_except_decorator
    async def server_delete(ctx: discord.Interaction):
        server = ctx.guild
        # await ctx.response.defer(ephemeral=False)

        if not await is_server_registered(ctx, server=server,
                                          context=f"Your Server [**{server.name}**]:[**{server.id}**] hasn't been registered. Aborted.",
                                          delete_after=False):
            return

        MYSQL = mysql.MYSQL()
        MYSQL.execute(f"DELETE FROM servers WHERE `id`='{server.id}'")
        MYSQL.commit(True)
        local_flush_server_settings(server.id)
        await ctx.edit_original_response(
            content=f"Your Server [**{server.name}**]:[**{server.id}**] has been deleted.")
        await delete_discord_message(ctx, 10)

    # endregion

    async def bot_say_hi_to_registered_server(server_id: int | str):
        if bot.is_ready() and local_get_status(server_id) == ServerStatus.REGISTERED:
            try:
                bot_channel = bot.get_channel(BOT_LOCAL_CONFIG[server_id]['bot_channel'])
                await bot_channel.send(content=f"Hi! **{BOT_LOCAL_CONFIG[server_id]['name']}** SERVER. I'm online!!!")
                print(f"Hi! **{BOT_LOCAL_CONFIG[server_id]['name']}** SERVER. I'm online!!!")
            except discord.errors.Forbidden as e:
                print(f"I have a service channel on {server_id}, but I have no rights. Just skipping this carrotbutt.")

    # endregion

    @bot.event
    async def on_ready():
        await bot.wait_until_ready()
        await bot.tree.sync()
        print(f"Logged in as {bot.user.name}({bot.user.id})")
        for server in bot.guilds:
            for group in [group_test, commands_group_ytube, commands_group_egs, commands_group_spinwheel]:
                bot.tree.add_command(group, guild=server)
            await bot.tree.sync(guild=server)

            # It'd be better fetching all rows, but I'm too lazy for it.
            BOT_LOCAL_CONFIG[server.id] = {
                'id': server.id,
                'name': server.name,
                'bot_channel': server_get_bot_channel(server.id),
                'status': server_get_status(server.id),
                'features': server_get_settings(server.id),
                'match_list': server_get_matching_list(server.id),
                'spin_wheel': server_get_spinwheel_list(server.id),
            }
            if BOT_LOCAL_CONFIG[server.id]['bot_channel'] is not None:
                await bot_say_hi_to_registered_server(server.id)
            # Check LOOPS here
            print(f"Server:[{server.name}]:[{server.id}]")

    bot.run(token=config.BUNNYBYTE_TOKEN)


if __name__ == "__main__":
    discord_bot()
