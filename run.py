#!/usr/bin/python -u
# -*- coding: utf-8 -*-

import argparse
import contextlib
import json
import logging
import time
import threading
from io import BytesIO
from gtts import gTTS
from websocket import WebSocket
import api
from cmd_type import CHZZK_CHAT_CMD
from block_pattern import PATTERN_EMOJI_UNICODE, PATTERN_EMOJI_LITERAL, PATTERN_URL
with contextlib.redirect_stdout(None):
    import pygame


class ChzzkChat:

    def __init__(self, streamer: str, cookies: str):
        self.default_dict = {}
        self.streamer_id = streamer
        self.cookies = cookies
        self.logger = self.init_logger()
        self.sid = None
        self.sock_id = 0
        self.sock = None
        self.terminate = False

        # Initializes tokens, channel info, etc.
        self.chat_channel_id = api.fetch_chat_channel_id(self.streamer_id)
        self.channel_name = api.fetch_channel_name(self.streamer_id)
        self.access_token, self.extra_token = api.fetch_access_token(
            self.chat_channel_id, self.cookies
        )
        self.default_dict = {
            "ver": "2",
            "svcid": "game",
            "cid": self.chat_channel_id,
        }
        try:
            self.user_id_hash = api.fetch_user_id_hash(self.cookies)
        except ValueError:
            self.logger.error("[ChzzkChat.__init__] 쿠키가 정상적이지 않습니다. 미로그인 상태로 진행합니다.")

        # Connect WebSocket upon initialization
        self.connect()


    def init_logger(self, filename: str = "chat.log"):
        formatter = logging.Formatter("[%(asctime)s][%(levelname)s]%(message)s")
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG) # logging.DEBUG
        file_handler = logging.FileHandler(filename, mode="a+")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        return logger


    def sanitize_message(self, message: str) -> str:
        message = PATTERN_EMOJI_LITERAL.sub("", message)
        message = PATTERN_EMOJI_UNICODE.sub("", message)
        message = PATTERN_URL.sub("", message)
        return message


    def play_tts(self, message: str, language: str):
        self.logger.debug("[ChzzkChat.play_tts] Save TTS to file")
        buffer = BytesIO()
        try:
            tts = gTTS(text=message, lang=language)
            tts.write_to_fp(buffer)
            buffer.seek(0)
        except Exception as exc:
            self.logger.error("[play_tts] Exception: %s", exc)
            return

        self.logger.debug("[ChzzkChat.play_tts] Initialize TTS")
        pygame.mixer.init()
        pygame.mixer.music.load(buffer)
        pygame.mixer.music.set_volume(1.0)

        self.logger.debug("[ChzzkChat.play_tts] Run TTS")
        pygame.mixer.music.play()
        clock = pygame.time.Clock()
        while pygame.mixer.music.get_busy():
            clock.tick(1)

        self.logger.debug("[ChzzkChat.play_tts] Destroy TTS")
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        pygame.mixer.quit()


    def connect(self):
        # Init websocket
        self.sock = WebSocket()
        self.sock.connect("wss://kr-ss1.chat.naver.com/chat")

        # Authentication Packet
        self.logger.info("[ChzzkChat.connect] %s 채팅창에 로그인 중 ...", self.channel_name)
        send_dict = {
            "cmd": CHZZK_CHAT_CMD.connect,
            "tid": 1,
            "bdy": {
                "uid": self.user_id_hash,
                "devType": 2001,
                "accTkn": self.access_token,
                "auth": "READ",
            },
        }
        self.sock.send(json.dumps(dict(send_dict, **self.default_dict)))
        sock_response = json.loads(self.sock.recv())
        self.sid = sock_response["bdy"]["sid"]
        self.logger.debug("[ChzzkChat.connect] SID %s", self.sid)

        # Recent Chat Request Packet
        self.logger.info("[ChzzkChat.connect] %s 채팅창 로딩중 ...", self.channel_name)
        send_dict = {
            "cmd": CHZZK_CHAT_CMD.request_recent_chat,
            "tid": 2,
            "sid": self.sid,
            "bdy": {"recentMessageCount": 50},
        }
        self.sock.send(json.dumps(dict(send_dict, **self.default_dict)))
        self.logger.debug("[ChzzkChat.connect] RecentChat: %s", self.sock.recv())

        if self.sock.connected:
            self.sock.send(json.dumps({"ver": "2", "cmd": CHZZK_CHAT_CMD.ping}))
            self.logger.info("[ChzzkChat.connect] 접속에 성공하였습니다.")
        else:
            raise ValueError("오류 발생")

    def run(self):
        thread_send = threading.Thread(target=self.send_handler)
        thread_recv = threading.Thread(target=self.recv_handler)
        try:
            thread_send.start()
            thread_recv.start()

            while thread_send.is_alive() or thread_recv.is_alive(): 
                thread_send.join(1)
                thread_recv.join(1)

        except (KeyboardInterrupt, SystemExit):
            self.terminate = True
            self.logger.info("[ChzzkChat.run] KeyboardInterrupt")


    def recv_handler(self):
        while True:
            try:
                raw_message = self.sock.recv()
                self.logger.debug("[ChzzkChat.recv_handler] Raw message: %s", raw_message)
                self.process_response(json.loads(raw_message))

            except Exception as exc:
                self.logger.error("[ChzzkChat.recv_handler] Exception: %s", exc)
                self.connect()
            
            finally:
                if self.terminate:
                    break


    def send_handler(self):
        while True:
            try:
                self.logger.debug("[ChzzkChat.send_handler] PING 패킷 전송 중 ...")
                self.sock.send(json.dumps({"ver": "2", "cmd": CHZZK_CHAT_CMD.ping}))

            except Exception as exc:
                self.logger.error("[ChzzkChat.send_handler] Exception: %s", exc)
                self.connect()

            finally:
                i = 0
                while i < 20:
                    if self.terminate:
                        break
                    time.sleep(1)
                    i += 1
                if self.terminate:
                    break


    def process_response(self, raw_message: str):
        chat_cmd = int(raw_message["cmd"])

        match chat_cmd:
            case CHZZK_CHAT_CMD.chat:
                chat_type = "채팅"

            case CHZZK_CHAT_CMD.donation:
                chat_type = "후원"

            case CHZZK_CHAT_CMD.pong:
                self.logger.debug("[ChzzkChat.process_response] PONG 패킷이 왔습니다.")
                return

            case CHZZK_CHAT_CMD.ping:
                self.logger.debug("[ChzzkChat.process_response] PONG 패킷을 보냅니다.")
                self.sock.send(json.dumps({"ver": "2", "cmd": CHZZK_CHAT_CMD.pong}))

                # chat_channel_id is different on every new broadcast
                if self.chat_channel_id != api.fetch_chat_channel_id(self.streamer_id):
                    self.logger.info("[ChzzkChat.process_response] 채널ID가 달라졌으므로 다시 채팅을 불러옵니다.")
                    self.connect()
                return

            case _:
                return

        for chat_data in raw_message["bdy"]:
            if chat_data["uid"] == "anonymous":
                nickname = "익명의 후원자"
            else:
                try:
                    profile_data = json.loads(chat_data["profile"])
                    nickname = profile_data["nickname"]
                    if "msg" not in chat_data:
                        nickname = "후원자"
                except:
                    nickname = "후원자"

            # Filter out useless chat messages
            chat_message = self.sanitize_message(chat_data["msg"])
            self.logger.info(
                "[ChzzkChat.process_response][%s] %s: %s",
                chat_type,
                nickname,
                chat_message
            )
            if chat_message:
                self.play_tts(
                    message=chat_message,
                    language="ko"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--streamer_id", type=str, default="479126c03d01dcad3e8348f2d491a5b3")
    args = parser.parse_args()

    try:
        with open("cookies.json", encoding="utf-8") as f:
            session_cookies = json.load(f)
    except:
        session_cookies = {}

    chzzkchat = ChzzkChat(args.streamer_id, session_cookies)
    chzzkchat.run()
