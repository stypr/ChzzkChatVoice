#!/usr/bin/python -u
#-*- coding: utf-8 -*-
from types import SimpleNamespace

# Code from https://github.com/kimcore/chzzk/blob/main/src/chat/types.ts\
CHZZK_CHAT_CMD = {
    'ping': 0,
    'pong': 10000,
    'connect': 100,
    'connected': 10100,
    'send_chat': 3101,
    'recent_chat': 15101,
    'request_recent_chat': 5101,
    'event': 93006,
    'chat': 93101,
    'donation' : 93102,
    'kick': 94005,
    'block': 94006,
    'blind': 94008,
    'notice': 94010,
    'pentalty': 94015
}
CHZZK_CHAT_CMD = SimpleNamespace(**{k: v for k, v in CHZZK_CHAT_CMD.items()})