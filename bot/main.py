import asyncio
import config
import discord
import db_requests
import helpers
import mysql
import random
import joke

from datetime import datetime

from helpers import (
    simple_try_except_decorator,
    discord_async_try_except_decorator,
    logger,
    EPHEMERAL_ATTRIBUTE_NAME, DEFER_YES, DEFER_NO, utc_time_now
)
# region DISCORD IMPORTS
from discord import (
    app_commands,
)
from discord.ext import (
    commands, tasks,
)
from yt_parser import YTLiveStreamParser, YouTubeLiveStream, YoutubeStreamStatus
from egs_parser import EGSGamesParser, EGSGame
from gp_parser import GamerPowerParser, GamerPowerGame
from enums import *
from spinwheel_games import *

# endregion

BOT_CONFIG = {}


# region HELPERS CLASSES

# endregion


@simple_try_except_decorator
def egs_games_save_to_dbase(server, free_game: EGSGame | GamerPowerGame, game_info: dict):
    db_requests.egs_save_game_to_db(server.id, free_game)
    BOT_CONFIG[server.id]['match_egs'][free_game.id] = game_info
    logger.info(f"Game [{free_game.title}] list has been saved.")


# region LOCAL_BOT
def local_flush_server_settings(server: discord.Guild):
    BOT_CONFIG[server.id]['bot_channel'] = None
    BOT_CONFIG[server.id]['ready'] = False
    BOT_CONFIG[server.id]['status'] = ServerStatus.UNREGISTERED
    BOT_CONFIG[server.id]['features'] = {
        'egs': {'settings': None, 'task': None, },
        'ytube': {'settings': None, 'task': None, }
    }
    BOT_CONFIG[server.id]['match_ytube'] = {}
    BOT_CONFIG[server.id]['match_egs'] = {}


def local_get_bot_channel(server_id: int | str = None):
    return BOT_CONFIG[server_id].get('bot_channel', -1)


def local_get_status(server_id: int | str = None):
    return BOT_CONFIG[server_id].get('status', ServerStatus.UNREGISTERED)


def logger_save_and_return_text(text: str):
    logger.info(text)
    return text


# endregion

def discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    allowed_mentions = discord.AllowedMentions(everyone=True)
    bot = commands.Bot(command_prefix='.', intents=intents, help_command=None, allowed_mentions=allowed_mentions)

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

    async def discord_delete_message(msg: discord.Message | discord.Interaction, delete_after_sec: int = 5):
        if not msg.command.extras.get(EPHEMERAL_ATTRIBUTE_NAME):
            await asyncio.sleep(delete_after_sec)
            if isinstance(msg, discord.Message):
                await msg.delete()
            elif isinstance(msg, discord.Interaction):
                await msg.delete_original_response()

    async def embed_output_server_message(ctx: discord.Interaction, msg: str = None, delete_after: bool = False,
                                          embed_: discord.Embed | List[discord.Embed] = None,
                                          view_: discord.ui.View = None):
        embed_list = list()
        if msg is not None:
            emb = discord.Embed(title="Message from BunnyByte", description=msg)
            emb.set_thumbnail(url=bot.user.avatar)
            embed_list.append(emb)
        if embed_ is not None:
            if isinstance(embed_, list):
                for e in embed_:
                    embed_list.append(e)
            else:
                embed_list.append(embed_)
        if not embed_list:
            embed_list.append(discord.Embed(title="Message from BunnyByte", description="Message is empty"))
        await ctx.edit_original_response(embeds=embed_list, view=view_)
        if delete_after:
            await discord_delete_message(ctx)

    async def discord_has_permission_to_send_messages(ctx: discord.Interaction, channel: discord.TextChannel):
        has_permission = all([channel.permissions_for(channel.guild.me).send_messages,
                              channel.permissions_for(channel.guild.me).view_channel,
                              channel.permissions_for(channel.guild.me).attach_files,
                              channel.permissions_for(channel.guild.me).embed_links, ])
        if not has_permission:
            await embed_output_server_message(ctx,
                                              f"I have no rights to send messages here. Channel [**{channel.name}**]")
        return has_permission

    async def discord_channel_is_available(ctx: discord.Interaction, channel_id: int) -> discord.TextChannel | None:
        channel_exist = bot.get_channel(channel_id)
        if channel_exist is None:
            await embed_output_server_message(ctx, "Current Channel isn't available.")
        return channel_exist

    async def discord_is_server_registered(ctx: discord.Interaction, server: discord.Guild, context: str = None,
                                           delete_after: bool = True, delete_after_sec: int = 5) -> bool:
        status = local_get_status(server.id) is ServerStatus.UNREGISTERED
        if status:
            if context is None:
                context = f'Server **{server.name}** is Unregistered'
            logger.info(context)
            await embed_output_server_message(ctx, context)
            if delete_after and ctx.command.extras.get(EPHEMERAL_ATTRIBUTE_NAME) is not None:
                await discord_delete_message(ctx, delete_after_sec)
        return not status

    async def discord_is_owner(ctx: discord.Interaction, send_response: bool = True):
        permission = ctx.user.guild_permissions.administrator
        if not permission and send_response:
            await embed_output_server_message(ctx, "🐰, у тебя лапки.", True)
        return permission

    async def passed_checks_before_start_command(server: discord.Guild = None,
                                                 ctx: discord.Interaction = None,
                                                 channel: discord.TextChannel | int = None,
                                                 checks: List[StartChecks] = None):
        if checks is None: checks = []

        if StartChecks.OWNER in checks:
            if not await discord_is_owner(ctx):
                return False
        if StartChecks.REGISTRATION in checks:
            if not await discord_is_server_registered(ctx, server):
                return False
        if StartChecks.CHANNEL_EXIST in checks:
            channel_id = channel.id if isinstance(channel, discord.TextChannel) else channel
            if await discord_channel_is_available(ctx, channel_id) is None:
                return False
        if StartChecks.CHANNEL_AVAILABLE in checks:
            channel_perm = channel if isinstance(channel, discord.TextChannel) else bot.get_channel(channel)
            if not await discord_has_permission_to_send_messages(ctx, channel_perm):
                return False
        if StartChecks.ALREADY_REGISTERED in checks:
            if BOT_CONFIG[server.id]['status'] is ServerStatus.REGISTERED:
                await embed_output_server_message(ctx, f"You're already here [**{server.name}**]:[**{server.id}**]")
                return

        return True

    async def task_ytube_create(server: discord.Guild, check_minutes: int,
                                notification_time_before: int, yt_channel_url: str,
                                notification_channel: discord.TextChannel):

        ytube = BOT_CONFIG[server.id]['features']['ytube']
        task_to_run: tasks.Loop | None = ytube.get('task')

        if task_to_run is None:
            new_task = ytube['task'] = tasks.loop(minutes=check_minutes)(ytube_last_livestream)
            task_to_run = new_task
        if task_to_run.is_running():
            return False, logger_save_and_return_text(f"YT-Notificator is already running on {server.name}")
        else:

            ytube = ytube['settings']
            ytube['enable']['value'] = True
            ytube['repeat']['value'] = check_minutes
            ytube['notification_time']['value'] = notification_time_before
            ytube['yt_channel']['value'] = yt_channel_url
            ytube['channel_id']['value'] = notification_channel.id
            ytube['show_description']['value'] = False

            db_requests.server_update_settings(server, ytube)
            task_to_run.start(server, notification_channel, yt_channel_url)
            return True, logger_save_and_return_text(f"YT-Notificator is alive on {server.name}")

    async def task_ytube_stop(server: discord.Guild):
        ytube = BOT_CONFIG[server.id]['features']['ytube']
        task_to_run: tasks.Loop | None = ytube.get('task')

        if task_to_run is None:
            return False, logger_save_and_return_text(f"Nothing to stop on {server.name}")
        task_to_run.cancel()

        ytube['task'] = None
        ytube['settings']['enable']['value'] = False

        db_requests.server_update_settings(server, ytube['settings'])
        return True, logger_save_and_return_text(f"The loop is shut down on {server.name}")

    async def task_egsgames_create(server: discord.Guild, check_minutes: int, notification_channel: discord.TextChannel):
        egs_service = BOT_CONFIG[server.id]['features']['egs']
        task_to_run: tasks.Loop | None = egs_service.get('task')
        if task_to_run is None:
            new_task = egs_service['task'] = tasks.loop(minutes=check_minutes)(get_games)
            task_to_run = new_task
        if task_to_run.is_running():
            return False, logger_save_and_return_text(f"EGS-Notificator is already running on {server.name}")
        else:
            egs_service = egs_service['settings']
            egs_service['enable']['value'] = True
            egs_service['repeat']['value'] = check_minutes
            egs_service['channel_id']['value'] = notification_channel.id
            db_requests.server_update_settings(server, egs_service)
            task_to_run.start(server, notification_channel)
            return True, logger_save_and_return_text(f"EGS-Notificator is alive on {server.name}")

    async def task_egsgames_stop(server: discord.Guild):
        egs_service = BOT_CONFIG[server.id]['features']['egs']
        task_to_run: tasks.Loop | None = egs_service['task']

        if task_to_run is None:
            return False, logger_save_and_return_text(f"Nothing to stop on {server.name}")
        task_to_run.cancel()

        egs_service['task'] = None
        egs_service['settings']['enable']['value'] = False
        db_requests.server_update_settings(server, egs_service['settings'])
        return True, logger_save_and_return_text(f"EGS Notificator is shut down on {server.name}")

    # region Interactions
    # region SLASH_COMMANDS
    @bot.tree.command(name="help", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def custom_help(ctx: discord.Interaction):
        # await ctx.response.defer(ephemeral=False)
        emb = discord.Embed(title="BunnyByte FAQ", description="There are some commands that I can do for you.")
        # emb.set_footer(text="After 1 minute I'm leaving|Я скроюсь через миниту :)")
        if not await discord_is_owner(ctx, send_response=False):
            emb.add_field(name="-----[USER]-----", value=helpers.FAQ_USER, inline=False)
        else:
            emb.add_field(name="-----[SERVER]-----", value=helpers.FAQ_ADMIN, inline=False)
        emb.set_thumbnail(url=bot.user.avatar)
        await embed_output_server_message(ctx, embed_=emb)

        # LOOPS
        # region PARSER_YOUTUBE

    def update_match_ytube_list(server: discord.Guild):
        BOT_CONFIG[server.id]['match_ytube'] = db_requests.server_get_matching_ytube_list(server.id)

    async def ytube_last_livestream(server, channel_for_notification: discord.TextChannel, yt_channel_url: str):
        async def delete_notify_message(message_id):
            if message_id != "":
                notify_msg = await channel_for_notification.fetch_message(int(message_id))
                if notify_msg is not None:
                    await notify_msg.delete()

        # TODO: ChecksBeforeStart?
        yt_settings = BOT_CONFIG[server.id]['features']['ytube']['settings']
        server_ready = BOT_CONFIG[server.id]['ready']

        if not any([yt_settings['enable']['value'], server_ready]):
            logger.info("Bot or channel isn't ready for launching YT-notificator.")
            return

        yt_stream = await YTLiveStreamParser(yt_channel_url).get_last_livestream()
        if yt_stream is None:
            streams_to_delete = len([x for x in BOT_CONFIG[server.id]['match_ytube'].values()
                                     if x['status'] is YoutubeStreamStatus.NOTIFIED_ONLINE])
            if streams_to_delete > 0:
                db_requests.ytube_delete_finished_streams(server)
            logger.info(f"There's no stream. Channel:({yt_channel_url})")

            return
        logger.info(f"Fetching video info: {yt_stream.title}")

        video_id = yt_stream.video_id
        server_stream_data = BOT_CONFIG[server.id]['match_ytube']  # db_requests.ytube_get_streams_data(server.id)
        yt_stream.greeting = server_stream_data.get(video_id, {}).get('greeting', '')

        if video_id not in server_stream_data:
            video_status = YoutubeStreamStatus.UPCOMING if yt_stream.upcoming else YoutubeStreamStatus.ONLINE
            db_requests.ytube_save_video_to_dbase(server, yt_stream, video_status)
            server_stream_data[video_id] = yt_stream.get_video_info(video_status)
        else:
            local_video = server_stream_data[video_id]
            upcoming_date_ = local_video['upcoming_date']
            status_ = local_video['status']

            if yt_stream.upcoming:
                if yt_stream.upcoming_date != upcoming_date_:
                    await delete_notify_message(local_video['message_id'])
                    db_requests.ytube_update_upcoming_stream_date(server.id, video_id, yt_stream.upcoming_date)
                    local_video.update(yt_stream.get_video_info(YoutubeStreamStatus.UPCOMING))
            elif yt_stream.livestream:
                if status_ in [YoutubeStreamStatus.UPCOMING, YoutubeStreamStatus.NOTIFIED]:
                    db_requests.ytube_save_video_to_dbase(server, yt_stream, YoutubeStreamStatus.ONLINE, True)
                    local_video.update(yt_stream.get_video_info(YoutubeStreamStatus.ONLINE, local_video['message_id']))
        # TODO: Stream first iteration is online

        local_video = server_stream_data[video_id]
        if local_video['status'] is YoutubeStreamStatus.ONLINE:
            video_info, emb, view_ = yt_stream.get_discord_video_card()

            await delete_notify_message(local_video['message_id'])

            await channel_for_notification.send(content="@everyone", embed=emb, view=view_)
            db_requests.ytube_update_stream_status(server.id, video_id, YoutubeStreamStatus.NOTIFIED_ONLINE)
            db_requests.ytube_update_stream_message_id(server.id, video_id)
            local_video.update(yt_stream.get_video_info(YoutubeStreamStatus.NOTIFIED_ONLINE))
        elif local_video['status'] is YoutubeStreamStatus.UPCOMING:
            # TODO: Checking UpcomingStream
            notification_time = yt_settings['notification_time']['value']
            t_delta = (yt_stream.upcoming_date - utc_time_now()).total_seconds()
            stream_is_about_to_start = t_delta < notification_time * 60
            logger.info(f"{stream_is_about_to_start=}, {yt_stream.upcoming_date=}, utc=:{utc_time_now()}, "
                        f"notification time:{notification_time * 60}, delta=:{t_delta / 60}")
            if stream_is_about_to_start:
                # TODO: Change Video Status to NOTIFIED
                video_info, emb, view_ = yt_stream.get_discord_video_card()
                msg = await channel_for_notification.send(content="@everyone", embed=emb, view=view_)
                db_requests.ytube_update_stream_status(server.id, video_id, YoutubeStreamStatus.NOTIFIED)
                db_requests.ytube_update_stream_message_id(server.id, video_id, msg.id)
                local_video.update(yt_stream.get_video_info(YoutubeStreamStatus.NOTIFIED, msg.id))

        logger.info(f"Got video info: {local_video}")

    @commands_group_ytube.command(name="start", description="Enable YouTube Streams Notificator.", extras=DEFER_YES)
    @app_commands.describe(channel_url="YouTube Channel URL",
                           notification_channel="Discord channel for sending notifications.",
                           notification_time_before="Send upcoming stream notifications before X-time. Default = 5",
                           check_minutes="Check new stream every X minutes. Default = 15 | Min = 5")
    @discord_async_try_except_decorator
    async def ytube_service_start(ctx: discord.Interaction,
                                  notification_channel: discord.TextChannel,
                                  channel_url: str,
                                  notification_time_before: app_commands.Range[int, 5] = 10,
                                  check_minutes: app_commands.Range[int, 5] = 15):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, notification_channel, checks=[StartChecks.OWNER, StartChecks.REGISTRATION,
                                                           StartChecks.CHANNEL_EXIST,
                                                           StartChecks.CHANNEL_AVAILABLE]): return
        task_status, task_message = await task_ytube_create(server, check_minutes,
                                                            notification_time_before, channel_url,
                                                            notification_channel)
        await embed_output_server_message(ctx, task_message, True)

    @commands_group_ytube.command(name="stop", description="Disable YouTube Notificator.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def ytube_service_stop(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]): return
        task_status, task_message = await task_ytube_stop(server)
        await embed_output_server_message(ctx, task_message)

    @commands_group_ytube.command(name="restart", description="Restart YouTube Notificator.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def ytube_service_restart(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return
        task_message = 'YouTube is not ready'
        r = await check_bot_before_starting_tasks(server)
        if r['response']:
            # await task_ytube_restart(server, bot_channel)
            task_status, task_message = await task_ytube_restart(server)

        await embed_output_server_message(ctx, f"Restart: {task_message}")

    async def ytube_video_autocomplete(ctx: discord.Interaction, current: str, ) -> List[app_commands.Choice[str]]:
        server = ctx.guild
        if local_get_status(server.id) is ServerStatus.UNREGISTERED:
            return []
        video_list = BOT_CONFIG[server.id]['match_ytube']

        def return_stream_name(item):
            time_left = item['upcoming_date'] - utc_time_now()
            title = item['title']
            if len(title) > 50:
                title = f"{title[:50]}..."
            return f"{title} [Time Left: {helpers.strfdelta(tdelta=time_left)}]"

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
        if not await passed_checks_before_start_command(server, interaction, checks=[StartChecks.OWNER,
                                                                                     StartChecks.REGISTRATION]):
            return
        stream = BOT_CONFIG[server.id]['match_ytube'][video]
        stream['greeting'] = description
        db_requests.ytube_update_upcoming_stream_greeting(server.id, video, description)
        await embed_output_server_message(interaction, msg=f"Your greeting has been changed:\n"
                                                           f"Stream: **{stream['title']}**\n"
                                                           f"Greetings: **{description}**")

    # endregion

    # region PARSER_EGS

    async def get_games(server, notification_channel: discord.TextChannel):
        egs_settings = BOT_CONFIG[server.id]['features']['egs']['settings']
        server_ready = BOT_CONFIG[server.id]['ready']

        if not any([egs_settings['enable']['value'], server_ready]):
            logger.info("Bot or channel isn't ready for launching YT-notificator.")
            return
        # egs = EGSGamesParser()
        # egs = GamerPowerParser()
        # if egs.empty:
        #     return
        FREE_GAMES = BOT_CONFIG.get("FREE_GAMES", [])
        if not FREE_GAMES:
            return
        local_db = BOT_CONFIG[server.id]['match_egs']
        for egs_game in FREE_GAMES:
            if egs_game.id not in local_db:
                logger.info(f"Fetching game info: {egs_game.title}")
                game_info, emb, view_ = egs_game.get_discord_game_card()
                egs_games_save_to_dbase(server, egs_game, game_info)
                await notification_channel.send(embed=emb, view=view_)
                logger.info(f"Got game info: {egs_game.title}")

    @commands_group_egs.command(name="start", description="Enable EGS Notificator.", extras=DEFER_YES)
    @app_commands.describe(notification_channel="Channel for sending notifications.",
                           check_minutes="Check new games every X minutes. Default = 15")
    @discord_async_try_except_decorator
    async def egs_service_start(ctx: discord.Interaction,
                                notification_channel: discord.TextChannel,
                                check_minutes: app_commands.Range[int, 15] = 15):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, notification_channel,
                checks=[StartChecks.OWNER, StartChecks.REGISTRATION, StartChecks.CHANNEL_EXIST,
                        StartChecks.CHANNEL_AVAILABLE]):
            return

        task_status, task_message = await task_egsgames_create(server, check_minutes, notification_channel)
        await embed_output_server_message(ctx, task_message)

    @commands_group_egs.command(name="stop", description="Disable EGS Notificator.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def egs_service_stop(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return
        task_status, task_message = await task_egsgames_stop(server)
        await embed_output_server_message(ctx, task_message)

    @commands_group_egs.command(name="restart", description="Restart EGS Notificator.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def egs_service_restart(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return
        task_message = 'EGS is not ready'
        r = await check_bot_before_starting_tasks(server)
        if r['response']:
            # await task_ytube_restart(server, bot_channel)
            task_status, task_message = await task_egs_restart(server)

        await embed_output_server_message(ctx, f"Restart: {task_message}")

    # endregion
    group_test = app_commands.Group(name="bb_test", description="Testing slash groups")

    # region SPINWHEEL
    async def wheel_games_autocomplete(ctx: discord.Interaction, current: str, ) -> List[app_commands.Choice[str]]:
        server = ctx.guild
        if local_get_status(server.id) is ServerStatus.UNREGISTERED:
            return []
        games_list = BOT_CONFIG[server.id]['spin_wheel']
        return [app_commands.Choice(name=f"{game_status_dict[item['status']]['emoji']} {game}", value=game)
                for game, item in games_list.items() if
                current.lower() in game.lower()][:24]

    async def spinwheel_save_to_db(server, values_row: dict, action: SpinWheelAction):
        db_requests.spinwheel_save_to_server(server, values_row, action)

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
    async def spinwheel_add(interaction: discord.Interaction,
                            game: str,
                            status: SpinWheelGameStatus,
                            playlist: str = None, comment: str = None):
        server = interaction.guild
        if not await passed_checks_before_start_command(
                server, interaction, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return

        game_ = BOT_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is not None:
            await embed_output_server_message(interaction, f'This game is already in db **{game}**')
            return
        await spinwheel_save_to_db(server, {"game": game, "status": status, "url": playlist, "comment": comment},
                                   SpinWheelAction.Add)
        await embed_output_server_message(interaction, f'Your game has been added **{game}**', True)

    @commands_group_spinwheel.command(name="edit", description="Edit game in Spin Wheel.", extras=DEFER_YES)
    @app_commands.autocomplete(game=wheel_games_autocomplete)
    @app_commands.choices(status=game_status_choices)
    @app_commands.describe(game="Game from your Spin Wheel List.", name="Change name of game",
                           status="Game status | Default = Previous Status", playlist="Save YT-playlist Link.",
                           comment="Comment to current record. Type ! to wipe out.")
    @discord_async_try_except_decorator
    async def spinwheel_edit(interaction: discord.Interaction, game: str, name: str = None,
                             status: SpinWheelGameStatusEdit = SpinWheelGameStatusEdit.Previous,
                             playlist: str = None, comment: str = None):
        server = interaction.guild
        if not await passed_checks_before_start_command(
                server, interaction, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return

        game_ = BOT_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is None:
            await embed_output_server_message(interaction, msg=f'I don\'t have this game in db {game}')
            return

        status = game_['status'] if status is SpinWheelGameStatusEdit.Previous else SpinWheelGameStatus(status.value)
        playlist = game_['url'] if playlist is None else playlist
        comment = "" if comment == "!" else (game_['comment'] if comment is None else comment)
        name = game if name is None else name

        await spinwheel_save_to_db(server, {"game": game, "new_game": name, "status": status, "url": playlist,
                                            "comment": comment}, SpinWheelAction.Edit)
        await embed_output_server_message(interaction, msg=f'Your game has been changed **{game}**')

    @commands_group_spinwheel.command(name="delete", description="Delete a game from Spin Wheel.", extras=DEFER_YES)
    @app_commands.autocomplete(game=wheel_games_autocomplete)
    @app_commands.describe(game="Game to delete from your Spin Wheel List.")
    @discord_async_try_except_decorator
    async def spinwheel_delete(interaction: discord.Interaction, game: str):
        server = interaction.guild
        if not await passed_checks_before_start_command(
                server, interaction, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return

        game_ = BOT_CONFIG[server.id]['spin_wheel'].get(game)
        if game_ is None:
            await embed_output_server_message(interaction, msg=f'I don\'t have this game in db {game}')
            return
        await spinwheel_save_to_db(server, {"game": game, "status": None, "url": None}, SpinWheelAction.Delete)
        await embed_output_server_message(interaction, msg=f'Your has been deleted **{game}**')

    @commands_group_spinwheel.command(name="choice", description="Choice a game for playing.")
    @discord_async_try_except_decorator
    async def spinwheel_choice(interaction: discord.Interaction):
        server = interaction.guild
        if not await passed_checks_before_start_command(
                server, interaction, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return

        game_list = [{"game": game, "status": item['status'], "url": item['url'], "comment": item['comment']}
                     for game, item in BOT_CONFIG[server.id]['spin_wheel'].items()
                     if item['status'] is SpinWheelGameStatus.InList]
        if not game_list:
            await embed_output_server_message(interaction, f'The Game List is empty.')
            return
        game_ = random.choice(game_list)
        await spinwheel_save_to_db(server, {"game": game_['game'], "new_game": game_['game'],
                                            "status": SpinWheelGameStatus.InProgress,
                                            "url": game_["url"], "comment": game_["comment"]}, SpinWheelAction.Edit)
        emb = discord.Embed(
            title="Уразайка-Поиграйка!"
        )
        emb.add_field(name="Пора играть:", value=f"**{game_['game']}**", inline=False)
        emb.set_footer(text=game_["comment"])
        emb.set_thumbnail(url='https://cdn-icons-png.flaticon.com/256/9217/9217857.png')
        await interaction.edit_original_response(embed=emb)

    @commands_group_spinwheel.command(name="poll", description="Create a poll.", extras={'use_defer': False})
    @app_commands.describe(count="How many games do you want to choose? Default = 3",
                           streams="Is it a list 'Games for Stream'? Default = No",
                           defer="Visible only for you")
    @discord_async_try_except_decorator
    async def spinwheel_poll(interaction: discord.Interaction, count: app_commands.Range[int, 1, 5] = 3,
                             streams: SettingYesNo = SettingYesNo.Yes,
                             defer: SettingYesNo = SettingYesNo.Yes):
        server = interaction.guild
        if not await passed_checks_before_start_command(
                server, interaction, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return
        GameListFilter = SpinWheelGameStatus.InList if streams is SettingYesNo.No else SpinWheelGameStatus.InListStream
        game_list = [{"game": game, "status": item['status'], "url": item['url'], "comment": item['comment']}
                     for game, item in BOT_CONFIG[server.id]['spin_wheel'].items()
                     if item['status'] is GameListFilter]
        if not game_list:
            await embed_output_server_message(interaction, f'The Game List is empty.')
            return

        # await spinwheel_save_to_db(server, {"game": game_['game'], "new_game": game_['game'],
        #                                     "status": SpinWheelGameStatus.InProgress,
        #                                     "url": game_["url"], "comment": game_["comment"]}, SpinWheelAction.Edit)

        emb = discord.Embed(
            title="Уразайка-Поиграйка!",
            description="Пора выбирать, во что поиграть."
        )
        for _ in range(count):
            if not game_list:
                break
            game_ = random.choice(game_list)
            emb.add_field(name=f"Вариант {_ + 1}:", value=f"**{game_['game']}**", inline=False)
            game_list.remove(game_)
        # emb.set_footer(text=game_["comment"])
        emb.set_thumbnail(url='https://cdn-icons-png.flaticon.com/256/9217/9217844.png')
        await interaction.response.defer(ephemeral=defer.value)
        await interaction.edit_original_response(embed=emb)

    class Select(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label=x['name'], value=str(x['value']), emoji=x['emoji'])
                for x in game_status_dict.values()
            ]
            super().__init__(placeholder="Select an option", max_values=len(game_status_dict), min_values=1,
                             options=options)

        async def callback(self, interaction: discord.Interaction):
            # await interaction.response.defer(ephemeral=True)
            params = BOT_CONFIG[interaction.guild.id]['category_filter'][interaction.user.id]
            descript, search = params['descript'], params['search']
            defer, list_view = params['defer'], params['list_view']
            await interaction.response.defer(ephemeral=defer)
            del params
            del BOT_CONFIG[interaction.guild.id]['category_filter'][interaction.user.id]
            await spinwheel_show(interaction, descript=descript, search=search, filter=''.join(self.values),
                                 defer=defer, list_view=list_view)

    class CategoryFilter(discord.ui.View):
        def __init__(self, *, timeout=180):
            super().__init__(timeout=timeout)
            self.add_item(Select())

    @commands_allowed_to_user.command(name="show_spin_wheel", description="Show Spin the Wheel.", extras=DEFER_YES)
    @app_commands.describe(descript="Show Spin Wheel List Rules.",
                           search="Searching query",
                           category_filter="Show up category filter",
                           list_view="Table View")
    @discord_async_try_except_decorator
    async def show_spin_wheel(interaction: discord.Interaction,
                              category_filter: SettingYesNo = SettingYesNo.No,
                              search: app_commands.Range[str, 3] = None,
                              descript: SettingYesNo = SettingYesNo.No,
                              list_view: SettingYesNo = SettingYesNo.No):

        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction,
                                                        checks=[StartChecks.REGISTRATION]):
            return
        if category_filter is SettingYesNo.Yes:
            # await interaction.response.defer(ephemeral=True)
            BOT_CONFIG[server.id]['category_filter'] = {
                interaction.user.id: {"descript": descript, "search": search, "defer": True,
                                      "list_view": list_view.value}}
            await interaction.edit_original_response(view=CategoryFilter())
        else:
            await spinwheel_show(interaction, descript=descript, search=search, list_view=list_view.value)

    @commands_group_spinwheel.command(name="show", description="Show Spin the Wheel.", extras=DEFER_YES)
    @app_commands.describe(descript="Show Spin Wheel List Rules.",
                           search="Searching query",
                           category_filter="Show up category filter",
                           # defer="Message is Visible only for you.",
                           list_view="Table View")
    @discord_async_try_except_decorator
    async def spinwheel_show_wheel(interaction: discord.Interaction,
                                   descript: SettingYesNo = SettingYesNo.No,
                                   # defer: bool = True,
                                   category_filter: SettingYesNo = SettingYesNo.No,
                                   search: app_commands.Range[str, 3] = None,
                                   list_view: SettingYesNo = SettingYesNo.No):

        server = interaction.guild
        if not await passed_checks_before_start_command(server, interaction, checks=[StartChecks.REGISTRATION]):
            return
        if category_filter is SettingYesNo.Yes:
            # await interaction.response.defer(ephemeral=defer)
            BOT_CONFIG[server.id]['category_filter'] = {
                interaction.user.id: {"descript": descript, "search": search, "defer": True,
                                      "list_view": list_view.value}}
            await interaction.edit_original_response(view=CategoryFilter())
        else:
            await spinwheel_show(interaction, descript=descript, search=search, list_view=list_view.value)

    async def spinwheel_show(interaction: discord.Interaction, **kwargs):
        server = interaction.guild
        list_view = bool(kwargs.get('list_view', 0))
        search = kwargs.get('search', None)
        filter_category = kwargs.get('filter', [e.value for e in SpinWheelGameStatus])
        is_admin = interaction.user.guild_permissions.administrator
        if isinstance(filter_category, str):
            filter_category = [int(char) for char in filter_category]
        filter_category.sort()

        games_list = [{"game": game, "status": item['status'], "url": item['url'], "comment": item['comment']} for
                      game, item in BOT_CONFIG[server.id]['spin_wheel'].items() if
                      item['status'].value in filter_category and (
                          True if search is None else game.lower().find(search.lower()) != -1)]

        filter_category_and_search = set(x['status'].value for x in games_list)
        embeds_dict = {item['value']: {"info": item, "game_list": [], } for item in game_status_dict.values() if
                       item['value'] in filter_category_and_search}

        if not games_list:
            await embed_output_server_message(interaction, f'The Game List is empty.')
            return

        for game in games_list:
            embeds_dict[game['status'].value]['game_list'].append(game)

        messages = [Paginator(server, emb['game_list'], emb['info'], True, is_admin, list_view, ) for emb in
                    embeds_dict.values()]

        await asyncio.sleep(1)

        descript = kwargs.get('descript')
        if descript is SettingYesNo.Yes:
            description_ = SPINWHEEL_RULES if descript is SettingYesNo.Yes else ''
            emb = discord.Embed(title="Рулетка Уразайки-Поиграйки!", description=description_)
            emb.set_thumbnail(url='http://samyukthascans.com/images/icon/spin.gif')
            await interaction.edit_original_response(embed=emb, view=None)

        for message in messages:
            await interaction.followup.send(embed=message.current_emb, view=message.view, ephemeral=True)

        # endregion

    @commands_allowed_to_user.command(name="joke", description="Do you wanna hear a joke 😜?", extras=DEFER_YES)
    @app_commands.checks.cooldown(1, 10)
    @discord_async_try_except_decorator
    async def tell_joke(ctx: discord.Interaction):
        dads_joke = await joke.DadJoke().get_joke()
        emb = discord.Embed(title="Dad\'s Joke 🎅")
        emb.add_field(name="Joke", value=dads_joke)
        emb.set_thumbnail(url=bot.user.avatar)
        await ctx.edit_original_response(embed=emb)

    @tell_joke.error
    async def on_tell_joke_error(ctx: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await ctx.response.send_message(embed=discord.Embed(
                title="Wow, slow down, mate", description=f"Take your time, mate! {str(error)}"), ephemeral=True)

    # region SC_SERVER
    @commands_group_server.command(name="info", description="Show SERVER info.", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def server_info(ctx: discord.Interaction):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, checks=[StartChecks.OWNER, ]):
            return

        bot_channel = bot.get_channel(local_get_bot_channel(server.id))
        bot_channel_name = None if bot_channel is None else bot_channel.name

        egs_info = "Not found"
        ytube_info = "Not found"

        if local_get_status(server.id) is ServerStatus.REGISTERED:
            egs_task = BOT_CONFIG[server.id]['features']['egs']['task']
            ytube_task = BOT_CONFIG[server.id]['features']['ytube']['task']
            if egs_task is not None:
                egs_info = f"Task has been found: Next launch (GMT): " \
                           f"{datetime.strftime(egs_task.next_iteration, '%d.%m.%y %H:%M')}"
            if ytube_task is not None:
                ytube_info = f"Task has been found: Next launch (GMT): " \
                             f"{datetime.strftime(ytube_task.next_iteration, '%d.%m.%y %H:%M')}"
        emb = discord.Embed(title="SERVER-INFO", )
        emb.add_field(name="Name", value=f"[**{ctx.guild.name}**]")
        emb.add_field(name="ID", value=f"[**{ctx.guild.id}**]")
        emb.add_field(name="Status", value=f"[**{BOT_CONFIG[server.id]['status'].name}**]", inline=False)
        emb.add_field(name="Service channel", value=f"[**{bot_channel_name}**]")
        emb.add_field(name="EGS-notificator", value=f"[**{egs_info}**]", inline=False)
        emb.add_field(name="YouTube-notificator", value=f"[**{ytube_info}**]", inline=False)
        emb.set_thumbnail(url=bot.user.avatar)
        await ctx.edit_original_response(embed=emb)

    @commands_group_server.command(name="change_channel",
                                   description="Change service (private) channel for notifications from bot.",
                                   extras=DEFER_YES)
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @discord_async_try_except_decorator
    async def server_change_channel(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, bot_channel,
                checks=[StartChecks.OWNER, StartChecks.REGISTRATION, StartChecks.CHANNEL_EXIST,
                        StartChecks.CHANNEL_AVAILABLE, ]):
            return

        if bot_channel.id == local_get_bot_channel(server.id):
            await embed_output_server_message(ctx,
                                              "Hey, Bunny! You are giving me the same channel. Are you alright? :)",
                                              True)
            return
        db_requests.server_change_service_channel(server, bot_channel)
        BOT_CONFIG[server.id]['bot_channel'] = bot_channel.id
        await embed_output_server_message(
            ctx, f"It's done. **{bot_channel.name}** now is your new service channel.", True)

    @commands_group_server.command(name="signup",
                                   description="Register the bot. You need to create a private channel "
                                               "(mute) & give me permission.",
                                   extras=DEFER_YES)
    @app_commands.describe(bot_channel='Service (Private) Channel for sending messages from bot.')
    @discord_async_try_except_decorator
    async def server_signup(ctx: discord.Interaction, bot_channel: discord.TextChannel):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, bot_channel, checks=[StartChecks.OWNER, StartChecks.CHANNEL_EXIST,
                                                  StartChecks.CHANNEL_AVAILABLE, StartChecks.ALREADY_REGISTERED, ]):
            return

        # Making a registration
        logger.info(f"Creating server row for [**{server.name}**]:[**{server.id}**]...")
        await db_requests.server_signup(server, bot_channel)

        BOT_CONFIG[server.id]['status'] = ServerStatus.REGISTERED
        BOT_CONFIG[server.id]['ready'] = True
        BOT_CONFIG[server.id]['bot_channel'] = bot_channel.id
        BOT_CONFIG[server.id]['features'] = db_requests.server_get_settings(server.id)

        await embed_output_server_message(
            ctx, f"Your Server [**{server.name}**]:[**{server.id}**] has been registered. Congrats!.", True)

    @commands_group_server.command(name="delete",
                                   description="Delete server from bot' database. **All your setting will be lost.**",
                                   extras=DEFER_YES)
    @app_commands.describe(confirm="In order to check your decision.")
    @discord_async_try_except_decorator
    async def server_delete(ctx: discord.Interaction, confirm: SettingYesNo):
        server = ctx.guild
        if not await passed_checks_before_start_command(
                server, ctx, checks=[StartChecks.OWNER, StartChecks.REGISTRATION]):
            return

        if confirm is SettingYesNo.No:
            await embed_output_server_message(ctx, "Command has been canceled.")
            return

        db_requests.server_delete_bot_registration(server.id)
        local_flush_server_settings(server)
        await embed_output_server_message(
            ctx, f"Your Server [**{server.name}**]:[**{server.id}**] has been deleted.")

    @commands_group_server.command(name="flush", extras=DEFER_YES)
    @discord_async_try_except_decorator
    async def flush_setting(ctx: discord.Interaction, password: str):
        if password == '!Space@Monkey#':
            local_flush_server_settings(ctx.guild)
            await bot_load_settings(ctx.guild)
            await embed_output_server_message(ctx, msg="Done")
        else:
            await embed_output_server_message(ctx, msg="Never guess 😜")

    # endregion

    async def bot_say_hi_to_registered_server(server: discord.Guild, bot_channel_id):
        if bot.is_ready() and local_get_status(server.id) is ServerStatus.REGISTERED and bot_channel_id is not None:
            try:
                if not BOT_CONFIG[server.id]['ready']:
                    return
                bot_channel = bot.get_channel(bot_channel_id)
                if bot_channel is None:
                    owner = server.owner
                    await owner.send(
                        f"**{owner.name}** A зачем канал удалили для сервисных сообщений на **{server.name}**? ")
                    return
                await bot_channel.send(content=logger_save_and_return_text(
                    f"Hi! **{BOT_CONFIG[server.id]['name']}** SERVER. I'm online!!!"))
            except discord.errors.Forbidden as e:
                logger.info(
                    f"I have a service channel on {server.id}, but I have no rights. Just skipping this carrotbutt.")

    # endregion

    async def send_message_to_server_owner(server: discord.Guild, message: str = None):
        owner = server.owner
        if message is None:
            message = f"**{owner.name}** A канал для сервисных сообщений на **{server.name}** недоступен. "
        await owner.send(content=message)

    async def task_egs_restart(server: discord.Guild, bot_channel: discord.TextChannel = None):
        egs_service = BOT_CONFIG[server.id]["features"]["egs"]
        egs_settings = egs_service["settings"]

        if egs_settings['enable']['value']:
            egs_service['task'] = None
            egs_channel = bot.get_channel(int(egs_settings['channel_id']['value']))

            if egs_channel is None:
                text = 'You don\'n have a channel for fetching data from EGS.'
                if bot_channel is None:  # Launched by slash command
                    return False, logger_save_and_return_text(text)
                else:  # Launched by task manager
                    await bot_channel.send(text)
                    return
            BOT_CONFIG[server.id]['match_egs'] = db_requests.server_get_matching_egs_list(server.id)
            task_status, task_message = await task_egsgames_create(
                server=server, check_minutes=int(egs_settings['repeat']['value']),
                notification_channel=egs_channel)
            if bot_channel is None:
                return task_status, task_message
            else:
                await bot_channel.send(content=task_message)
        else:
            if bot_channel is None:
                return False, logger_save_and_return_text('Service EGS is not ready')

    async def task_ytube_restart(server: discord.Guild, bot_channel: discord.TextChannel = None):
        ytube_service = BOT_CONFIG[server.id]["features"]["ytube"]
        ytube_settings = ytube_service["settings"]
        if ytube_settings['enable']['value']:
            ytube_service['task'] = None
            ytube_channel = bot.get_channel(int(ytube_settings['channel_id']['value']))

            if ytube_channel is None:
                text = 'You don\'n have a channel for fetching data from Youtube.'
                if bot_channel is None:  # Launched by slash command
                    return False, logger_save_and_return_text(text)
                else:  # Launched by task manager
                    await bot_channel.send(text)
                    return
            BOT_CONFIG[server.id]['match_ytube'] = db_requests.server_get_matching_ytube_list(server.id)
            task_status, task_message = await task_ytube_create(
                server=server, check_minutes=int(ytube_settings['repeat']['value']),
                notification_channel=ytube_channel,
                notification_time_before=ytube_settings['notification_time']['value'],
                yt_channel_url=ytube_settings['yt_channel']['value'])
            if bot_channel is None:
                return task_status, task_message
            else:
                await bot_channel.send(content=task_message)
        else:
            if bot_channel is None:
                return False, logger_save_and_return_text('Service YouTube is not ready')

    async def check_bot_before_starting_tasks(server: discord.Guild):
        server_ready = BOT_CONFIG[server.id]['ready']
        bot_channel = bot.get_channel(BOT_CONFIG[server.id]['bot_channel'])
        result = {"response": False, "bot_channel": bot_channel}
        if server_ready:
            if bot_channel is not None:
                result.update({"response": True})
            else:
                db_requests.server_update_bot_ready(server, False)
                BOT_CONFIG[server.id]['ready'] = False
                await send_message_to_server_owner(server)
        return result

    async def run_services_task(server: discord.Guild):
        r = await check_bot_before_starting_tasks(server)
        if r['response']:
            bot_channel = r['bot_channel']
            await task_ytube_restart(server, bot_channel)
            await task_egs_restart(server, bot_channel)

    # region BOT_LOOP_TASKS
    @tasks.loop(hours=1)
    async def bot_task_get_free_games_list():
        logger.info(f"Starting task 'Get Free Games'")
        BOT_CONFIG.update({"FREE_GAMES": GamerPowerParser().free_games})
        logger.info(f"End a loop of task 'Get Free Games'")

    @tasks.loop(hours=3)
    async def bot_task_delete_old_data():
        logger.info(f"Starting task 'Delete obsolete data' on DataBase")
        MYSQL = mysql.MYSQL()
        MYSQL.execute("DELETE FROM egs_games WHERE CONVERT_TZ(NOW(), 'System', 'GMT') > exp_date")
        MYSQL.execute("DELETE FROM yt_videos WHERE `status` = %s", values=YoutubeStreamStatus.FINISHED.value)
        MYSQL.commit(True)
        logger.info(f"Old data have been deleted on DataBase")

    # endregion

    @bot.event
    async def on_guild_channel_delete(deleted_channel):
        if isinstance(deleted_channel, discord.TextChannel):
            server = deleted_channel.guild
            if local_get_status(server.id) is ServerStatus.UNREGISTERED:
                return
            bot_channel_id = BOT_CONFIG[server.id]['bot_channel']
            if deleted_channel.id == bot_channel_id:
                await task_ytube_stop(server)
                await task_egsgames_stop(server)
                db_requests.server_update_bot_ready(server, False)
                await send_message_to_server_owner(server,
                                                   f"Канал для сервисных сообщений на **{server.name}** недоступен."
                                                   f"Серверные задачи приостановлены.")
                return
            else:
                task_message = None
                bot_channel = bot.get_channel(bot_channel_id)
                if deleted_channel.id == BOT_CONFIG[server.id]['features']['egs']['settings']['channel_id']['value']:
                    task_status, task_message = await task_egsgames_stop(server)
                if deleted_channel.id == BOT_CONFIG[server.id]['features']['ytube']['settings']['channel_id']['value']:
                    task_status, task_message = await task_ytube_stop(server)
                if task_message is not None and BOT_CONFIG[server.id]['ready']:
                    await bot_channel.send(content=task_message)

    @bot.event
    async def on_guild_join(server: discord.Guild):
        await bot.tree.sync()
        await prepare_guild(server)

    async def prepare_guild(server: discord.Guild):
        if server.id not in BOT_CONFIG:
            for group in [commands_group_ytube, commands_group_egs, commands_group_spinwheel,
                          commands_group_server, commands_allowed_to_user]:
                bot.tree.add_command(group, guild=server)
            await asyncio.sleep(1)
            await bot.tree.sync(guild=server)
            await bot_load_settings(server)
            if (bot_channel := BOT_CONFIG[server.id]['bot_channel']) is not None:
                pass# await bot_say_hi_to_registered_server(server, bot_channel)
            # Check LOOPS here
            await run_services_task(server)
            logger.info(f"Server:[{server.name}]:[{server.id}]")

    @bot.event
    async def on_guild_remove(server: discord.Guild):
        if server.id in BOT_CONFIG:
            await task_ytube_stop(server)
            await task_egsgames_stop(server)
            db_requests.server_delete_bot_registration(server.id)
            del BOT_CONFIG[server.id]

    async def start_bot_tasks():
        bot_task_get_free_games_list.start()
        bot_task_delete_old_data.start()

    @bot.event
    async def on_ready():
        await bot.wait_until_ready()
        logger.info(f"Logged in as {bot.user.name}({bot.user.id})")
        logger.info(f"Synchronizing bot tree...")
        await bot.tree.sync()
        logger.info(f"Synchronizing has been finished.")
        logger.info(f"Launch bot tasks...")
        await start_bot_tasks()
        logger.info(f"Done.")
        logger.info(f"Prepare guilds...")
        for server in bot.guilds:
            await prepare_guild(server)
        logger.info(f"Done...")

    async def bot_load_settings(server):
        # local_flush_server_settings(server.id)
        if server.id in BOT_CONFIG:
            logger.info(f'Settings have been loaded already for [{server.name}, {server.id}]')
            return
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

    bot.run(token=config.BUNNYBYTE_TOKEN)


if __name__ == "__main__":
    discord_bot()
