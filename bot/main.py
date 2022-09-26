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
from yt_parser import YTParser
from egs_parser import EGSGamesParser, EGSGame

# endregion

TIME_DELAY = 60 * 60 * 12
SERVER_TASKS = dict()
BOT_LOCAL_CONFIG = dict()


# bot_settings = dict()
# games_from_file = []
# egs_obj = EGSGamesParser()


def is_user_admin(ctx: commands.Context | Interaction):
    return ctx.author.guild_permissions.administrator


def discord_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='.', intents=intents)
    bot.remove_command('help')

    # region Interactions

    @bot.tree.command()
    async def hello(interaction: discord.Interaction):
        """Says hello!"""
        await interaction.response.send_message(f'Hi, {interaction.user.mention}')

    class SettingSwitcher(Enum):
        Enable = 1
        Disable = 0

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
    @bot.tree.context_menu(name='Show Join Date')
    async def show_join_date(interaction: discord.Interaction, member: discord.Member):
        # The format_dt function formats the date time into a human readable representation in the official client
        await interaction.response.send_message(f'{member} joined at {discord.utils.format_dt(member.joined_at)}')

    # This context menu command only works on messages
    @bot.tree.context_menu(name='Report to Moderators')
    async def report_message(interaction: discord.Interaction, message: discord.Message):
        # We're sending this response message with ephemeral=True, so only the command executor can see it
        await interaction.response.send_message(
            f'Thanks for reporting this message by {message.author.mention} to our moderators.', ephemeral=True
        )

        # Handle report by sending it into a log channel
        log_channel = interaction.guild.get_channel(0)  # replace with your channel id

        embed = discord.Embed(title='Reported Message')
        if message.content:
            embed.description = message.content

        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.timestamp = message.created_at

        url_view = discord.ui.View()
        url_view.add_item(discord.ui.Button(label='Go to Message', style=discord.ButtonStyle.url, url=message.jump_url))

        await log_channel.send(embed=embed, view=url_view)

    # region SLASH_COMMANDS
    async def delete_discord_message(msg: discord.Message | discord.Interaction, delete_after_sec: int = 3):
        await asyncio.sleep(delete_after_sec)
        if isinstance(msg, discord.Message):
            await msg.delete()
        elif isinstance(msg, discord.Interaction):
            await msg.delete_original_response()

    # region SC_SERVER
    @bot.tree.command(name="server_info")
    @commands.has_permissions(administrator=True)
    async def server_info(ctx: Interaction):
        # if is_user_admin(ctx):
        server = ctx.guild
        try:
            emb = discord.Embed(
                title="SERVER-INFO",
                description=f"Name: [**{ctx.guild.name}**]\n"
                            f"ID: [**{ctx.guild.id}**]\n"
                            f"Status: [**{BOT_LOCAL_CONFIG[str(server.id)]['status'].name}**]"
            )
            await ctx.response.send_message(embed=emb)
            await delete_discord_message(ctx, 10)
        except Exception as e:
            await ctx.response.send_message(
                f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.tree.command(name="server_delete")
    @commands.has_permissions(administrator=True)
    async def server_delete(ctx: Interaction):
        # if is_user_admin(ctx):
        server = ctx.guild
        MYSQL = mysql.MYSQL()
        try:
            MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
            if MYSQL.empty:
                await ctx.response.send_message(
                    f"Your Server [**{server.name}**]:[**{server.id}**] hasn't been registered. Aborted.")
                await delete_discord_message(ctx)
                return
            MYSQL.execute(f"DELETE FROM servers WHERE `id`='{server.id}'")
            MYSQL.commit(True)
            BOT_LOCAL_CONFIG[str(server.id)]['status'] = ServerStatus.UNREGISTERED
            await ctx.response.send_message(
                f"Your Server [**{server.name}**]:[**{server.id}**] has been deleted.")
            await delete_discord_message(ctx, 10)
        except Exception as e:
            await ctx.response.send_message(
                f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    # endregion
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

    # endregion

    # endregion
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
            # inserted_video_id = MYSQL.cursor.lastrowid
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
    @commands.has_permissions(administrator=True)
    async def server_info(ctx: commands.Context):
        # if is_user_admin(ctx):
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
            await ctx.send(msg, delete_after=10)
        except Exception as e:
            await ctx.send(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.command(name="server_signup", aliases=['server-register'])
    @commands.has_permissions(administrator=True)
    async def server_signup(ctx: commands.Context, bot_channel: discord.TextChannel | None):
        # if is_user_admin(ctx):
        server = ctx.guild
        MYSQL = mysql.MYSQL()
        if bot_channel is None:
            await ctx.send(
                content="Use this command! .server-registered #your-service-channel-for-bot.",
                delete_after=3,
                ephemeral=True)
            return
        try:
            MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`='{server.id}'")
            if not MYSQL.empty:
                await ctx.send(f"You're already here [**{server.name}**]:[**{server.id}**]", delete_after=5)
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
            await ctx.send(f"Your Server [**{server.name}**]:[**{server.id}**] has been registered. Congrats!.",
                           delete_after=5)
        except Exception as e:
            await ctx.send(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.command(name="server_delete", aliases=['server-delete'])
    @commands.has_permissions(administrator=True)
    async def server_delete(ctx: commands.Context):
        # if is_user_admin(ctx):
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
            BOT_LOCAL_CONFIG[str(server.id)]['status'] = ServerStatus.UNREGISTERED
            await ctx.send(f"Your Server [**{server.name}**]:[**{server.id}**] has been deleted.", delete_after=10)

        except Exception as e:
            await ctx.send(f"Something went wrong [{e}]. Try again or send me a message and we will do something.")

    @bot.command(name="custom_help", aliases=["help"])
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

    class ServerStatus(Flag):
        REGISTERED = True
        UNREGISTERED = False

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

    @bot.event
    async def on_ready():
        await bot.wait_until_ready()
        await bot.tree.sync()

        print(f"Logged in as {bot.user.name}({bot.user.id})")
        for server in bot.guilds:
            server_id = str(server.id)
            BOT_LOCAL_CONFIG[server_id] = {
                'id': server_id,
                'name': server.name,
                'status': server_get_status(server.id),
                'tasks': [],
            }
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
    discord_bot()
