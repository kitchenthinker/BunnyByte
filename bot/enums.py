from enum import Enum, auto


class StartChecks(Enum):
    OWNER = auto()
    REGISTRATION = auto()
    CHANNEL_EXIST = auto()
    CHANNEL_AVAILABLE = auto()
    CHANNEL_TEXT = auto()
    READY = auto()
    ALREADY_REGISTERED = auto()


class SettingSwitcher(Enum):
    Enable = 1
    Disable = 0


class SettingYesNo(Enum):
    Yes = 1
    No = 0


class ServerStatus(Enum):
    REGISTERED = 1
    UNREGISTERED = 0
