import datetime

# 用您的 API 密钥替换以下字符串
import json

import requests
import settings
# 腾讯云函数服务代理
from RedisUtil import RedisTool
from WeChatGPT import dealUserSession

baseTxProxyUrl = settings.Config.baseTxProxyUrl

subscription_url = baseTxProxyUrl + "/v1/dashboard/billing/subscription"
credit_grants_url = baseTxProxyUrl + "/v1/dashboard/billing/credit_grants"
# subscription_url = "https://api.openai.com/v1/dashboard/billing/subscription"
preKey = 'USAGE-'


def getUsage(FromUserName, apikey):
    """
    查询账户 token 费用使用情况，查询余额
    订阅接口：https://api.openai.com/dashboard/billing/subscription
    查询有效期: https://api.openai.com/dashboard/billing/credit_grants
    根据日期查询账单详情：https://api.openai.com/v1/dashboard/billing/usage?start_date={start_date}&end_date={end_date}

    :param getLast: 获取上次余额结果，一般用于"继续"
    :param FromUserName: 用户 ID
    :param apikey: apikey
    :return:
    """
    redisKey = preKey + FromUserName + "-" + apikey
    try:
        redis_tool = RedisTool().get_client()
        # 默认一小时，每次更新数据都刷，如果一小时内都没有交互，默认删除 session
        usage = redis_tool.get(redisKey)
        if usage:
            # 查询结果保留 30 分钟
            return usage
        # 请求 openai 实时查询
        headers = {
            "Authorization": "Bearer " + apikey,
            "Content-Type": "application/json",
            "check": "1"
        }
        subscription_response = requests.get(subscription_url, headers=headers)
        # subscription_response = requests.get(credit_grants_url, headers=headers)
        if subscription_response.status_code == 200:
            data = subscription_response.json()
            total = data.get("hard_limit_usd")

            # 以下是 credit_grants_url 方案，获取有效期
            # total_usage = data["grants"]["data"][0]["used_amount"]
            # total = data["grants"]["data"][0]["grant_amount"]
            # effective_at = data["grants"]["data"][0]["effective_at"]
            # expires_at = data["grants"]["data"][0]["expires_at"]
        else:
            try:
                response_dict = json.loads(subscription_response.text)
                code = response_dict["error"]["code"]
                message = response_dict["error"]["message"]

                if code == "invalid_api_key":
                    return f"对不起, 您输入的 key 在OpenAI 官网查询无效或输入指令格式有误，请检查您的key是否正确或是否多输入了换行\n " \
                           f"\nOpenAI 官方返回错误信息如下:\n" + message + \
                           f"\n\n 如遇使用问题，请回复「功能说明」查看此公众号GPT 相关功能使用技巧，感谢您的理解与支持~"
                else:
                    return subscription_response.text
            except Exception as e:
                print("解析 usage 信息异常" + e)
                return subscription_response.text

        # start_date设置为今天日期前99天
        start_date = (datetime.datetime.now() - datetime.timedelta(days=99)).strftime("%Y-%m-%d")
        # end_date设置为今天日期+1
        end_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        billing_url = f"{baseTxProxyUrl}/v1/dashboard/billing/usage?start_date={start_date}&end_date={end_date}"
        # billing_url = f"https://api.openai.com/v1/dashboard/billing/usage?start_date={start_date}&end_date={end_date}"
        billing_response = requests.get(billing_url, headers=headers)
        if billing_response.status_code == 200:
            data = billing_response.json()
            total_usage = data.get("total_usage") / 100
            daily_costs = data.get("daily_costs")
            days = min(15, len(daily_costs))
            recent = f"最近{days}天使用情况  \n"
            for i in range(days):
                cur = daily_costs[-i - 1]
                date = datetime.datetime.fromtimestamp(cur.get("timestamp")).strftime("%Y-%m-%d")
                line_items = cur.get("line_items")
                cost = 0
                for item in line_items:
                    cost += item.get("cost")
                recent += f" {date}：{round(cost / 100, 4)} \n"

        else:
            try:
                response_dict = json.loads(billing_response.text)
                code = response_dict["error"]["code"]
                message = response_dict["error"]["message"]

                if code == "invalid_api_key":
                    return f"对不起, 您输入的 key 在OpenAI 官网查询无效，请检查您的 key 是否正确\n " \
                           f"\nOpenAI 官方返回错误信息如下:\n" + message + \
                           f"\n\n 如遇使用问题，请回复「功能说明」查看此公众号GPT 相关功能使用技巧，感谢您的理解与支持~"
                else:
                    return billing_response.text
            except Exception as e:
                print("解析 usage 信息异常" + e)
                return billing_response.text

        usage = f"总额:\t{total:.4f}  \n" \
                f"已用:\t{total_usage:.4f}  \n" \
                f"剩余:\t{total - total_usage:.4f}  \n" \
                f"\n" + recent

        # f"有止期起:\t{effective_at}  \n" \
        # f"有效期止:\t{expires_at}  \n" \

        redis_tool.setex(redisKey, settings.Config.clearSessionTime, usage)

        return usage
    except Exception as e:
        print(f"An redis error occurred: {e}")
    finally:
        redis_tool.close()


# 测试一下
print(getUsage("userId", settings.Config.chat_gpt_key))
