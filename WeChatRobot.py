import hashlib
import json
import time
import xml.etree.ElementTree as ET

import requests
import werobot
from flask import Flask, request, make_response

import WeChatGPT
import settings
from RedisUtil import RedisTool

app = Flask(__name__)
weToken = settings.Config.weToken

# token是微信公众号用来指定接入当前云服务器的服务的凭证，代表是自己人接入的，等一下就有什么用了
robot = werobot.WeRoBot(token=weToken)
hasRequest = None

"""
    微信公众号验证 token
"""


def checkToken():
    signature = request.args.get("signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    echostr = request.args.get("echostr", "")

    print("handle/GET func: signature, timestamp, nonce, echostr, token: ", signature, timestamp, nonce, echostr)

    token = weToken
    data = [token, timestamp, nonce]
    data.sort()
    temp = ''.join(data)
    sha1 = hashlib.sha1(temp.encode('utf-8'))
    hashcode = sha1.hexdigest()
    print("hashcode=", hashcode)

    if hashcode == signature:
        print("wechat commit check OK")
        return echostr
    else:
        print("GET error input msg")
        return "error-return\r\n"


"""
    微信公众号用户消息对话
"""


def getHistoryMsg(FromUserName):
    """
    查看历史对话， 仅支持查看 clearSessionTime/60 分钟内的对话记录
    :param FromUserName: 微信用户 id
    :return:
    """
    hisTime = "仅支持查看 " + str(settings.Config.clearSessionTime / 60) + " 分钟内的对话记录"
    redis_tool = RedisTool().get_client()
    try:
        weChatToken = "WeChatGPT_" + FromUserName

        resultMsg = ""
        messages = redis_tool.get(weChatToken)
        if messages:
            messages = json.loads(messages)
            for msg in messages:
                if msg["role"] == "user":
                    resultMsg += "我问: " + msg["content"] + "\n"
                else:
                    resultMsg += "助手: " + msg["content"].replace("\n\n", "\n") + "\n------------------- \n\n"
        else:
            resultMsg = "未查询到历史对话记录（" + hisTime + "）"

        print(f"用户{FromUserName}的历史会话如下：\n{resultMsg}")
        return resultMsg
    except Exception as e:
        print(f"An redis error occurred: {e}")
        raise ValueError("对不起，由于当前访问量过高，当前提问已被限制，请重新提问，谢谢~")
    finally:
        redis_tool.close()


def intercept_byte_length(text):
    """
    从后往前截取 n 个字节
    首先，我们需要计算开始和结束索引
    :param text: 要截取字节的文本
    :return: 截取后的新文本字符串
    """
    byte_count = 0
    start_index = len(text)

    for i, char in enumerate(reversed(text)):
        byte_count += len(char.encode('utf-8'))
        if byte_count >= settings.Config.interceptionLength:
            start_index = len(text) - i - 1
            break

    # 使用切片操作从后往前截取字符串
    result = text[start_index:]
    return result


def getLastAnswer(FromUserName):
    """
    获取上一条助手回复的消息
    :param FromUserName: 用户 id
    :return: 若助手回复了，则返回 content ，否则返回 None
    """
    outputContent = []
    sessionMsg = WeChatGPT.dealUserSession(FromUserName, False)
    if sessionMsg:
        if len(sessionMsg) > 0:
            # 取最后一套，判断是不是 assistant 消息，如果是，说明回复了，如果不是，说明尚未回复
            outputContent = [sessionMsg[-1]]

    # 判断是否已经回复，如果已经回复，取最后一条 assistant
    if len(outputContent) > 0 and outputContent[0]["role"] == WeChatGPT.ROLE_ASSISTANT:
        return outputContent[0]["content"].replace('\n\n', '\n')
    else:
        return None


def chatRobot():
    # 解析微信消息
    xmlData = ET.fromstring(request.stream.read())
    msg_type = xmlData.find('MsgType').text
    # 文本类型
    ToUserName = xmlData.find('ToUserName').text
    FromUserName = xmlData.find('FromUserName').text
    CreateTime = xmlData.find('CreateTime').text
    content = None

    start_time = time.time()
    print(f"用户{FromUserName}请求开始时间=={start_time}, msg_type={msg_type}", flush=True)

    if msg_type == 'voice' and settings.Config.VoiceSwitch:
        # 语音消息，先将语音转换为文字后，再调用文本流程
        try:
            mediaId = xmlData.find('MediaId').text
            # 需要开启微信接收语音识别结果【公众号-设置与开发-接口权限处开启接收消息-接收语音识别结果】
            content = xmlData.find('Recognition').text
            print(f"用户{FromUserName}输入了语音消息，语音MediaId为{mediaId}, 语音结果为：{content}")
            # # 通过临时素材接口获取语音 url https://developers.weixin.qq.com/doc/offiaccount/Asset_Management/Get_temporary_materials.html
            # url = f"https://api.weixin.qq.com/cgi-bin/media/get?access_token={settings.Config.weToken}&media_id={mediaId}"
            # response = requests.get(url)
            # voice_url = response.url
            # print(f"用户{FromUserName}的语音消息 voice_url 为：{voice_url}")
            # response = requests.get(voice_url)
            # # 将语音生成 voice.amr 文件存入本地
            # filepath = "voice/" + FromUserName + "_voice.amr"
            # with open(filepath, 'wb') as f:
            #     f.write(response.content)
            #
            # content = BaiDuVoice.getContent(filepath)
            msg_type = 'text'

            print(f"用户{FromUserName}的语音转文字成功：{content}")
        except Exception as e:
            print(f"解析语音失败, {e}")
            return generate_response_xml(FromUserName, ToUserName,
                                         '语音提问（中国-普通话）功能升级维护中...\n\n请先使用文本消息提问，感谢理解！')

    if msg_type == 'text':
        if content is None:
            content = xmlData.find('Content').text
        print("=======================================================")
        print(
                f"用户请求信息：ToUserName={ToUserName},FromUserName={FromUserName},CreateTime={CreateTime}, Content={content}",
                flush=True)
        print("=======================================================")

        if content == '继续' or content == '[继续]' or content == '【继续】':
            print(f'用户{FromUserName}输入了{content}，已进入获取上条消息功能！')
            # 睡 3s 再回复，期间加上前面重试的14s 一共 17s 也差不多了。

            lastContent = getLastAnswer(FromUserName)
            # 判断是否已经回复，如果已经回复，取最后一条 assistant
            if lastContent is None:
                # 如果还没返回结果，睡 3 秒再查一次，以免影响正常的继续查看
                time.sleep(3)
                lastContent = getLastAnswer(FromUserName)
                if lastContent is None:
                    lastContent = "GPT尚未解析完成，请稍后回复「继续」以获取最新结果!\n\n哥们的服务部署在美国硅谷，网络传输会有延迟，请耐心等待...\n\n【强烈建议】回复【功能说明】查看功能清单以及使用说明（为您排惑），基本上每天都会支持一些新功能！\n\n如您使用完毕，可以回复【stop】或【暂停】来结束并情空您的对话记录！"

            return generate_response_xml(FromUserName, ToUserName, lastContent)

        elif content == '历史对话' or content == '历史消息' or content == '历史记录':
            print(f'用户{FromUserName}输入了{content}，已进入获取历史对话功能！')
            msg = getHistoryMsg(FromUserName)
            if len(msg.encode("utf-8")) > settings.Config.interceptionLength:
                msg = intercept_byte_length(
                        msg) + '\n\n根据微信官方文档，文本消息的内容最多不超过 2048 个字节（一般一个英文字符占用1个字节，一个中文字符占用2-4个字节）, 所以只返回最新记录的部分文字'
            return generate_response_xml(FromUserName, ToUserName, msg)
        elif content == '功能说明' or content == '使用说明':
            print(f'用户{FromUserName}输入了{content}，已进入获取功能说明功能！')
            msg = "如果您来到了这里，说明你可能遇到了问题，这里给您充分解答如下：\n\n"
            msg += " 1、回复「继续」查阅 GPT 的最后一次回答（并不是让gpt继续写，千万别混淆） \n\n"
            msg += " 2、回复「继续写」可以让GPT联想对话上下文继续为你撰写或重新回答你的问题（伴随着下一次的回复一定是「继续」）！\n\n"
            msg += " 3、输入「历史对话」可以查看您的所有对话记录（1小时内如果无对话，将为您清空会话内容，保证您的隐私）\n\n"
            msg += " 4、支持输入语音消息（仅支持中国普通话，时间不要太长）\n\n"
            msg += "注意事项\n\n"
            msg += " 1、若出现「请稍后回复『继续』以获取最新结果!」是因为微信公众号有5s访问超时限制，而哥们服务器部署在美国硅谷，网络传输一个来回要绕一个地球，所以慢很正常。且无客服消息接口权限，所以大家见谅~\n\n"
            msg += " 2、回复「历史对话」，可以查看您的所有对话记录，但仅在一小时内有效，如果一小时内无任何对话活动，我将为您清空会话记录，保证您的隐私安全。另一方面也是我个人经费有限，无法支撑所有人的数据。\n\n"
            msg += " 3、我会定期在公众号文章中分享一些圈内资讯或技术实践等，感兴趣可以关注一下\n\n"
            msg += "另外，哥们完全免费为大家提供便利，但是也投入了上千元，而且每个月都有服务器等各项费用产生（对个人来说，压力蛮大的），如果您觉得好用，可以在公众号文章中给点打赏（已开启打赏功能），这会给我带来更大的动力坚持做下去，最后，再次感谢您的理解与支持！"

            msg += "\n\n如果您也想一起研究 ChatGPT 或给出优化建议可以与我联系，微信号同名：javastarboy"
            return generate_response_xml(FromUserName, ToUserName, msg)
        else:
            # 是否结束会话？
            result = checkIsStop(FromUserName, ToUserName, content)
            if result:
                return result

        if (start_time - float(CreateTime)) > 5:
            # 微信的重试请求中，参数不变，所以可以用当前请求 - CreateTime来计算是不是超时重试场景
            # 字段逻辑是由 微信重试触发返给客户端的，并非客户端主动请求响应的（5s 重试一次，第三次的时候若还没通则相应给客户端）
            if 10 < (start_time - float(CreateTime)) < 15:
                # 微信第三次请求时判断一下 GPT 助手是否已经回复，如果回复了，则返回(最后等 4s ，相当于用户共等了 14 秒)
                time.sleep(4)
                lastContent = getLastAnswer(FromUserName)
                if lastContent is None:
                    print("请求超时，耗时：", (time.time() - float(CreateTime)))
                    lastContent = "GPT马上处理完，就差一丢丢了，请回复 「继续」 查看结果!\n\n哥们的服务部署在美国硅谷，网络传输会有延迟，请耐心等待...\n\n【强烈建议】回复【功能说明】查看功能清单以及使用说明（为您排惑），基本上每天都会支持一些新功能！\n\n如您使用完毕，可以回复【stop】或【暂停】来结束并情空您的对话记录！"
                return generate_response_xml(FromUserName, ToUserName, lastContent)
            else:
                # 微信第二次请求, 因为没有客服接口，为了尽量提升用户体验，咱们等到微信第三次请求再决定是否让客户回复继续获取结果
                print("微信第二次请求进来了，睡 6s，强制超时进行第三次请求")
                time.sleep(6)
                # 虽然已经超时了，但是也要响应一下，以免后台异常
                return generate_response_xml(FromUserName, ToUserName, 'success')
        else:
            print(f"用户{FromUserName}开始请求 OpenAI,content={content}")
            output_content = weChatGpt(content, FromUserName)
            end_time = time.time()
            print(f"用户{FromUserName}请求结束时间={end_time}")
            if (end_time - start_time) < 5:
                response = generate_response_xml(FromUserName, ToUserName, output_content)
                return response
            else:
                # 虽然已经超时了，但是也要响应一下，以免后台异常
                # TODO: 如果是企业主体的公众号，这里应该调用客服消息接口主动推送消息给客户
                print('！！！！！！！！GPT 解析完成！！！！！！！！！')
                print('公众号端回复"继续"即可获取最新结果! 当前结果为：', output_content)
                return generate_response_xml(FromUserName, ToUserName, 'success')
    else:
        return generate_response_xml(FromUserName, ToUserName,
                                     '对不起，目前仅支持文本消息以及语音消息（中国-普通话），可以试试在对话框输入文字来向我提问！')


def generate_response_xml(FromUserName, ToUserName, output_content):
    """
    解析微信公众号 xml 报文结构
    :param FromUserName:
    :param ToUserName:
    :param output_content:
    :return:
    """
    reply = '''
    <xml>
    <ToUserName><![CDATA[%s]]></ToUserName>
    <FromUserName><![CDATA[%s]]></FromUserName>
    <CreateTime>%s</CreateTime>
    <MsgType><![CDATA[text]]></MsgType>
    <Content><![CDATA[%s]]></Content>
    </xml>
    '''
    response = make_response(reply % (FromUserName, ToUserName, str(int(time.time())), output_content))
    response.content_type = 'application/xml'
    print(f"output_content = {output_content} and generate_response_xml response={response}")
    return response


def get_time(f):
    """
    计算方法耗时
    """

    def inner(*arg, **kwarg):
        s_time = time.time()
        res = f(*arg, **kwarg)
        e_time = time.time()
        print('=============ChatGPT 耗时：{}秒=============='.format(e_time - s_time))
        print("=======================================================")
        return res

    return inner


def validUpMsgHasRtn(FromUserName):
    """
    判断上次的问题是否已经解答，如果没有，需要等待，以免会话 session 异常
    :param FromUserName: 用户 id
    :param messages: 问题消息
    :return: 如果返回有值代表尚未回答完毕，返回值为上次提问的问题； 如果返回为 None, 则代表已经返回结果，继续执行
    """
    redis_tool = RedisTool().get_client()
    try:
        weChatToken = "WeChatGPT_" + FromUserName

        messages = redis_tool.get(weChatToken)
        if messages:
            messages = json.loads(messages)
            upContent = [messages[-1]]
            if upContent[0]["role"] == "user":
                return "您上一次的提问「" + upContent[0]["content"] + "」GPT正在快马加鞭解析中，请先回复「继续」获取结果后再继续提问，感谢理解~"
            print(f"用户{FromUserName}进行了重复提问，已限制")
        else:
            return None
    except Exception as e:
        print(f"An redis error occurred: {e}")
        return "对不起，由于当前访问量过高，当前提问已被限制，请重新提问，谢谢~"
    finally:
        redis_tool.close()


@get_time
def weChatGpt(messages, FromUserName):
    """
      与 ChatGPT 交互
    :param messages: 用户发送的消息
    :param FromUserName: 用户 id
    :return: gpt 助手消息
    """
    noReq = validUpMsgHasRtn(FromUserName)
    if noReq:
        return noReq
    else:
        return WeChatGPT.completion(WeChatGPT.dealMsg(WeChatGPT.ROLE_USER, messages, '1', FromUserName), FromUserName)


def checkIsStop(FromUserName, ToUserName, content):
    stopList = ['暂停', 'stop', 'STOP', 'Stop', '结束', '停止']
    if stopList.__contains__(content):
        msg = WeChatGPT.clearMsg(FromUserName)
        return generate_response_xml(FromUserName, ToUserName, msg)
    else:
        return None


"""
    获取微信用户信息
"""


def getUserInfo(openId):
    APP_ID = 'wxc32a24c2ebbc8f16'
    APP_SECRET = 'c23af7032f16e2dda7d7469e760a37ba'

    # 第一步：获取 token
    # https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=wxc32a24c2ebbc8f16&secret=c23af7032f16e2dda7d7469e760a37ba
    url = "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=" + APP_ID + "&secret=" + APP_SECRET
    response = requests.get(url)
    accessToken = response.content

    # 第二步：根据openid获取用户信息
    urlId = "https://api.weixin.qq.com/cgi-bin/user/info?access_token=" + accessToken + "&openid=" + openId
    response = requests.get(url)
    nickname = response.content

    return nickname
