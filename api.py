import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def fetch_chat_channel_id(streamer_id: str) -> str:
    try:
        response = requests.get(
            f"https://api.chzzk.naver.com/polling/v2/channels/{streamer_id}/live-status",
            headers=HEADERS,
        ).json()
        return response["content"]["chatChannelId"]
    except:
        raise ValueError(f"[fetch_chat_channel_id] 잘못된 입력값 : {streamer_id}")


def fetch_channel_name(streamer_id: str) -> str:
    try:
        response = requests.get(
            f"https://api.chzzk.naver.com/service/v1/channels/{streamer_id}",
            headers=HEADERS,
        ).json()
        return response["content"]["channelName"]
    except:
        raise ValueError(f"[fetch_channel_name] 잘못된 입력값 : {streamer_id}")


def fetch_access_token(chat_channel_id: str, cookies: dict) -> str:
    try:
        response = requests.get(
            f"https://comm-api.game.naver.com/nng_main/v1/chats/access-token?channelId={chat_channel_id}&chatType=STREAMING",
            cookies=cookies,
            headers=HEADERS,
        ).json()
        return response["content"]["accessToken"], response["content"]["extraToken"]
    except:
        raise ValueError(f"[fetch_access_token] 잘못된 입력값 : {chat_channel_id}, {cookies}")


def fetch_user_id_hash(cookies: dict) -> str:
    try:
        response = requests.get(
            "https://comm-api.game.naver.com/nng_main/v1/user/getUserStatus",
            cookies=cookies,
            headers=HEADERS,
        ).json()
        return response["content"]["userIdHash"]
    except:
        raise ValueError(f"[fetch_user_id_hash] 잘못된 입력값 : {cookies}")
