import os
import hmac
import hashlib
import requests
import time
import json
import random
import google.generativeai as genai
from datetime import datetime, date

# 1. 환경 변수 및 설정
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY')
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
START_DATE = date(2026, 2, 2)  # 프로젝트 시작일

# 제미나이 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# --- [전략 로직 1: 자동 스케줄러] ---
def get_current_strategy():
    days_passed = (date.today() - START_DATE).days
    if days_passed < 14:
        return {"total": 3, "info_ratio": 0.7, "desc": "1단계: 신뢰 구축기"}
    elif days_passed < 30:
        return {"total": 4, "info_ratio": 0.7, "desc": "2단계: 성장 가속기"}
    else:
        return {"total": 6, "info_ratio": 0.6, "desc": "3단계: 수익 극대화기"}

# --- [전략 로직 2: 페르소나 및 프롬프트] ---
def generate_content_with_gemini(post_type, product_data=None):
    personas = [
        "깐깐한 살림 전문가", "IT 가성비 탐험가", 
        "실사용 후기 중심의 리뷰어", "데이터로 분석하는 쇼핑 가이드"
    ]
    persona = random.choice(personas)
    
    if post_type == "INFO":
        # 정보성 글 프롬프트
        prompt = f"""
        당신은 '{persona}'로서 독자에게 유용한 정보를 제공하는 블로거입니다.
        주제: 최근 쇼핑 트렌드나 가성비 제품을 고르는 팁에 대해 작성하세요.
        조건: 
        1. HTML 형식으로 작성 (<h2>, <p> 사용).
        2. 절대 상품 판매 링크를 넣지 마세요.
        3. 마지막에 '다음 포스팅에서는 구체적인 추천 제품을 다뤄보겠습니다'라는 문구를 넣으세요.
        """
    else:
        # 광고성(AD) 글 프롬프트 (표 삽입 및 Why 강조)
        prompt = f"""
        당신은 '{persona}'입니다. 아래 상품에 대한 매력적인 구매 가이드를 작성하세요.
        상품명: {product_data['productName']}
        가격: {product_data['productPrice']}원
        
        조건:
        1. '왜 이 제품을 지금 사야 하는지(Why)'를 논리적으로 설명하세요.
        2. 핵심 스펙을 HTML <table> 태그를 사용하여 깔끔한 비교표로 만드세요.
        3. HTML 형식으로 작성하세요.
        4. 말투는 친근하면서도 전문적이어야 합니다.
        """
    
    response = model.generate_content(prompt)
    return response.text

# --- [기존 쿠팡 로직 생략 - 그대로 유지] ---
# (get_authorization_header, fetch_coupang_products 함수는 이전 단계와 동일)

def main():
    strategy = get_current_strategy()
    print(f"🚀 {strategy['desc']} 실행 중...")
    
    # 오늘 게시할 글의 성격 결정 (INFO vs AD)
    # 실제 실행 시에는 GitHub Actions의 매 시간 실행 순서에 따라 결정하도록 구성 예정
    post_type = "AD" if random.random() > strategy['info_ratio'] else "INFO"
    
    if post_type == "AD":
        products = fetch_coupang_products("가성비 가전") # 키워드는 자동화 가능
        if products:
            content = generate_content_with_gemini("AD", products[0])
            print(f"✨ 광고성 글 생성 완료: {products[0]['productName']}")
    else:
        content = generate_content_with_gemini("INFO")
        print("📚 정보성 글 생성 완료")

    # [다음 단계] 여기서 생성된 content를 Blogger API로 전송할 예정입니다.

if __name__ == "__main__":
    main()
