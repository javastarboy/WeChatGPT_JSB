class Config(object):
    # 微信公众号的 token
    weToken = 'xxxxxxxxxxxxx'
    # javastarboy 的 api_key
    chat_gpt_key = 'xxxxxxxxxxxxx'
    # javastarboy 的腾讯云服务器函数服务，跳转硅谷区域代理
    baseTxProxyUrl = "xxxxxxxxxxxxx"
    # 也可以写完整的代理 url 
    txProxyUrl = "xxxxxxxxxxxxx"
    # session 自动失效时间，秒
    clearSessionTime = 3600
    # 历史对话返回字符长度
    interceptionLength = 1800

    # 语音识别开关
    VoiceSwitch = True
    # 百度语音识别：https://console.bce.baidu.com/ai/?_=1682589061589#/ai/speech/app/list
    BaiDU_APP_ID = 'xxxx'
    BaiDU_API_KEY = 'xxxx'
    BaiDU_SECRET_KEY = 'xxxx'

    # redis
    host = 'xxxxxxxxxxxxx'
    port = xxxx
    password = 'xxxxxxxxxxxxx'
    db = 0
    # cluster、sentinel、single
    model = "cluster"
    startup_nodes = [
        {'host': 'xxxxxxxxxxxxx', 'port': 26379},
        {'host': 'xxxxxxxxxxxxx', 'port': 26380},
        {'host': 'xxxxxxxxxxxxx', 'port': 26381},
        {'host': 'xxxxxxxxxxxxx', 'port': 26382},
        {'host': 'xxxxxxxxxxxxx', 'port': 26383},
        {'host': 'xxxxxxxxxxxxx', 'port': 26384}]
    sentinel_list = [
        ('xxxxxxxxxxxxx', '26379'),
        ('xxxxxxxxxxxxx', '26380'),
        ('xxxxxxxxxxxxx', '26381'),
        ('xxxxxxxxxxxxx', '26382'),
        ('xxxxxxxxxxxxx', '26383'),
        ('xxxxxxxxxxxxx', '26384')]
