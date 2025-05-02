import asyncio
from discord import Guild, TextChannel
import mysql
from enums import *
from helpers import (
    simple_try_except_decorator, logger, get_right_value_type
)
from spinwheel_games import (
    SpinWheelGameStatus, SpinWheelAction
)
from yt_parser import (YoutubeStreamStatus, YouTubeLiveStream)


def mysql_getdata(*args, **kwargs):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(*args, **kwargs)
    MYSQL.close()
    return MYSQL


@simple_try_except_decorator
def server_get_status(server_id: int | str = None):
    MYSQL = mysql_getdata(f"SELECT * FROM `servers` WHERE `id`=%s", values=server_id)
    return ServerStatus(not MYSQL.empty)


@simple_try_except_decorator
def server_get_bot_channels():
    MYSQL = mysql_getdata(f"SELECT service_channel, ready FROM `bot_config`")
    if MYSQL.empty:
        return list() if MYSQL.empty else int(MYSQL.data)


@simple_try_except_decorator
def server_get_bot_settings(server_id: int | str = None):
    # LOCAL_SETTING = BOT_LOCAL_CONFIG.get('bot_channels')
    # if LOCAL_SETTING is not None:
    #     return server_id if server_id in LOCAL_SETTING else None
    MYSQL = mysql_getdata(f"SELECT service_channel, ready, msg_id FROM `bot_config` WHERE `server_id`=%s", values=server_id)
    if MYSQL.empty:
        return None, False, None
    else:
        return (int(MYSQL.data[0]['service_channel']), bool(MYSQL.data[0]['ready']), MYSQL.data[0]['msg_id'])

###
# UPDATE 10/04/2025
@simple_try_except_decorator
def server_community_message_update(server: Guild, value):
    MYSQL = mysql.MYSQL()
    MYSQL.execute("UPDATE `bot_config` SET `msg_id` = %s WHERE `server_id` = %s", values=(value, server.id))
    MYSQL.commit(True)

@simple_try_except_decorator
def server_community_message_get(server_id):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(user_query="SELECT `msg_id` FROM bot_config WHERE `server_id` = %s", values=server_id)
    return MYSQL.data[0]['msg_id']
###

@simple_try_except_decorator
def server_update_bot_ready(server: Guild, value):
    MYSQL = mysql.MYSQL()
    MYSQL.execute("UPDATE `bot_config` SET `ready` = %s WHERE `server_id` = %s", values=(value, server.id))
    MYSQL.commit(True)


@simple_try_except_decorator
def server_update_settings(server: Guild, settings: dict):
    MYSQL = mysql.MYSQL()
    settings_list = [(setting['value'], setting['setting_id'], server.id) for setting in settings.values()]
    MYSQL.executemany(user_query="UPDATE srv_config SET `value` = %s WHERE `setting_id` = %s and `server_id` = %s",
                      values=settings_list)
    MYSQL.commit(True)


@simple_try_except_decorator
def server_get_settings(server_id: int | str = None):
    def return_setting_dict(feature_name: str):
        def get_item(item: dict):
            ml = {'bool': bool, 'int': int}
            f = ml.get(item['type'])
            if f is not None:
                item['value'] = int(item['value'])
            return item

        return {x['name']: get_item(x) for x in (item for item in MYSQL.data if item['fname'] == feature_name)}

    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT settings.name, srv_config.value, settings.`type`, "
                   "settings.description, srv_config.setting_id, features.name AS fname\n"
                   "FROM srv_config\n"
                   "LEFT JOIN settings\n"
                   "ON srv_config.setting_id = settings.id\n"
                   "LEFT JOIN features\n"
                   "ON settings.feature_id = features.id\n"
                   "WHERE srv_config.server_id = %s",
        values=server_id
    )
    settings_egs, settings_ytube, settings_ytube_msg = None, None, None
    if not MYSQL.empty:
        settings_egs = return_setting_dict('egs')
        settings_ytube = return_setting_dict('ytube')
        settings_ytube_msg = return_setting_dict('ytube_msg')
    MYSQL.close()
    return {
        'egs': {'settings': settings_egs, 'task': None, },
        'ytube': {'settings': settings_ytube, 'task': None, },
        'ytube_msg': {'settings': settings_ytube_msg, 'task': None, 'msg_id': '', }
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
                   "`thumbnail_url`, `watch_url`, `description`, `greeting`, `upcoming`,"
                   "`livestream`, `status`, `message_id` "
                   "FROM yt_videos WHERE server_id = %s",
        values=server_id
    )
    MYSQL.close()
    return {} if MYSQL.empty else return_dict()


@simple_try_except_decorator
def server_get_matching_egs_list(server_id: int | str = None):
    def return_dict():
        return {item['game_id']: item for item in MYSQL.data}

    MYSQL = mysql_getdata(
        user_query="SELECT `game_id`, `title`, `description`, `url`, `exp_date`, `thumbnail` "
                   "FROM egs_games WHERE server_id = %s",
        values=server_id
    )
    return {} if MYSQL.empty else return_dict()


@simple_try_except_decorator
def server_get_spinwheel_list(server_id: int | str = None):
    MYSQL = mysql_getdata(
        user_query="SELECT game, status, url, comment, hltb FROM spin_wheel WHERE server_id = %s ORDER BY `status`, game",
        values=server_id
    )
    return dict() if MYSQL.empty else {x['game']: {"status": SpinWheelGameStatus(x['status']),
                                                   "url": x['url'],
                                                   "comment": x['comment'],
                                                   "hltb": x['hltb']} for x in MYSQL.data}


@simple_try_except_decorator
def server_delete_bot_registration(server_id: int | str = None):
    MYSQL = mysql.MYSQL()
    MYSQL.execute(f"DELETE FROM servers WHERE `id`= %s", values=server_id)
    MYSQL.commit(True)


@simple_try_except_decorator
async def server_signup(server: Guild, bot_channel: TextChannel):
    MYSQL = mysql.MYSQL()
    MYSQL.get_data(f"SELECT * FROM `settings`")
    features = MYSQL.data
    await asyncio.sleep(1)

    MYSQL.execute(
        user_query=f"INSERT INTO servers (`id`, `name`) VALUES (%s, %s)",
        values=(server.id, server.name)
    )
    logger.info(f"Creating settings for [**{server.name}**]:[**{server.id}**]...")
    user_query = f"INSERT INTO srv_config (`server_id`, `setting_id`, `value`) VALUES (%s, %s, %s) "

    value_list = [(server.id, feature['id'], get_right_value_type(feature['type'])) for feature in features]
    # MYSQL.commit()
    MYSQL.executemany(user_query, value_list)
    MYSQL.execute('INSERT INTO bot_config (service_channel, server_id, ready) VALUES (%s, %s, %s)',
                  values=(bot_channel.id, server.id, True))
    await asyncio.sleep(1)
    MYSQL.commit(True)


@simple_try_except_decorator
def server_change_service_channel(server: Guild, bot_channel: TextChannel):
    MYSQL = mysql.MYSQL()
    MYSQL.execute("UPDATE bot_config SET `service_channel` = %s WHERE `server_id` = %s",
                  values=(bot_channel.id, server.id))
    MYSQL.commit()


def ytube_update_custom_field(server_id, video_id, field, value):
    logger.info(f"Update *yt_videos* | {field=}")
    MYSQL = mysql.MYSQL()
    MYSQL.execute(
        user_query=f"UPDATE yt_videos SET `{field}` = %s WHERE `video_id` = %s and `server_id` = %s",
        values=(value, video_id, server_id)
    )
    MYSQL.commit(True)


@simple_try_except_decorator
def ytube_update_upcoming_stream_greeting(server_id, video_id, description):
    ytube_update_custom_field(server_id, video_id, "greeting", description)


@simple_try_except_decorator
def ytube_update_upcoming_stream_date(server_id, video_id, upcoming_date):
    ytube_update_custom_field(server_id, video_id, "upcoming_date", upcoming_date)


@simple_try_except_decorator
def ytube_update_stream_status(server_id, video_id, status: YoutubeStreamStatus):
    ytube_update_custom_field(server_id, video_id, "status", status.value)


@simple_try_except_decorator
def ytube_update_stream_message_id(server_id, video_id, message_id=''):
    ytube_update_custom_field(server_id, video_id, "message_id", message_id)


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
def ytube_delete_finished_streams(server: Guild):
    MYSQL = mysql.MYSQL()
    MYSQL.execute("DELETE FROM yt_videos WHERE `server_id` = %s and `status` = 4", values=server.id)
    MYSQL.commit(True)


@simple_try_except_decorator
def ytube_save_video_to_dbase(server: Guild, yt_stream: YouTubeLiveStream,
                              status: YoutubeStreamStatus, is_update: bool = False):
    MYSQL = mysql.MYSQL()
    if not is_update:
        MYSQL.execute(
            user_query="INSERT INTO yt_videos "
                       "(`server_id`,`video_id`, `title`, `author`, `publish_date`, "
                       "`upcoming_date`, `thumbnail_url`, `watch_url`, "
                       "`description`, `greeting`, `upcoming`, `livestream`, `status`) "
                       "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
                    server.id, yt_stream.video_id,)
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
            user_query="INSERT INTO spin_wheel "
                       "(`game`, `status`, `url`, `comment`, `hltb`, `server_id`) "
                       "VALUES (%s,%s,%s,%s,%s,%s)",
            values=(
                values_row['game'], values_row['status'].value, values_row['url'], values_row['comment'], values_row['hltb'],
                server.id)
        )
    elif action is SpinWheelAction.Edit:
        MYSQL.execute(
            user_query="UPDATE spin_wheel "
                       "SET `status` = %s, `url` = %s, `comment` = %s, `game` = %s, `hltb` = %s"
                       "WHERE `game` = %s and `server_id` = %s",
            values=(
                values_row['status'].value, values_row['url'], values_row['comment'], values_row['new_game'], values_row['hltb'],
                values_row['game'], server.id)
        )
    elif action is SpinWheelAction.Delete:
        MYSQL.execute(
            user_query="DELETE FROM spin_wheel WHERE `game` = %s and `server_id` = %s",
            values=(values_row['game'], server.id)
        )
    MYSQL.commit(True)
