from WeChatRobot import getHistoryMsg, generate_response_xml, intercept_byte_length

msg = getHistoryMsg("og1d3wowAH-mFz5FRf8Nf7Rlhw6o")
print(
    len("\n\n根据微信官方文档，文本消息的内容最多不超过 2048 个字（汉字或英文字母）, 所以只返回最新记录的部分文字".encode("utf-8")))
print(len(msg.encode("utf-8")))



if len(msg.encode("utf-8")) >= 1890:
    print("调整前长度："+str(len(msg.encode("utf-8"))))
    msg = intercept_byte_length(msg) + '\n\n根据微信官方文档，文本消息的内容最多不超过 2048 个字（汉字或英文字母）, 所以只返回最新记录的部分文字'
    print("调整后长度："+str(len(msg.encode("utf-8"))))
    print(generate_response_xml("og1d3wowAH-mFz5FRf8Nf7Rlhw6o", "og1d3wowAH-mFz5FRf8Nf7Rlhw6o", msg))
