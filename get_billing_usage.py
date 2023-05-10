import datetime

# 用您的 API 密钥替换以下字符串
import requests
import settings
# 腾讯云函数服务代理
baseTxProxyUrl = settings.Config.baseTxProxyUrl

subscription_url = baseTxProxyUrl + "/v1/dashboard/billing/subscription"
# subscription_url = "https://api.openai.com/v1/dashboard/billing/subscription"

def getUsage(apikey):
    """
    查询账户 token 费用使用情况，查询余额
    :param apikey: apikey
    :return:
    """
    headers = {
        "Authorization": "Bearer " + apikey,
        "Content-Type": "application/json",
        "check": "1"
    }
    subscription_response = requests.get(subscription_url, headers=headers)
    if subscription_response.status_code == 200:
        data = subscription_response.json()
        total = data.get("hard_limit_usd")
    else:
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
        days = min(5, len(daily_costs))
        recent = f"最近{days}天使用情况  \n"
        for i in range(days):
            cur = daily_costs[-i-1]
            date = datetime.datetime.fromtimestamp(cur.get("timestamp")).strftime("%Y-%m-%d")
            line_items = cur.get("line_items")
            cost = 0
            for item in line_items:
                cost += item.get("cost")
            recent += f"\t{date}\t{cost / 100} \n"
    else:
        return billing_response.text

    return f"\n总额:\t{total:.4f}  \n" \
                f"已用:\t{total_usage:.4f}  \n" \
                f"剩余:\t{total-total_usage:.4f}  \n" \
                f"\n"+recent


print(getUsage(settings.Config.chat_gpt_key))
