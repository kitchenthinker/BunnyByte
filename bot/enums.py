from enum import Enum, auto


class ChecksBeforeStart(Enum):
    OWNER = auto()
    REGISTRATION = auto()
    CHANNEL = auto()
    READY = auto()


class SettingSwitcher(Enum):
    Enable = 1
    Disable = 0


class SettingYesNo(Enum):
    Yes = 1
    No = 0


class ServerStatus(Enum):
    REGISTERED = 1
    UNREGISTERED = 0

