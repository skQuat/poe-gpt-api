import toml
import time
import os
import sys
import logging
from flask import Flask, request
from flask_sock import Sock
import asyncio
from fastapi_poe.types import ProtocolMessage
from fastapi_poe.client import get_bot_response

file_path = os.path.abspath(sys.argv[0])
file_dir = os.path.dirname(file_path)
config_path = os.path.join(file_dir, "..", "config.toml")
config = toml.load(config_path)
proxy = config["proxy"]
timeout = config["api-timeout"] or config["timeout"] or 7


def convert_bot_name_reverse(name):
    bot_name_dict = {
        "Assistant": "chinchilla",
        "gpt-4": "beaver",
        "GPT-4-128k":"vizcacha",
        "Claude-3-Haiku-200k":"claude_3_haiku_200k",
        "Claude-3-Sonnet":"claude_2_1_bamboo",
        "Claude-3-Opus":"claude_2_1_cedar",
    }

    # 翻转字典
    reversed_dict = {value: key for key, value in bot_name_dict.items()}

    # 检查name是否在翻转的字典中
    if name in reversed_dict:
        return reversed_dict[name]
    else:
        return "Unknown name"

async def get_responses(api_key, prompt, bot):
    print("get_responses")
    print("[BOT] : ", bot)
    bot = convert_bot_name_reverse(bot)
    message = ProtocolMessage(role="user", content=prompt)
    buf = ""
    print("[BOT] : ", bot)
    # async for partial in get_bot_response(messages=[message], bot_name="GPT-3.5-Turbo", api_key=api_key):
    async for partial in get_bot_response(messages=[message], bot_name=bot, api_key=api_key):
        # print(partial.text)
        buf = buf + partial.text
    print(buf)
    return buf


'''
def get_client(token) -> Client:
    print("Connecting to poe...")
    client_poe = poe.Client(token, proxy=None if proxy == "" else proxy)
    return client_poe
'''

app = Flask(__name__)
sock = Sock(app)
sock.init_app(app)
client_dict = {}


def _add_token(token):
    if token not in client_dict.keys():
        try:
            ret = asyncio.run(get_responses(token, "Please return “OK”", "chinchilla"))
            #ret = get_responses(token, "Please return “OK”", "Assistant")
            if ret == "OK":
                # c = get_client(token)
                # client_dict[token] = c
                client_dict[token] = token
                return "ok"
            else:
                return "failed"
        except Exception as exception:
            print("Failed to connect to poe due to " + str(exception))
            return "failed: " + str(exception)
    else:
        return "exist"


@app.route('/add_token', methods=['GET', 'POST'])
def add_token():
    token = request.form['token']
    return _add_token(token)


@app.route('/ask', methods=['GET', 'POST'])
def ask():
    token = request.form['token']
    bot = request.form['bot']
    content = request.form['content']
    _add_token(token)
    #client = client_dict[token]
    try:
        #for chunk in client.send_message(bot, content, with_chat_break=True, timeout=timeout):
            #pass
        ret = asyncio.run(get_responses(token, content, bot))#get_responses(token, content, bot)
        return ret
        #return chunk["text"].strip()
    except Exception as e:
        # del client_dict[token]
        # client.disconnect_ws()
        errmsg = f"An exception of type {type(e).__name__} occurred. Arguments: {e.args}"
        print(errmsg)
        return errmsg


@sock.route('/stream')
def stream(ws):
    token = ws.receive()
    bot = ws.receive()
    content = ws.receive()
    _add_token(token)
    try:
        print("stream_get_responses")
        print("[BOT] : ", bot)
        bot = convert_bot_name_reverse(bot)
        message = ProtocolMessage(role="user", content=content)
        print("[BOT] : ", bot)

        # 创建一个新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 将异步函数包装在一个由事件循环运行的任务中
        async def async_get_bot_response():
            async for partial in get_bot_response(messages=[message], bot_name=bot, api_key=token):
                ws.send(partial.text)
                print(partial.text)

        # 运行直到异步函数完成
        loop.run_until_complete(async_get_bot_response())

    except Exception as e:
        errmsg = f"An exception of type {e.__class__.__name__} occurred. Arguments: {e.args}"
        print(errmsg)
        ws.send(errmsg)
    finally:
        # 关闭事件循环
        loop.close()
        ws.close()


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=config.get('gateway-port', 5100))
