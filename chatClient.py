import socket
import threading
from typing import Callable
from chatMessage import HEADER_LENGTH, MessageMeta, MessageKeys
import curses
import time
import json
import signal


class ChatClientDisplay:
    PORT_IN = "Enter the server port: "
    USER_IN = "Enter your username: "
    MESSAGE_IN = "You: "

    def __init__(self, stdscr: curses.window, buffer: int) -> None:
        self._stdscr: curses.window = stdscr
        self._display_buffer: int = buffer

        self._message_box: curses.window = self._stdscr
        self._input_box: curses.window = self._stdscr
        self._users_box: curses.window = self._stdscr

        self._users_height: int = 10

        self.resize()

        curses.curs_set(1)
        self._stdscr.clear()

    def resize(self) -> None:
        min_message_height = 7  # 5 Content, 2 for border
        min_user_height = 4  # 2 Content, 2 for border
        input_height = 3  # 1 Content, 2 for border

        self._stdscr.clear()
        self._message_box.clear()
        self._input_box.clear()
        self._users_box.clear()

        height, width = self._stdscr.getmaxyx()

        if height < min_message_height + min_user_height + input_height:
            raise RuntimeError("Window too small.")

        message_height = max(min(self._display_buffer + 2,
                                 height - (min_user_height + input_height)),
                             min_message_height)
        self._display_buffer = message_height - 2

        self._message_box = curses.newwin(
            message_height, width, 0, 0)

        self._input_box: curses.window = curses.newwin(
            input_height, width, message_height, 0)

        self._users_height = max(min(height - (message_height + input_height),
                                     self._users_height), min_user_height)
        self._users_box: curses.window = curses.newwin(
            self._users_height, width, message_height + input_height,
            0)
        self._stdscr.refresh()
        self._users_box.refresh()
        self._message_box.refresh()
        self._input_box.refresh()

    def login_screen(self) -> tuple[str, int]:
        self._stdscr.clear()
        self._stdscr.border()
        self._stdscr.addstr(1, 1, "Welcome to the Chat Client!")
        self._stdscr.addstr(3, 1, self.PORT_IN)
        self._stdscr.addstr(2, 1, self.USER_IN)
        curses.echo()
        self._stdscr.refresh()
        username = self._stdscr.getstr(2, len(self.USER_IN) + 1
                                       ).decode("utf-8")

        while True:
            self._stdscr.move(3, 1)
            self._stdscr.clrtoeol()
            self._stdscr.border()
            self._stdscr.addstr(3, 1, "Enter the server port: ")
            self._stdscr.refresh()
            try:
                port = int(self._stdscr.getstr(3, len(self.PORT_IN) + 1
                                               ).decode("utf-8"))
                if 1 <= port <= 65535:
                    break
                else:
                    self._stdscr.move(4, 1)
                    self._stdscr.clrtoeol()
                    self._stdscr.addstr(4, 1,
                                        "Port must be between 1 and 65535.")
                    self._stdscr.refresh()
            except ValueError:
                self._stdscr.move(4, 1)
                self._stdscr.clrtoeol()
                self._stdscr.addstr(
                    4, 1, "Invalid input. Please enter a valid port number.")
                self._stdscr.refresh()

        curses.noecho()
        self._stdscr.refresh()
        return username, port

    def main_screen(self) -> None:
        curses.curs_set(0)
        self._stdscr.clear()
        self._stdscr.refresh()

        self._users_box.clear()
        self._input_box.clear()
        self.update_display([], [])

        self._input_box.border()
        self._input_box.addstr(1, 1, self.MESSAGE_IN)
        self._input_box.refresh()
        curses.curs_set(1)

    def handle_input(self) -> str:
        max_input_len = self._input_box.getmaxyx()[1] - (2 + len(
            self.MESSAGE_IN))
        user_input = []

        while True:
            char = self._input_box.getch()
            if char in (curses.KEY_ENTER, 10, 13):
                break
            elif (len(user_input) > 0 and
                  (char == curses.KEY_BACKSPACE or char == 127)):
                user_input = user_input[:-1]
            elif 32 <= char <= 126:
                user_input.append(chr(char))

            display_text = "".join(user_input[-max_input_len:])
            self._input_box.clear()
            self._input_box.border()
            self._input_box.addstr(1, 1, self.MESSAGE_IN + display_text)
            self._input_box.refresh()
        return "".join(user_input)

    def get_input(self) -> tuple[str, str]:
        curses.curs_set(0)
        self._input_box.clear()
        self._input_box.border()
        self._input_box.addstr(1, 1, self.MESSAGE_IN)
        curses.curs_set(1)
        self._input_box.refresh()
        message = self.handle_input()
        self._input_box.clear()
        self._input_box.border()
        self._input_box.refresh()
        return self.MESSAGE_IN, message

    def update_messages(self, messages: list[str]) -> None:
        curses.curs_set(0)

        self._message_box.clear()
        self._message_box.border()

        self._message_box.move(1, 1)

        max_width = self._message_box.getmaxyx()[1] - 2
        wrapped_messages = []

        for message in messages[-self._display_buffer:]:
            wrapped_lines = [message[i:i + max_width]
                             for i in range(0, len(message), max_width)]
            wrapped_messages.extend(wrapped_lines)

        for i, line in enumerate(wrapped_messages[-self._display_buffer:]):
            self._message_box.addstr(i + 1, 1, line)

        curses.curs_set(1)
        self._message_box.refresh()
        self._input_box.refresh()

    def update_users(self, users: list[str]) -> None:
        curses.curs_set(0)

        self._users_box.clear()
        self._users_box.border()

        for i, user in enumerate(users):
            column = (i // self._users_height) * 20 + 1
            self._users_box.addstr(
                i + 1, column, user[:self._users_box.getmaxyx()[1] - 2])

        curses.curs_set(1)
        self._users_box.refresh()
        self._input_box.refresh()

    def update_display(self, messages: list[str], users: list[str]) -> None:
        self.update_messages(messages)
        self.update_users(users)


class ChatClientSocketHandler:
    def __init__(self, message_callback: Callable[[str], None],
                 user_callback: Callable[[list[str], bool], None]) -> None:
        self._host: str | None = None
        self._port: int | None = None
        self._message_callback: Callable[[str], None] = message_callback
        self._user_callback: Callable[[list[str], bool], None] = user_callback
        self._socket = None
        self._running: bool = False

    def connect(self, host: str, port: int) -> None:
        if self._running:
            raise RuntimeError("Client already connected")

        self._host = host
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._socket.connect((self._host, self._port))
        self._running = True
        threading.Thread(target=self.receive_message, daemon=True).start()

    def handle_message(self, message: str) -> None:
        message = json.loads(message)
        meta = message[MessageKeys.META.value]
        if meta == MessageMeta.SEND.value:
            content = message[MessageKeys.CONTENT.value]
            sender = message[MessageKeys.SENDER.value]
            value = f"{sender}: {content}"
            self._message_callback(value)
        elif meta == MessageMeta.JOIN.value:
            username = message[MessageKeys.USERNAME.value]
            value = f"{username} has joined the chat."
            self._message_callback(value)
            self._user_callback([username], True)
        elif meta == MessageMeta.LEAVE.value:
            username = message[MessageKeys.USERNAME.value]
            value = f"{username} has left the chat."
            self._message_callback(value)
            self._user_callback([username], False)
        elif meta == MessageMeta.BATCH_JOIN.value:
            usernames = message[MessageKeys.USERNAMES.value]
            value = f"{', '.join(usernames)} are in the chat."
            self._message_callback(value)
            self._user_callback(usernames, True)
        elif meta == MessageMeta.BATCH_LEAVE.value:
            usernames = message[MessageKeys.USERNAMES.value]
            value = f"{', '.join(usernames)} have left the chat."
            self._message_callback(value)
            self._user_callback(usernames, False)

    def receive_message(self) -> None:
        data_chunks = []
        expected_chunks = None
        while self._running:
            try:
                chunk = self._socket.recv(1024)
                if not chunk:
                    break

                header = chunk[:HEADER_LENGTH].decode().strip()
                body = chunk[HEADER_LENGTH:]

                index, total = map(int, header.split("/"))

                if expected_chunks is None:
                    expected_chunks = total

                data_chunks.append((index, body))

                if len(data_chunks) == expected_chunks:
                    data_chunks.sort()
                    full_data = b"".join(chunk for _, chunk in data_chunks)
                    message = full_data.decode()

                    self.handle_message(message)

                    data_chunks.clear()
                    expected_chunks = None

            except Exception as err:
                self._running = False
                print(f"Error receiving message: {err}")

    def send_message(self, message: str) -> None:
        if not self._running:
            raise RuntimeError("Socket is not running")

        try:
            self._socket.sendall(message.encode())
        except Exception as err:
            print(f"Error sending message: {err}")

    def close(self) -> None:
        self._running = False
        self._socket.close()


class ChatClient:
    HOST = "127.0.0.1"
    MESSAGE_IN = "You: "

    def __init__(self, stdscr: curses.window) -> None:
        self._buffer = 20
        self._display = ChatClientDisplay(stdscr, self._buffer)
        self._messages: list[str] = []
        self._users: list[str] = []
        self._history_length: int = 1000

        self._socket_handler = ChatClientSocketHandler(self.add_message,
                                                       self.handle_user)

        signal.signal(signal.SIGWINCH, self.handle_resize)

    def start(self) -> None:
        username, port = self._display.login_screen()
        self._socket_handler.connect(ChatClient.HOST, port)
        self._socket_handler.send_message(username)
        curses.curs_set(1)
        self._display.main_screen()

        try:
            while True:
                time.sleep(0.2)
                curses.curs_set(1)
                curses.echo()
                field, message = self._display.get_input()
                if message.lower() == "/quit":
                    break
                self._messages.append(f"{field}{message}")
                self._socket_handler.send_message(message)
                self._display.update_messages(self._messages)
                curses.noecho()
                curses.curs_set(0)
        finally:
            self._socket_handler.close()
        curses.noecho()

    def add_message(self, message: str) -> None:
        self._messages.append(message)
        self._messages = self._messages[-self._history_length:]
        self._display.update_messages(self._messages)

    def handle_user(self, usernames: list[str], joined: bool) -> None:
        if joined:
            self._users.extend(usernames)
        else:
            for username in usernames:
                self._users.remove(username)
        self._display.update_users(self._users)

    def handle_resize(self, *args) -> None:
        self._display.resize()
        self._display.main_screen()
        self._display.update_display(self._messages, self._users)


def main(stdscr):
    client = ChatClient(stdscr)
    client.start()



if __name__ == "__main__":
    curses.wrapper(main)

