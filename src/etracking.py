import json
import re

import pytesseract
import requests
from bs4 import BeautifulSoup
from PIL import Image

url_base = "https://eservice.7-11.com.tw/e-tracking/"
url_search = url_base + "search.aspx"


def get_validate_image(url, session):
    resp = session.get(url)

    if resp.status_code != 200:
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    __VIEWSTATE = soup.find("input", id="__VIEWSTATE").get("value")
    __VIEWSTATEGENERATOR = soup.find("input", id="__VIEWSTATEGENERATOR").get("value")

    # Since BeautifulSoup will skip the first src=, so using re instead
    ValidateImage_url = url_base + re.search(
        'src="(ValidateImage\.aspx\?ts=[0-9]+)"', resp.text
    ).group(1)
    resp = session.get(ValidateImage_url)

    if resp.status_code != 200:
        resp.raise_for_status()
    else:
        with open("code.jpeg", "wb") as f:
            f.write(resp.content)

    return __VIEWSTATE, __VIEWSTATEGENERATOR


def get_code(OCR):
    # if OCR is False, then input the validation code manually
    if OCR == False:
        code = input("請輸入驗證碼: ")
    else:
        tesseract_config = "-c tessedit_char_whitelist=0123456789 --psm 8"
        code = pytesseract.image_to_string(
            Image.open("code.jpeg"), config=tesseract_config
        ).strip()
    return code


def post_search(url, __VIEWSTATE, __VIEWSTATEGENERATOR, txtProductNum, code, session):
    # Construct the payload which will be used in the POST request
    payload = {
        "__EVENTTARGET": "submit",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": __VIEWSTATE,
        "__VIEWSTATEGENERATOR": __VIEWSTATEGENERATOR,
        "txtProductNum": txtProductNum,
        "tbChkCode": code,
        "txtIMGName": "",
        "txtPage": 1,
    }
    resp = session.post(url, data=payload)

    if resp.status_code != 200:
        resp.raise_for_status()
    return resp.text


def parse_result(html: str):
    json_data = {
        "msg": "",
        "m_news": "",
        "result": {"info": {}, "shipping": {"timeline": []}},
    }
    soup = BeautifulSoup(html, "html.parser")

    # check if there is any alert message
    script = soup.find_all("script")
    for i in script:
        if "alert(" in i.get_text():
            return {"msg": i.get_text().split("alert('")[1].split("');")[0]}

    # check if there is any error message
    lbmsg = soup.find("span", id="lbMsg")
    if lbmsg != None and lbmsg.get_text() != "":
        return {"msg": lbmsg.get_text()}

    content_result = soup.find("div", id="content_result")
    if content_result == None:
        return {"msg": "查無資料"}

    # m_news
    json_data["m_news"] = content_result.find("div", class_="m_news").get_text()

    # result
    result = content_result.find("div", class_="result")

    # info
    info = result.find("div", class_="info")
    info_list = info.find_all("span")
    for i in info_list:
        json_data["result"]["info"][i.get("id")] = i.get_text()
    json_data["result"]["info"]["servicetype"] = info.find(
        "h4", id="servicetype"
    ).get_text()

    # shipping
    shipping = result.find("div", class_="shipping")
    shipping_list = shipping.find_all("p")
    for i in shipping_list:
        json_data["result"]["shipping"]["timeline"].append(i.get_text())

    json_data["msg"] = "success"

    return json_data


def etracking(txtProductNum: str, OCR: bool = True) -> dict:
    """
    7-11 e-tracking
    :param txtProductNum: The tracking number of 7-11
    :param OCR: Whether to use OCR to recognize the validation code
    """
    session = requests.Session()

    __VIEWSTATE, __VIEWSTATEGENERATOR = get_validate_image(url_search, session)
    code = get_code(OCR)
    html = post_search(
        url_search, __VIEWSTATE, __VIEWSTATEGENERATOR, txtProductNum, code, session
    )
    json_data = parse_result(html)

    while json_data["msg"] == "驗證碼錯誤!!":
        __VIEWSTATE, __VIEWSTATEGENERATOR = get_validate_image(url_search, session)
        code = get_code(OCR)
        html = post_search(
            url_search, __VIEWSTATE, __VIEWSTATEGENERATOR, txtProductNum, code, session
        )
        json_data = parse_result(html)

    return json_data


if __name__ == "__main__":
    res = etracking("87717609642")
    print(json.dumps(res, indent=4, ensure_ascii=False))
    res = etracking("87717609641")
    print(json.dumps(res, indent=4, ensure_ascii=False))
    res = etracking("87717609641567")
    print(json.dumps(res, indent=4, ensure_ascii=False))
