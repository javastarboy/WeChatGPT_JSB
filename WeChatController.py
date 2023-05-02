from flask import Flask, request

import WeChatRobot

app = Flask(__name__)
weToken = 'javastarboy'

# token是微信公众号用来指定接入当前云服务器的服务的凭证，代表是自己人接入的，等一下就有什么用了
# robot = werobot.WeRoBot(token=weToken)
outputContent = []
hasRequest = None


@app.route("/chatgpt", methods=['Post', 'GET'])
def chatgpt():
    # 验证 token
    if request.method == 'GET':
        print("微信 token 验证")
        return WeChatRobot.checkToken()
    else:
        return WeChatRobot.chatRobot()


if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=80, threaded=True)
