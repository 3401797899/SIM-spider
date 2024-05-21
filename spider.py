from openai import OpenAI
import requests
from lxml import etree

# 百度智能云ocr识别API
API_KEY = ""
SECRET_KEY = ""

# ChatGPT API KEY
CHATGPT_API_KEY = ""

# ChatGPT prompt
PROMPT = """
你会得到一段通过ocr得到的关于流量卡的介绍信,你需要分析这些数据来了解这张卡,至少分析出以下数据：
1. 预充值金额: 【输出格式：100】(如:激活当月专属渠道首充50元享受优惠 - 50元, 激活强充100元话费享以下优惠 - 100元, 首充100后每月赠送180G通用流量 - 100元, 激活后七天内充值100元享受以下优惠不充值无法享受 - 100元等)
2. 初始价格:【输出格式：19】 (初始价格为第一个月(即首月)的价格,如:19元)
3. 最终价格:【输出格式：39】(3年后的价格,如: 39元)

请尽量保持准确性,不要偷懒,分析完后,将结果严格按以下列csv的格式发送给我，不需要给出原因：
{预充值金额},{初始价格},{最终价格}
如：100,19,39
"""

client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key=CHATGPT_API_KEY,
    base_url="https://api.chatanywhere.cn/v1",
)


# 获取某平台的基础流量卡信息
def get_172_product_info():
    url = "https://haokawx.lot-ml.com/Product/Index/1"
    r = requests.get(url)
    html = etree.HTML(r.text)
    products = html.xpath('//ul[@class="fa"]/li')
    product_info = []
    for product in products:
        name = product.xpath('./a/div[@class="f1"]/dd/h1/text()')[0]
        if name not in [i["name"] for i in product_info]:
            product_info.append(
                {
                    "name": name,
                    "pid": product.xpath("./a/@href")[0].split("&")[0].split("=")[-1],
                    "tongyong": product.xpath(
                        './a/div[@class="f1"]/dd/div[@class="b2"]/span[1]/text()'
                    )[0].split("\xa0")[-1],
                    "dingxiang": product.xpath(
                        './a/div[@class="f1"]/dd/div[@class="b2"]/span[2]/text()'
                    )[0].split("\xa0")[-1],
                    "tonghua": product.xpath(
                        './a/div[@class="f1"]/dd/div[@class="b2"]/span[3]/text()'
                    )[0].split("\xa0")[-1],
                }
            )
    return product_info


# 通过pid获取流量卡的介绍图片
def generate_pic(pid):
    url = f"https://haokawx.lot-ml.com/h5order/index?pudiD={pid}&userid=1"
    r = requests.get(url)
    html = etree.HTML(r.text)
    pic_url = html.xpath('//div[@class="view_8"]/div[@class="view_text"]/img/@src')[0]
    return pic_url


def ocr_pic(u):
    url = (
        "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token="
        + get_access_token()
    )

    payload = f"url={u}&detect_direction=false&detect_language=false&paragraph=false&probability=false"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    words = response.json()["words_result"]
    text = "\n".join([i["words"] for i in words])
    return text


def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": SECRET_KEY,
    }
    return str(requests.post(url, params=params).json().get("access_token"))


# 通过ocr结果进行分析
def chat(ocr_result):
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": ocr_result},
        ],
    )
    return completion.choices[0].message.content


products = get_172_product_info()

f = open("result.csv", "w")
f.write("名称,类型,预充值金额,初始价格,最终价格,通用流量,定向流量,通话时长\n")
for i in products:
    u = generate_pic(i["pid"])
    ocr_result = ocr_pic(u)
    result = chat(ocr_result).split(",")
    prestore, origin_price, final_price = result
    csv_result = f"{i['name']},{'长期卡' if origin_price == final_price else '短期卡'},{prestore},{origin_price},{final_price},{i['tongyong']},{i['dingxiang']},{i['tonghua']}"
    print(csv_result)
    f.write(csv_result + "\n")
f.close()
