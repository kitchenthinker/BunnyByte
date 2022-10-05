import mysql
from enums import *
from main import (
    simple_try_except_decorator,
)
from spinwheel_games import SpinWheelGameStatus


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
        return None, None
    else:
        return int(MYSQL.data[0]['service_channel']), bool(MYSQL.data[0]['ready'])


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
        return {item['video_id']: item for item in MYSQL.data}

    MYSQL = mysql.MYSQL()
    MYSQL.get_data(
        user_query="SELECT `video_id`, `title`, `author`, `publish_date`, `upcoming_date`,"
                   "`thumbnail_url`, `watch_url`, `upcoming`, `livestream` "
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
        user_query="SELECT `game_id`, `title`, `description`, `url`, `expdate`, `cover_url` "
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
def ytube_update_upcoming_stream_description(server_id, video_id, description):
    MYSQL = mysql.MYSQL()
    MYSQL.execute(
        user_query="UPDATE yt_videos SET `description` = %s WHERE `video_id` = %s and `server_id` = %s",
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
