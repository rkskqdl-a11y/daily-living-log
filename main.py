import os
import hmac
import hashlib
import requests
import time
import json
from datetime import datetime

# 깃허브 Secrets에서 키 불러오기
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY')
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY')

def get_authorization_header(method, path, query_string=""):
    """쿠팡 API 인증 헤더 생성 함수"""
    timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
    message = timestamp + method + path + query_string
    signature = hmac.new(bytes(SECRET_KEY, "utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"

def fetch_coupang_products(keyword):
    """특정 키워드로 쿠팡 상품 검색"""
    method = "GET"
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={keyword}&limit=5" # 5개 상품 수집
    url = f"https://link.coupang.com{path}?{query_string}"
    
    headers = {
        "Authorization": get_authorization_header(method, path, query_string),
        "Content-Type": "application/json"
    }
    
    response = requests.request(method, url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('data', {}).get('productData', [])
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return []

# 테스트 실행 (나중에 삭제하거나 수정할 부분)
if __name__ == "__main__":
    # 임시 테스트용 키워드
    products = fetch_coupang_products("가성비 가전")
    for p in products:
        print(f"상품명: {p['productName']}, 가격: {p['productPrice']}")
