import datetime
from string import Formatter
from functools import wraps
import logging
from discord import Interaction
from discord.utils import utcnow

EPHEMERAL_ATTRIBUTE_NAME = 'defer'
DEFER_YES = {EPHEMERAL_ATTRIBUTE_NAME: True}
DEFER_NO = {EPHEMERAL_ATTRIBUTE_NAME: False}
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def utc_time_now() -> datetime.datetime:
    return utcnow().replace(tzinfo=None)

def strfdelta(tdelta, fmt='{D:02}d {H:02}h {M:02}m {S:02}s', inputtype='timedelta'):
    """Convert a datetime.timedelta object or a regular number to a custom-
    formatted string, just like the stftime() method does for datetime.datetime
    objects.

    The fmt argument allows custom formatting to be specified.  Fields can
    include seconds, minutes, hours, days, and weeks.  Each field is optional.

    Some examples:
        '{D:02}d {H:02}h {M:02}m {S:02}s' --> '05d 08h 04m 02s' (default)
        '{W}w {D}d {H}:{M:02}:{S:02}'     --> '4w 5d 8:04:02'
        '{D:2}d {H:2}:{M:02}:{S:02}'      --> ' 5d  8:04:02'
        '{H}h {S}s'                       --> '72h 800s'

    The inputtype argument allows tdelta to be a regular number instead of the
    default, which is a datetime.timedelta object.  Valid inputtype strings:
        's', 'seconds',
        'm', 'minutes',
        'h', 'hours',
        'd', 'days',
        'w', 'weeks'
    """

    # Convert tdelta to integer seconds.
    if inputtype == 'timedelta':
        remainder = int(tdelta.total_seconds())
    elif inputtype in ['s', 'seconds']:
        remainder = int(tdelta)
    elif inputtype in ['m', 'minutes']:
        remainder = int(tdelta) * 60
    elif inputtype in ['h', 'hours']:
        remainder = int(tdelta) * 3600
    elif inputtype in ['d', 'days']:
        remainder = int(tdelta) * 86400
    elif inputtype in ['w', 'weeks']:
        remainder = int(tdelta) * 604800

    f = Formatter()
    desired_fields = [field_tuple[1] for field_tuple in f.parse(fmt)]
    possible_fields = ('W', 'D', 'H', 'M', 'S')
    constants = {'W': 604800, 'D': 86400, 'H': 3600, 'M': 60, 'S': 1}
    values = {}
    for field in possible_fields:
        if field in desired_fields and field in constants:
            values[field], remainder = divmod(remainder, constants[field])
    return f.format(fmt, **values)


def simple_try_except_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.info(f"S - Something went wrong [{e}]. Try again or send me a message and we will do something.")
            raise

    return wrapper


def discord_async_try_except_decorator(func):
    """
    To be honest, I dunno know what I'm doing. It works (I hope) , I don't touch.
    """

    @wraps(func)
    async def wrapper(interaction, *args, **kwargs):
        is_discord_interaction = isinstance(interaction, Interaction)
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

    #            raise

    return wrapper


FAQ_ADMIN = f"[**.server-register <#service-channel>**]\n" \
            f"- Зарегистрировать сервер для работы бота. Нужно создать приватный канал и дать доступ боту.\n" \
            f"- Пример: .server-register #приватный-канал\n" \
            f"{'--' * 20}\n" \
            f"- Register the bot. You need to create a private channel and give permission to bot.\n" \
            f"- Example: .server-register #private-channel\n\n" \
            f"[**.server-delete**]\n" \
            f"- Прекратить работу бота. Все настройки будут удалены!!! Чтобы запустить бота снова, нужно пройти регистрацию.\n" \
            f"--------------------------------------------\n" \
            f"- Shut down the bot. All bot setting will be deleted!!! You need to register server if you wanna start it again.\n\n" \
            f"[**.server-csc <#service-channel>**]\n" \
            f"- Сменить канал для вывода сервисных сообщений.\n" \
            f"--------------------------------------------\n" \
            f"- Change service channel for receiving service bots notification.\n\n" \
            f"[**.server-info**]\n" \
            f"- Показать информацию о сервере.\n" \
            f"--------------------------------------------\n" \
            f"- Show up server info.\n"

FAQ_USER = f"[**.server-register <#service-channel>**]\n" \
           f"- Зарегистрировать сервер для работы бота. Нужно создать приватный канал и дать доступ боту.\n" \
           f"- Пример: .server-register #приватный-канал\n"
