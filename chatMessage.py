from enum import Enum
from typing import Generator
import json

HEADER_LENGTH = 16


class MessageMeta(Enum):
    SEND = 0
    JOIN = 1
    LEAVE = 2
    BATCH_JOIN = 3
    BATCH_LEAVE = 4


class MessageKeys(Enum):
    META = "meta"
    SENDER = "sender"
    CONTENT = "content"
    USERNAME = "username"
    USERNAMES = "usernames"


class MessageFactory:
    def __init__(self, message_bytes: int) -> None:
        self._message_bytes = message_bytes

    def create_chunks(self, data: dict) -> Generator[bytes, None, None]:
        json_data = json.dumps(data).encode()
        total_chunks = ((len(json_data) + self._message_bytes - 1) //
                        self._message_bytes)

        for i in range(total_chunks):
            chunk = json_data[
                    i * self._message_bytes:(i + 1) * self._message_bytes]
            header = f"{i+1}/{total_chunks}".encode().ljust(HEADER_LENGTH)
            yield header + chunk

    def message(self, sender: str, message: str
                ) -> Generator[bytes, None, None]:
        data = {
            MessageKeys.META.value: MessageMeta.SEND.value,
            MessageKeys.SENDER.value: sender,
            MessageKeys.CONTENT.value: message,
        }
        return self.create_chunks(data)

    def join_meta(self, username: str) -> Generator[bytes, None, None]:
        data = {
            MessageKeys.META.value: MessageMeta.JOIN.value,
            MessageKeys.USERNAME.value: username,
        }
        return self.create_chunks(data)

    def leave_meta(self, username: str) -> Generator[bytes, None, None]:
        data = {
            MessageKeys.META.value: MessageMeta.LEAVE.value,
            MessageKeys.USERNAME.value: username,
        }
        return self.create_chunks(data)

    def batch_join_meta(self, usernames: list[str]
                        ) -> Generator[bytes, None, None]:
        data = {
            MessageKeys.META.value: MessageMeta.BATCH_JOIN.value,
            MessageKeys.USERNAMES.value: usernames,
        }
        return self.create_chunks(data)

    def batch_leave_meta(self, usernames: list[str]
                         ) -> Generator[bytes, None, None]:
        data = {
            MessageKeys.META.value: MessageMeta.BATCH_LEAVE.value,
            MessageKeys.USERNAMES.value: usernames,
        }
        return self.create_chunks(data)

    def invalid_username(self, sender: str, username: str
                         ) -> Generator[bytes, None, None]:
        message = f"\"{username}\" is an invalid username."
        return self.message(sender, message)

    def username_in_use(self, sender: str, username: str
                        ) -> Generator[bytes, None, None]:
        message = f"\"{username}\" is already taken."
        return self.message(sender, message)

    def username_too_long(self, sender: str, username: str, max_len: int
                          ) -> Generator[bytes, None, None]:
        message = f"\"{username}\" is too long. Maximum length is {max_len}."
        return self.message(sender, message)

    def username_inv_chars(self, sender: str, username: str, inv_char: str
                           ) -> Generator[bytes, None, None]:
        message = (f"\"{username}\" has invalid characters. The following "
                   f"char is invalid \"{inv_char}\"")
        return self.message(sender, message)
