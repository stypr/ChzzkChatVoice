#!/usr/bin/python -u
# -*- coding: utf-8 -*-

import argparse
import contextlib
import logging
import json
import os
from gtts import gTTS
from websocket import WebSocket
import api
from cmd_type import CHZZK_CHAT_CMD
from block_pattern import PATTERN_EMOJI_UNICODE, PATTERN_EMOJI_LITERAL, PATTERN_URL
with contextlib.redirect_stdout(None):
    import pygame


class ChzzkChat:

    def __init__(self, streamer, cookies):
        self.default_dict = {}
        self.streamer = streamer
        self.cookies = cookies
        self.logger = self.init_logger()
        self.sid = None
        self.sock = None

        # Initializes tokens, channel info, etc.
        self.chatChannelId = api.fetch_chatChannelId(self.streamer)
        self.channelName = api.fetch_channelName(self.streamer)
        self.accessToken, self.extraToken = api.fetch_accessToken(self.chatChannelId, self.cookies)
        self.default_dict = {
            "ver": "2",
            "svcid": "game",
            "cid": self.chatChannelId,
        }
        try:
            self.userIdHash = api.fetch_userIdHash(self.cookies)
        except ValueError:
            self.logger.error("[ChzzkChat.__init__] 쿠키가 정상적이지 않습니다. 미로그인 상태로 진행합니다.")

        # Connect WebSocket upon initialization
        self.connect()


    def init_logger(self):
        formatter = logging.Formatter("[%(asctime)s][%(levelname)s]%(message)s")
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG) # logging.DEBUG
        file_handler = logging.FileHandler("chat.log", mode="a+")
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


    def play_tts(self, message: str, language: str, filename="tts.mp3"):
        self.logger.debug("[play_tts] Save TTS to file")
        tts = gTTS(text=message, lang=language)
        tts.save(filename)

        self.logger.debug("[play_tts] Initialize TTS")
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.set_volume(1.0)

        self.logger.debug("[play_tts] Run TTS")
        pygame.mixer.music.play()
        clock = pygame.time.Clock()
        while pygame.mixer.music.get_busy():
            clock.tick(1)

        self.logger.debug("[play_tts] Destroy TTS")
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        pygame.mixer.quit()

        self.logger.debug("[play_tts] Remove TTS")
        os.remove(filename)


    def connect(self):
        # Init websocket
        self.sock = WebSocket()
        self.sock.connect("wss://kr-ss1.chat.naver.com/chat")

        # Authentication Packet
        self.logger.info("[ChzzkChat.connect] %s 채팅창에 로그인 중 ...", self.channelName)
        send_dict = {
            "cmd": CHZZK_CHAT_CMD.connect,
            "tid": 1,
            "bdy": {
                "uid": self.userIdHash,
                "devType": 2001,
                "accTkn": self.accessToken,
                "auth": "READ",
            },
        }
        self.sock.send(json.dumps(dict(send_dict, **self.default_dict)))
        sock_response = json.loads(self.sock.recv())
        self.sid = sock_response["bdy"]["sid"]
        self.logger.debug("[ChzzkChat.connect] SID %s", self.sid)

        # Recent Chat Request Packet
        self.logger.info("[ChzzkChat.connect] %s 채팅창 로딩중 ...", self.channelName)
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
        while True:
            try:
                raw_message = self.sock.recv()
                self.logger.debug("[ChzzkChat.run] Raw message: %s", raw_message)
                self.handler(json.loads(raw_message))

            except KeyboardInterrupt:
                break

            except Exception as exc:
                self.logger.error("[ChzzkChat.run] Exception: %s", exc)
                self.connect()
                raw_message = self.sock.recv()


    def handler(self, raw_message: str):
        chat_cmd = int(raw_message["cmd"])

        match chat_cmd:
            case CHZZK_CHAT_CMD.chat:
                chat_type = "채팅"

            case CHZZK_CHAT_CMD.donation:
                chat_type = "후원"

            case CHZZK_CHAT_CMD.pong:
                self.logger.debug("[ChzzkChat.handler] PONG 패킷이 왔습니다.")
                return

            case CHZZK_CHAT_CMD.ping:
                self.logger.debug("[ChzzkChat.handler] PONG 패킷을 보냅니다.")
                self.sock.send(json.dumps({"ver": "2", "cmd": CHZZK_CHAT_CMD.pong}))

                # 방송 시작시 chatChannelId가 달라지는 문제
                if self.chatChannelId != api.fetch_chatChannelId(self.streamer):
                    self.logger.info("[ChzzkChat.handler] 채널ID가 달라졌으므로 다시 채팅을 불러옵니다.")
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
            self.logger.info("[ChzzkChat.handler][%s] %s: %s", chat_type, nickname, chat_message)
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
