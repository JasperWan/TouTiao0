import json
from hashlib import md5
import os
from json import JSONDecodeError
import requests
import re
from urllib.parse import urlencode
from requests.exceptions import RequestException
from config import *
import pymongo
from multiprocessing import Pool

# 声明mongodb对象
client = pymongo.MongoClient(MONGO_URL,connect=False)
db = client[MONGO_DB]


def get_page_index(offset,keyword,headers):
    """请求索引页"""
    # 构造ajax请求
    data = {
        'offset':offset,
        'format':'json',
        'keyword':keyword,
        'autoload':'true',
        'count':'20',
        'cur_tab':3,
    }
    # 完整的url, urlencode把字典转化为url的请求参数
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    try:
        response = requests.get(url,headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            return None
    except RequestException:
        print('请求索引页失败')
        return None


def parse_page_index(html):
    try:
        # 将json字符串转化成json格式的变量
        data = json.loads(html)
        if data and 'data' in data.keys():
            for item in data.get('data'):
                # 构造一个生成器对每一个item进行循环，提取url
                yield item.get('url')
    except JSONDecodeError:
        return None


def get_page_detail(url,headers):
    """请求详情页"""
    try:
        response = requests.get(url,headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            return None
    except RequestException:
        print('请求详情页失败')
        return None


def parse_page_detail(html,detail_url,headers):
    """解析详情页"""
    # 提取组图title
    pattern_title = re.compile("BASE_DATA\.galleryInf.*?title.*?\'(.*?)\',",re.S)
    try:
        title = re.search(pattern_title,html)
        if title:
            title = title.group(1)
            # print(title)
    except Exception as e:
        print(e)

    # 提取详情页图片地址
    pattern = re.compile('JSON\.parse\(\"(.*?)\"\),', re.S)
    result = re.search(pattern,html)
    # 必须做判断
    if result:
        temp_result = str(result.group(1))
        results = temp_result.replace("\\","")
        data = json.loads(results)
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            # 图片url
            images = [item.get('url') for item in sub_images]
            # 请求下载图片url
            for image in images:
                get_download_image(image,headers)
            return {
                'title':title,
                'url':detail_url,
                'images_url':images
            }

def save_to_mongo(result):
    """存储到mongo"""
    if result:
        if db[MONGO_TABLE].insert(result):
            print('存储到MongoDB成功',result)
            return True
        return False


def get_download_image(url,headers):
    """请求图片地址"""
    print('正在下载',url)
    try:
        response =requests.get(url,headers=headers)
        if response.status_code == 200:
            # 保存
            save_image(response.content) # content返回二进制内容
        else:
            return None
    except RequestException:
        print('图片下载失败')
        return None


def save_image(content):
    """存储图片"""
    # 文件名称：路径/文件名.后缀
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(),'jpg')  # md5去重,hexdigest返回摘要，作为十六进制数据字符串值
    # 判断文件是否存在
    if not os.path.exists(file_path):
        with open(file_path,'wb') as f:
            f.write(content)
            f.close()


def main(offset):
    headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"}
    html = get_page_index(offset,KEYWORD,headers)
    # print(html)
    detail_urls = parse_page_index(html)
    for detail_url in detail_urls:
        # print(detail_url)
        contents = get_page_detail(detail_url,headers)
        # print(contents)
        if contents:
            result = parse_page_detail(contents,detail_url,headers)
            # print(result)
            if result:
                save_to_mongo(result)


if __name__ == '__main__':
    # offset = 0
    # 20页
    offset = [x*20 for x in range(GROUP_START,GROUP_END)]
    # main(offset)
    # 多进程
    pool = Pool()
    pool.map(main,offset)




