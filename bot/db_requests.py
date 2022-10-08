import asyncio
from discord import Guild, TextChannel
import mysql
from enums import *
from helpers import (
    simple_try_except_decorator, logger
)
from spinwheel_games import (
    SpinWheelGameStatus, SpinWheelAction
)
from yt_parser import (YoutubeStreamStatus, YouTubeLiveStream)


@simple_try_except_decorator
def server_get_status(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(f"SELECT * FROM `servers` WHERE `id`=%s", values=server_id)
    MYSQL.close()
    return ServerStatus(not MYSQL.empty)


@simple_try_except_decorator
def server_get_bot_channels():
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(f"SELECT service_channel, ready FROM `bot_config`")
    MYSQL.close()
    if MYSQL.empty:
        return list() if MYSQL.empty else int(MYSQL.data)


@simple_try_except_decorator
def server_get_bot_settings(server_id: int | str = None):
    # LOCAL_SETTING = BOT_LOCAL_CONFIG.get('bot_channels')
    # if LOCAL_SETTING is not None:
    #     return server_id if server_id in LOCAL_SETTING else None
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(f"SELECT service_channel, ready FROM `bot_config` WHERE `server_id`=%s", values=server_id)
    MYSQL.close()
    if MYSQL.empty:
        return None, False
    else:
        return int(MYSQL.data[0]['service_channel']), bool(MYSQL.data[0]['ready'])


@simple_try_except_decorator
def server_update_bot_ready(server: Guild, value):
    MYSQL = mysql.MYSQL()
    MYSQL.execute("UPDATE `bot_config` SET `ready` = %s WHERE `server_id` = %s", values=(value, server.id))
    MYSQL.commit(True)


@simple_try_except_decorator
def server_get_settings(server_id: int | str = None):
    def return_setting_dict(feature_name: str):
        return {x['name']: x for x in (item for item in MYSQL.data if item['fname'] == feature_name)}

    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT settings.name, srv_config.value, settings.`type`, "
                   "settings.description, features.name AS fname\n"
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
def server_get_matching_ytube_list(server_id: int | str = None):
    def return_dict():
        def get_sub_dict(key, item):
            if key == 'status':
                return YoutubeStreamStatus(item)
            else:
                return item
        return {row['video_id']: {key: get_sub_dict(key, item) for key, item in row.items()} for row in MYSQL.data}

    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT `video_id`, `title`, `author`, `publish_date`, `upcoming_date`,"
                   "`thumbnail_url`, `watch_url`, `description`, `greeting`, `upcoming`, `livestream`, `status` "
                   "FROM yt_videos WHERE server_id = %s",
        values=server_id
    )
    MYSQL.close()
    return {} if MYSQL.empty else return_dict()


@simple_try_except_decorator
def server_get_matching_egs_list(server_id: int | str = None):
    def return_dict():
        return {item['game_id']: item for item in MYSQL.data}

    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT `game_id`, `title`, `description`, `url`, `exp_date`, `thumbnail` "
                   "FROM egs_games WHERE server_id = %s",
        values=server_id
    )
    MYSQL.close()
    return {} if MYSQL.empty else return_dict()


@simple_try_except_decorator
def server_get_spinwheel_list(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT game, status, url, comment FROM spin_wheel WHERE server_id = %s ORDER BY `status`, game",
        values=server_id
    )
    MYSQL.close()
    return dict() if MYSQL.empty else {x['game']: {"status": SpinWheelGameStatus(x['status']),
                                                   "url": x['url'],
                                                   "comment": x['comment']} for x in MYSQL.data}


@simple_try_except_decorator
def server_delete_bot_registration(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.execute(f"DELETE FROM servers WHERE `id`= %s", values=server_id)
    MYSQL.commit(True)


@simple_try_except_decorator
def server_signup(server: Guild, bot_channel: TextChannel):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(f"SELECT * FROM `settings`")
    features = MYSQL.data
    asyncio.sleep(1)

    MYSQL.execute(
        user_query=f"INSERT INTO servers (`id`, `name`) VALUES (%s, %s)",
        values=(server.id, server.name)
    )
    logger.info(f"Creating settings for [**{server.name}**]:[**{server.id}**]...")
    user_query = f"INSERT INTO srv_config (`server_id`, `setting_id`, `value`) VALUES (%s, %s, %s) "
    value_list = [(server.id, feature['id'], (False if feature['type'] == 'bool' else None)) for feature in features]
    # MYSQL.commit()
    MYSQL.executemany(user_query, value_list)
    MYSQL.execute('INSERT INTO bot_config (service_channel, server_id, ready) VALUES (%s, %s, %s)',
                  values=(bot_channel.id, server.id, True))
    asyncio.sleep(1)
    MYSQL.commit(True)


@simple_try_except_decorator
def server_change_service_channel(server: Guild, bot_channel: TextChannel):
    MYSQL = mysql.MYSQL()
    MYSQL.execute("UPDATE bot_config SET `service_channel` = %s WHERE `server_id` = %s",
                  values=(bot_channel.id, server.id))
    MYSQL.commit()


@simple_try_except_decorator
def ytube_update_upcoming_stream_greeting(server_id, video_id, description):
    MYSQL = mysql.MYSQL()
    MYSQL.execute(
        user_query="UPDATE yt_videos SET `greeting` = %s WHERE `video_id` = %s and `server_id` = %s",
        values=(description, video_id, server_id)
    )
    MYSQL.commit(True)


@simple_try_except_decorator
def ytube_update_upcoming_stream_date(server_id, video_id, upcoming_date):
    MYSQL = mysql.MYSQL()
    MYSQL.execute(
        user_query="UPDATE yt_videos SET `upcoming_date` = %s WHERE `video_id` = %s and `server_id` = %s",
        values=(upcoming_date, video_id, server_id)
    )
    MYSQL.commit(True)


@simple_try_except_decorator
def ytube_update_stream_status(server_id, video_id, status: YoutubeStreamStatus):
    MYSQL = mysql.MYSQL()
    MYSQL.execute(
        user_query="UPDATE yt_videos SET `status` = %s WHERE `video_id` = %s and `server_id` = %s",
        values=(status.value, video_id, server_id)
    )
    MYSQL.commit(True)


@simple_try_except_decorator
def ytube_get_streams_data(server_id):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(user_query="SELECT * FROM yt_videos WHERE `server_id` = %s", values=server_id)
    return {video['video_id']: video for video in MYSQL.data}


@simple_try_except_decorator
def ytube_get_streams_data(server_id, video_id):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(user_query="SELECT * FROM yt_videos WHERE `video_id` = %s, `server_id` = %s",
                   values=(video_id, server_id))
    return {video['video_id']: video for video in MYSQL.data}


@simple_try_except_decorator
def ytube_save_video_to_dbase(server: Guild, yt_stream: YouTubeLiveStream,
                              status: YoutubeStreamStatus, is_update: bool = False):
    MYSQL = mysql.MYSQL()
    if not is_update:
        MYSQL.execute(
            user_query="INSERT INTO yt_videos "
                       "(`server_id`,`video_id`, `title`, `author`, `publish_date`, "
                       "`upcoming_date`, `thumbnail_url`, `watch_url`, "
                       "`description`, `greeting` `upcoming`, `livestream`, `status`) "
                       "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            values=(server.id, yt_stream.video_id, yt_stream.title, yt_stream.author, yt_stream.publish_date,
                    yt_stream.upcoming_date, yt_stream.thumbnail_url, yt_stream.watch_url,
                    '', yt_stream.greeting, yt_stream.upcoming, yt_stream.livestream, status.value)
        )
    else:
        MYSQL.execute(
            user_query="UPDATE yt_videos "
                       "SET `title` = %s, `author` = %s, `publish_date` = %s, "
                       "`upcoming_date` = %s, `thumbnail_url` = %s, `watch_url` = %s, "
                       "`upcoming` = %s, `livestream` = %s, `status` = %s "
                       "WHERE `server_id` = %s and `video_id` = %s",
            values=(yt_stream.title, yt_stream.author, yt_stream.publish_date,
                    yt_stream.upcoming_date, yt_stream.thumbnail_url, yt_stream.watch_url,
                    yt_stream.upcoming, yt_stream.livestream, status.value,
                    server.id, yt_stream.video_id, )
        )
    MYSQL.commit(True)
    logger.info(f"YT-video has been saved.")


@simple_try_except_decorator
def egs_save_game_to_db(server_id, game):
    MYSQL = mysql.MYSQL()
    MYSQL.execute(
        user_query="INSERT INTO egs_games "
                   "(`game_id`, `server_id`, `title`, `description`, `url`, `exp_date`, `thumbnail`) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        values=(game.id, server_id, game.title, game.description, game.url, game.exp_date, game.thumbnail)
    )
    MYSQL.commit(True)


@simple_try_except_decorator
def spinwheel_save_to_server(server: Guild, values_row: dict, action: SpinWheelAction):
    MYSQL = mysql.MYSQL()
    if action is SpinWheelAction.Add:
        MYSQL.execute(
            user_query="INSER T INTO spin_wheel "
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
