import os, hmac, hashlib, requests, time, json, random, re, urllib.parse
from datetime import datetime, date
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 설정 및 환경 변수 안전 검사]
# ==========================================
BLOG_ID = os.environ.get('BLOGGER_BLOG_ID', '195027135554155574')
START_DATE = date(2026, 2, 2)

# Secrets 불러오기 (환경 변수 이름을 유연하게 체크합니다)
ACCESS_KEY = (os.environ.get('COUPANG_ACCESS_KEY') or '').strip()
SECRET_KEY = (os.environ.get('COUPANG_SECRET_KEY') or '').strip()
GEMINI_API_KEY = (os.environ.get('GEMINI_API_KEY') or '').strip()
REFRESH_TOKEN = (os.environ.get('BLOGGER_REFRESH_TOKEN') or os.environ.get('REFRESH_TOKEN') or '').strip()
CLIENT_ID = (os.environ.get('BLOGGER_CLIENT_ID') or os.environ.get('CLIENT_ID') or '').strip()
CLIENT_SECRET = (os.environ.get('BLOGGER_CLIENT_SECRET') or os.environ.get('CLIENT_SECRET') or '').strip()

# 인증 정보 유효성 검사 로그
if not CLIENT_ID: print("⚠️ 경고: CLIENT_ID가 비어있습니다. GitHub Secrets를 확인하세요.")
if not REFRESH_TOKEN: print("⚠️ 경고: REFRESH_TOKEN이 비어있습니다. GitHub Secrets를 확인하세요.")

# ==========================================
# [2. 거대 키워드 리스트 (300개)]
# ==========================================
HEALTH_KEYWORDS = [
    # 과일/채소/슈퍼푸드 (100개)
    "브로콜리 설포라판", "블루베리 안토시아닌", "토마토 라이코펜", "아보카도 불포화지방", "비트 식이섬유", "아스파라거스", "케일 해독", "시금치 루테인", "마늘 알리신", "양파 퀘르세틴",
    "사과 아침", "바나나 수면", "키위 소화", "석류 갱년기", "자몽 다이어트", "수박 이뇨", "딸기 비타민", "포도 심장", "레몬 해독", "파인애플 효소",
    "양배추 위건강", "당근 시력", "오이 수분", "단호박 부기", "고구마 변비", "청경채", "파프리카", "콜리플라워", "가지", "무 소화",
    "미나리 간", "쑥", "달래", "냉이", "고사리", "연근", "우엉", "마 뮤신", "도라지", "더덕",
    "상추 불면증", "깻잎 철분", "부추 정력", "미역 요오드", "다시마", "톳", "파래", "김", "매생이", "감태",
    "망고", "파파야", "코코넛", "무화과", "대추", "밤", "호두", "아몬드", "캐슈넛", "피스타치오",
    "브라질너트", "피칸", "해바라기씨", "호박씨", "치아씨드", "햄프씨드", "귀리 베타글루칸", "현미", "보리", "메밀",
    "율무", "조", "수수", "퀴노아", "병아리콩", "렌틸콩", "검은콩", "완두콩", "강낭콩", "작두콩",
    "생강 감기", "울금 커큐민", "계피 혈당", "고추 캡사이신", "후추", "산초", "허브", "바질", "로즈마리", "라벤더",
    
    # 육류/해산물/단백질 (100개)
    "닭가슴살", "소고기 단백질", "돼지고기 안심", "오리고기", "양고기", "연어 오메가3", "고등어", "굴 아연", "전복 타우린", "장어",
    "멸치 칼슘", "새우 키토산", "꽃게", "문어", "오징어", "달걀 콜린", "두부", "낫또", "청국장", "어묵",
    "명태", "대구", "갈치", "조기", "임연수", "가자미", "꽁치", "정배기", "숭어", "방어",
    "바지락", "재첩", "홍합", "꼬막", "가리비", "멍게", "해삼", "개불", "소라", "우렁이",
    "소고기 사태", "돼지 앞다리살", "닭다리살", "닭안심", "오리훈제", "추어탕", "염소고기", "사골", "도가니", "우족",
    
    # 영양제/증상/생활습관 (100개)
    "비타민C 추천", "비타민D 햇빛", "종합영양제", "유산균 고르는법", "오메가3 순도", "마그네슘 부족", "칼슘 흡수율", "아연 면역", "철분제 비타민C", "엽산",
    "밀크씨슬", "보스웰리아", "콘드로이친", "글루코사민", "엠에스엠(MSM)", "쏘팔메토", "루테인", "코엔자임Q10", "아르기닌", "카르니틴",
    "스피루리나", "클로렐라", "프로폴리스", "로열젤리", "화분", "맥주효모 탈모", "비오틴", "콜라겐", "히알루론산", "엘라스틴",
    "고혈압 식단", "당뇨 혈당", "고지혈증 혈관", "지방간 음식", "위염에 좋은", "장건강", "면역력 높이는", "피로회복", "눈건강", "뼈건강",
    "관절건강", "혈행개선", "기억력", "집중력", "스트레스 해소", "우울증 음식", "불면증 수면", "피부미용", "다이어트 식단", "해독주스",
    "반신욕 효과", "족욕", "명상", "복식호흡", "스트레칭", "유산소 운동", "근력 운동", "스쿼트", "플랭크", "걷기 운동",
    "수분 섭취", "충분한 수면", "스트레스 관리", "금연 효과", "금주", "자세 교정", "거북목 예방", "허리 통증", "무릎 통증", "어깨 결림",
    "대사증후군", "골다공증 예방", "빈혈", "부종 제거", "냉증", "갱년기 증상", "치매 예방", "구강 건강", "탈모 예방", "아토피"
]

# ==========================================
# [3. 핵심 기술 모듈]
# ==========================================
def get_image_html(kw):
    search_term = urllib.parse.quote(kw)
    img_url = f"https://source.unsplash.com/featured/?{search_term},health"
    return f"<div style='margin-bottom:25px; text-align:center;'><img src='{img_url}' style='max-width:100%; border-radius:15px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);'><br><small style='color:#777;'>※ {kw} 이미지 참고</small></div>"

def fetch_product(kw):
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={urllib.parse.quote(kw)}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    try:
        timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = timestamp + "GET" + path + query_string
        signature = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"
        res = requests.get(url, headers={"Authorization": auth, "Content-Type": "application/json"}, timeout=15)
        return res.json().get('data', {}).get('productData', []) if res.status_code == 200 else []
    except: return []

def generate_content(post_type, keyword, product=None):
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
        model = genai.GenerativeModel(target_model)
    except: model = genai.GenerativeModel('gemini-1.5-flash')

    persona = "당신은 건강 의학 전문 에디터입니다. 신뢰감 있고 전문적인 문체로 HTML 포스팅을 작성하세요."
    
    if post_type == "AD":
        prompt = f"{persona} 주제: '{keyword}'의 효능과 '{product['productName']}' 추천. 1,500자 이상 HTML로 작성. <table> 포함. 링크: <a href='{product['productUrl']}'>▶ 최저가 상세정보 확인</a>"
        footer = "<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
    else:
        prompt = f"{persona} 주제: '{keyword}'에 대한 정밀 가이드. 1,500자 이상 HTML로 작성. <table> 포함. 판매 링크 절대 금지."
        footer = ""

    try:
        res = model.generate_content(prompt).text
        # 기술 참고: 불필요한 마크다운 기호 제거
        clean_text = re.sub(r'\*\*|##|`|#', '', res)
        return get_image_html(keyword) + clean_text + footer
    except: return None

def post_to_blog(title, content):
    try:
        # 에러 발생 지점 방어 로직
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError("CLIENT_ID 또는 CLIENT_SECRET이 설정되지 않았습니다.")
            
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", 
                            client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
        if not creds.valid:
            creds.refresh(Request())
            
        service = build('blogger', 'v3', credentials=creds)
        res = service.posts().insert(blogId=BLOG_ID, body={"title": title, "content": content}).execute()
        return res.get('url')
    except Exception as e:
        print(f"❌ 발행 에러: {str(e)}")
        return None

# ==========================================
# [4. 메인 컨트롤러]
# ==========================================
def main():
    hour_idx = datetime.now().hour // 4 
    if hour_idx >= 3: 
        print(f"💤 휴식 모드 (슬롯 {hour_idx})")
        return

    is_ad = (hour_idx == 1) # 오후 4시경(Index 1)만 광고글
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {post_type} 발행 시작: {kw}")
    
    if post_type == "AD":
        products = fetch_product(kw.split()[0])
        if products:
            html = generate_content("AD", kw, products[0])
            if html:
                url = post_to_blog(f"[추천] {kw} 건강 관리를 위한 선택", html)
                if url: print(f"✅ 발행 성공: {url}")
        else:
            print("📦 상품 검색 실패. 정보글로 자동 전환.")
            post_type = "INFO"

    if post_type == "INFO":
        html = generate_content("INFO", kw)
        if html:
            url = post_to_blog(f"전문 가이드: {kw}의 놀라운 효능", html)
            if url: print(f"✅ 발행 성공: {url}")

if __name__ == "__main__":
    main()
