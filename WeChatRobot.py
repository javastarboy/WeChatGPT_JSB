import hashlib
import json
import random
import time
import xml.etree.ElementTree as ET

import requests
import werobot
from flask import Flask, request, make_response

import WeChatGPT
import get_billing_usage
import settings
from RedisUtil import RedisTool

app = Flask(__name__)
weToken = settings.Config.weToken

# token是微信公众号用来指定接入当前云服务器的服务的凭证，代表是自己人接入的，等一下就有什么用了
robot = werobot.WeRoBot(token=weToken)
hasRequest = None


def checkToken():
    """
    微信公众号验证 token
    :return:
    """
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


def getLastContentByLoop(firstTime, lastTime, CreateTime, FromUserName, failureMsg):
    """
    递归调用，因为没有客服消息接口权限，满足微信 5s 重试机制
    :param firstTime: 循环开始时间
    :param lastTime: 循环结束时间
    :param CreateTime: 用户第一次请求时间
    :param FromUserName: 用户 ID
    :param failureMsg: 失败话术
    :return:
    """
    current_time = time.time()
    while firstTime <= (current_time - float(CreateTime)) <= lastTime:
        lastContent = getLastAnswer(FromUserName)
        if lastContent:
            break
        # 若gpt尚未返回结果，则睡一秒继续试，直到 5s 结束进入微信下一次的重试
        time.sleep(1)
        current_time = time.time()

    if lastContent:
        return lastContent
    else:
        return failureMsg


def getDescription():
    """功能说明"""

    msg = "【功能说明解答如下】\n\n"
    msg += "【见面礼1】价值298元ChatGPT及AI绘画学习手册👇\nhttps://ydyrb84oyc.feishu.cn/docx/UVLydQxKnowuqmx5mAycm7RdnJg \n\n"
    msg += "【见面礼2】国内永久免费的ChatGPT网页版👇\nhttps://www.jsbcp.top/ \n\n"
    msg += "【见面礼3】若需开通 GPT-4 使用权限，请回复「GPT4」 \n"
    msg += "-----------------\n"
    msg += " 1、此公众号支持文本、语音消息（中国普通话）与ChatGPT进行对话！\n\n"
    msg += " 2、按照「查询余额+api_key」的格式输入消息（例如【查询余额 sk-adsf****2341】）即可查询您的api_key费用账单。\n我们承诺：您的账单数据会自动清除，且不消耗您的token。\n\n"
    msg += " 3、视频号 javastarboy 也已推出视频版相关教程，烦请用您发财的小手帮忙点个关注，十分感谢！\n\n"
    msg += "-----注意事项-----\n"
    msg += " 1、回复「继续」是查阅GPT的最后一次回答（并不是让GPT继续写，千万别混淆） \n\n"
    msg += " 2、回复「继续写」可以让GPT联想对话上下文继续为你撰写或重新回答你的问题（伴随着下一次的回复一定是「继续」）！\n\n"
    msg += " 3、输入「历史对话」可以查看您的所有对话记录（1小时内若无对话，将为您清空会话内容，保证您的隐私）\n\n"
    msg += " 4、若出现「请稍后回复『继续』以获取最新结果」是因为微信公众号有5s访问超时限制，而哥们服务器部署在美国硅谷，网络传输一个来回要绕一个地球，所以慢见谅~\n\n"
    msg += " 5、公众号、视频号文章中分享很多AI圈内资讯、教程、以及技术实践等，感兴趣可以关注一下\n\n"
    msg += "欢迎加入🔥AI2.0实验室交流微信群：https://www.jsbcp.top/%E5%BE%AE%E4%BF%A1%E4%BA%A4%E6%B5%81%E7%BE%A4.png"
    return msg


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
        if content.startswith("查询余额"):
            if content.startswith("查询余额sys"):
                # 查询微信公众号当前 key 的月
                key = random.choice(settings.Config.chat_gpt_key.split(','))
            else:
                # 用户提供的 key
                start = content.find("sk-")
                if start > 0:
                    key = content[start:]
                else:
                    lastContent = "对不起，您输入的指令有误。请按照「查询余额+api_key」的格式输入，例如【查询余额 sk-adsfasdf234123412341】\n注意：为保证您的隐私安全，查询结果仅保存 60 分钟，60 分钟后会自动清除 session 记录。"
                    return generate_response_xml(FromUserName, ToUserName, lastContent)

            lastContent = get_billing_usage.getUsage(FromUserName, key)
            return generate_response_xml(FromUserName, ToUserName, lastContent)
        if content == 'openai-proxy':
            lastContent = "百度网盘链接: https://pan.baidu.com/s/1YSNX3c4F-7iKWZmgeKycVA?pwd=star \n提取码: star --来自百度网盘超级会员v5的分享"
            return generate_response_xml(FromUserName, ToUserName, lastContent)
        if content == 'AI孙燕姿' or content == 'Ai孙燕姿' or content == 'ai孙燕姿':
            lastContent = "链接: https://pan.baidu.com/s/1lRTjKJ9MyKK1hSkYXan9IA?pwd=8888 提取码: 8888 --来自百度网盘超级会员v5的分享"
            return generate_response_xml(FromUserName, ToUserName, lastContent)
        if content == 'GPT4密码' or content == 'GPT4' or content == 'gpt4密码' or content == 'gpt4':
            lastContent = "▶ 【2023暑期钜惠】加入即可无限免费使用GPT-4👇\nhttps://www.jsbcp.top/2023%E6%9A%91%E6%9C%9F%E9%92%9C%E6%83%A0.png\n\n▶ 免费版 ChatGPT 网站升级版：https://www.jsbcp.top/\n  👉 GPT3.5模型：永久免费使用！ \n  👉 GPT4.0模型：考虑大家需求不同，支持按量付费（用多少买多少）\n  套餐介绍：https://ydyrb84oyc.feishu.cn/docx/XO3AdeWXZo5l8YxrGEHcLFo6n5p\n\n▶ 也可点击链接扫码加入【🔥AI2.0实验室】微信群获得更多福利！\n https://www.jsbcp.top/%E5%BE%AE%E4%BF%A1%E4%BA%A4%E6%B5%81%E7%BE%A4.png"
            return generate_response_xml(FromUserName, ToUserName, lastContent)
        if content == 'AI源码' or content == '微信群二维码':
            lastContent = "欢迎开启 OpenAI 人工智能之旅，点击链接扫码加入微信群【🔥AI2.0实验室 | 交流学习1群】即可获取！\n https://www.jsbcp.top/%E5%BE%AE%E4%BF%A1%E4%BA%A4%E6%B5%81%E7%BE%A4.png"
            return generate_response_xml(FromUserName, ToUserName, lastContent)
        elif content == '继续' or content == '[继续]' or content == '【继续】':
            print(f'用户{FromUserName}输入了{content}，已进入获取上条消息功能！')
            # 继续的时候，重试三秒
            failureMsg = 'GPT尚未解析完成，请稍后回复「继续」以获取最新结果!\n\n哥们的服务部署在美国硅谷，网络传输会有延迟，请耐心等待...\n\n【强烈建议】回复【功能说明】查看功能清单以及使用说明（为您排惑），基本上每天都会支持一些新功能！\n\n如您使用完毕，可以回复【stop】或【暂停】来结束并情空您的对话记录！'
            lastContent = getLastContentByLoop(0, 3, time.time(), FromUserName, failureMsg)

            return generate_response_xml(FromUserName, ToUserName, lastContent)
        elif content == '历史对话' or content == '历史消息' or content == '历史记录':
            print(f'用户{FromUserName}输入了{content}，已进入获取历史对话功能！')
            msg = getHistoryMsg(FromUserName)
            if len(msg.encode("utf-8")) > settings.Config.interceptionLength:
                msg = intercept_byte_length(
                        msg) + '\n\n根据微信官方文档，文本消息的内容最多不超过 2048 个字节（一般一个英文字符占用1个字节，一个中文字符占用2-4个字节）, 所以只返回最新记录的部分文字'
            return generate_response_xml(FromUserName, ToUserName, msg)
        elif content == '功能说明' or content == '使用说明' or content == '见面礼':
            print(f'用户{FromUserName}输入了{content}，已进入获取功能说明功能！')
            msg = getDescription()
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
                print("微信第三次请求进来了，开始循环 5s ，若超时则进入第三次请求")
                # 微信第三次请求时判断一下 GPT 助手是否已经回复，如果回复了，则返回
                failureMsg = "GPT马上处理完，就差一丢丢了，请回复「继续」查看结果!\n\n也可加我微信「javastarboy」拉你进入🔥AI2.0实验室\n\n⚠️建议回复「功能说明」查看使用说明，解锁新功能并获得超值见面礼[礼物]\n\n【2023暑期钜惠】加入即可\n✅免费获得120刀api_key👇\nhttps://www.jsbcp.top/2023%E6%9A%91%E6%9C%9F%E9%92%9C%E6%83%A0.png"
                lastContent = getLastContentByLoop(10, 15, CreateTime, FromUserName, failureMsg)

                return generate_response_xml(FromUserName, ToUserName, lastContent)
            else:
                print("微信第二次请求进来了，开始循环 5s ，若超时则进入第三次请求")
                failureMsg = 'success'
                lastContent = getLastContentByLoop(5, 11, CreateTime, FromUserName, failureMsg)

            return generate_response_xml(FromUserName, ToUserName, lastContent)
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
    elif msg_type == 'event':
        msg_event = xmlData.find('Event').text
        lastContent = "本公众号目前支持文本消息、语音消息（中国-普通话）向GPT提问，可以试试在对话框输入文字来向我提问！\n\n 【送您一份见面礼】请输入消息「见面礼」了解公众号使用技巧并免费获得价值298元的超值见面礼！\n\n【2023暑期钜惠】加入即可\n✅无限免费使用GPT-4👇\nhttps://www.jsbcp.top/2023%E6%9A%91%E6%9C%9F%E9%92%9C%E6%83%A0.png"
        if msg_event == 'subscribe':
            lastContent = "感谢关注，" + lastContent
        if msg_event == 'unsubscribe':
            lastContent = "十分遗憾没有留住小主您，如果哪里给您造成了疑惑，可以私信我给出建议或给您提供一些帮助。 我的微信号【javastarboy】"
        if msg_event == 'CLICK':
            event_key = xmlData.find('EventKey').text
            if event_key == 'reply_description':
                # 菜单点击事件，与 wechat_menu.py 的 button-type-click-key 绑定
                lastContent = getDescription()

        return generate_response_xml(FromUserName, ToUserName, lastContent)
    else:
        return generate_response_xml(FromUserName, ToUserName,
                                     '本公众号目前支持文本消息、语音消息（中国-普通话）向 GPT 提问，可以试试在对话框输入文字来向我提问！\n\n 【送您一份见面礼】请输入消息「功能说明」了解公众号使用技巧并获取见面礼')


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
        try:
            message = WeChatGPT.dealMsg(WeChatGPT.ROLE_USER, messages, '1', FromUserName)
            return WeChatGPT.completion(message, FromUserName)
        except Exception as e:
            resultMsg = str(e)
            WeChatGPT.dealMsg(WeChatGPT.ROLE_ASSISTANT, resultMsg, '2', FromUserName)
            return resultMsg


def checkIsStop(FromUserName, ToUserName, content):
    stopList = ['暂停', 'stop', 'STOP', 'Stop', '结束', '停止']
    if stopList.__contains__(content):
        msg = WeChatGPT.clearMsg(FromUserName)
        return generate_response_xml(FromUserName, ToUserName, msg)
    else:
        return None


def getUserInfo(openId):
    """
    获取微信用户信息
    :param openId: 微信 openid
    :return:
    """
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
