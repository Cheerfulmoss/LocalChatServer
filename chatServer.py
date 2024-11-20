import socket
import string
import threading
import time
from functools import wraps
from typing import Iterator
from chatMessage import MessageFactory


def thread_safe_method(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._lock:  # Just assume a ._lock exists :3
            return func(self, *args, **kwargs)
    return wrapper


class Clients:
    def __init__(self):
        self._clients: dict[socket.socket, str] = {}
        self._lock = threading.Lock()

    @thread_safe_method
    def add_client(self, socket: socket.socket, username: str) -> None:
        self._clients[socket] = username

    @thread_safe_method
    def remove_client(self, socket: socket.socket) -> None:
        self._clients.pop(socket, None)

    @thread_safe_method
    def get_clients(self) -> list[socket.socket]:
        return list(self._clients.keys())

    @thread_safe_method
    def get_username(self, socket: socket.socket) -> str | None:
        return self._clients.get(socket, None)

    @thread_safe_method
    def is_username_taken(self, username: str) -> bool:
        return username in self._clients.values()

    @thread_safe_method
    def is_client_connected(self, socket) -> bool:
        return socket in self._clients


class ServerClientHandler:
    DISALLOWED_USERNAMES: list[str] = ["You"]
    MAX_UNAME_LEN: int = 20
    INV_CHARS: str = string.punctuation

    def __init__(self, name: str, clients: Clients) -> None:
        self._name: str | None = name
        self.DISALLOWED_USERNAMES.append(self._name)
        self._message_factory: MessageFactory = MessageFactory(1024)
        self._clients: Clients = clients
        self._running: bool = True

    def validate_username(self, client_socket: socket.socket,
                          username: str) -> bool:
        if not username:
            client_socket.close()
            raise ValueError("Username must be provided")

        if len(username) > self.MAX_UNAME_LEN:
            message = self._message_factory.username_too_long(
                self._name, username, self.MAX_UNAME_LEN)
            self.send_message(client_socket, message)
            client_socket.close()
            return False

        for char in self.INV_CHARS:
            if char in username:
                message = self._message_factory.username_inv_chars(
                    self._name, username, char
                )
                self.send_message(client_socket, message)
                client_socket.close()
                return False

        if username in self.DISALLOWED_USERNAMES:
            message = self._message_factory.invalid_username(
                self._name, username)
            self.send_message(client_socket, message)
            client_socket.close()
            return False

        if self._clients.is_username_taken(username):
            message = self._message_factory.username_in_use(
                self._name, username)
            self.send_message(client_socket, message)
            client_socket.close()
            return False

        return True

    def remove_client(self, client_socket) -> None:
        client_socket.close()
        username = self._clients.get_username(client_socket)
        self._clients.remove_client(client_socket)
        message = self._message_factory.leave_meta(username)
        self.send_all(client_socket, message)

    def add_client(self, client_socket, username: str) -> None:
        self._clients.add_client(client_socket, username)

        message = self._message_factory.join_meta(username)
        self.send_all(client_socket, message)
        self.send_joins(client_socket)

    def send_message(self, client_socket: socket.socket,
                     message: Iterator[bytes]) -> None:
        to_remove = None
        try:
            for chunk in message:
                client_socket.sendall(chunk)
                time.sleep(0.01)
        except socket.error:
            to_remove = client_socket
        finally:
            if not to_remove:
                return
            self.remove_client(client_socket)

    def send_all(self, client_socket: socket.socket,
                 message: Iterator[bytes]) -> None:
        to_remove = []
        for chunk in message:
            for client in self._clients.get_clients():
                if client == client_socket:
                    continue
                try:
                    client.sendall(chunk)
                except socket.error:
                    to_remove.append(client)
            time.sleep(0.01)

        for client in to_remove:
            self.remove_client(client)

    def send_joins(self, client_socket: socket.socket) -> None:
        usernames = []
        for client in self._clients.get_clients():
            if client == client_socket:
                continue
            username = self._clients.get_username(client)
            usernames.append(username)

        if not usernames:
            return

        message = self._message_factory.batch_join_meta(usernames)
        self.send_message(client_socket, message)

    def handle_client(self, client_socket: socket.socket, addr) -> None:
        client_socket.settimeout(1.0)
        try:
            username = client_socket.recv(1024).decode().strip()
        except socket.error:
            return

        if not self.validate_username(client_socket, username):
            return

        print(f"{username} connected from {addr}")
        self.add_client(client_socket, username)

        while self._running:
            try:
                message = client_socket.recv(1024)
                if not message:
                    break
                message = message.decode().strip()
                print(f"Received from {username}@{addr}: {message}")
                message = self._message_factory.message(username, message)
                self.send_all(client_socket, message)

            except socket.timeout:
                if not self._running:
                    break
            except socket.error:
                break

        if client_socket not in self._clients.get_clients():
            return

        print(f"{username} disconnected from {addr}")
        self.remove_client(client_socket)

    def close_all(self) -> None:
        self._running = False
        for client in self._clients.get_clients():
            username = self._clients.get_username(client)
            self._clients.remove_client(client)
            print(f"Disconnected {username} on {client.getpeername()}")
            client.close()
        print("All users disconnected")


class ChatServerSocketHandler:
    HOST = "127.0.0.1"

    def __init__(self, client_handler: ServerClientHandler) -> None:
        self._socket: socket.socket | None = None
        self._port: str | None = None
        self._running: bool = False
        self._threads: list[threading.Thread] = []
        self._client_handler: ServerClientHandler = client_handler

    def bind_and_listen(self) -> None:
        if self._socket is not None:
            raise RuntimeError("socket is already bound")

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((ChatServerSocketHandler.HOST, 0))
        self._socket.listen()

        self._port = self._socket.getsockname()[-1]
        print(f"Server listening on {self.HOST}:{self._port}")

    def accept_clients(self) -> None:
        if not self._socket:
            raise RuntimeError("Server socket not initialized. "
                               "Call bind_and_listen first.")

        while self._running:
            client_socket, addr = self._socket.accept()
            print(f"New connection from {addr}")
            thread = threading.Thread(target=self._client_handler.handle_client,
                                      args=(client_socket, addr))
            thread.start()
            self._threads.append(thread)

    def start(self) -> None:
        if self._running:
            raise RuntimeError("Server already running")
        self._running = True
        self.bind_and_listen()
        self.accept_clients()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._client_handler.close_all()

        if self._socket:
            self._socket.close()

        for thread in self._threads:
            thread.join()
        print("Server shut down gracefully")


def main() -> None:
    clients = Clients()
    client_handler = ServerClientHandler("SERVER", clients)
    server = ChatServerSocketHandler(client_handler)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down the server")
        server.stop()
    except Exception as err:
        print(f"Server error: {err}")
        server.stop()


if __name__ == "__main__":
    main()
