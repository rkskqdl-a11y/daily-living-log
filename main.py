import os, hmac, hashlib, requests, time, json, random, re, urllib.parse
from datetime import datetime, date
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==========================================
# [1. 핵심 설정 정보]
# ==========================================
BLOG_ID = "195027135554155574"
START_DATE = date(2026, 2, 2)

# Secrets 인증 정보 (공백 제거)
ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '').strip()
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
REFRESH_TOKEN = os.environ.get('BLOGGER_REFRESH_TOKEN', '').strip()
CLIENT_ID = os.environ.get('BLOGGER_CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('BLOGGER_CLIENT_SECRET', '').strip()

# 시각적 버그 수정을 위한 CSS 스타일 (제목 겹침 및 표 넘침 해결)
STYLE_FIX = """
<style>
    h1, h2, h3 { line-height: 1.6 !important; margin-bottom: 20px !important; word-break: keep-all; }
    .table-container { width: 100%; overflow-x: auto; margin: 25px 0; -webkit-overflow-scrolling: touch; }
    table { width: 100%; min-width: 600px; border-collapse: collapse; line-height: 1.5; }
    th, td { border: 1px solid #eee; padding: 12px; text-align: left; font-size: 15px; }
    th { background-color: #f9f9f9; font-weight: bold; }
    img { display: block; margin: 0 auto; max-width: 100%; height: auto; border-radius: 10px; }
</style>
"""

# ==========================================
# [2. 대규모 키워드 DB (300개)]
# ==========================================
HEALTH_KEYWORDS = [
    # 채소/과일/슈퍼푸드 (100개)
    "브로콜리 설포라판", "블루베리 안토시아닌", "토마토 라이코펜", "아보카도 효능", "비트 식이섬유", "아스파라거스", "케일 해독", "시금치 루테인", "마늘 알리신", "양파 퀘르세틴",
    "사과 아침", "바나나 마그네슘", "키위 소화", "석류 갱년기", "자몽 다이어트", "수박 이뇨", "딸기 항산화", "포도 심장", "레몬 해독", "파인애플 브로멜라인",
    "양배추 비타민U", "당근 시력", "오이 수분", "단호박 부기", "고구마 변비", "청경채", "파프리카", "콜리플라워", "가지", "무 소화",
    "미나리 간", "쑥", "달래", "냉이", "고사리", "연근", "우엉", "마 뮤신", "도라지", "더덕",
    "상추 불면증", "깻잎 철분", "부추 정력", "미역 요오드", "다시마", "톳", "파래", "김", "매생이", "감태",
    "망고", "파파야", "코코넛", "무화과", "대추", "밤", "호두", "아몬드", "캐슈넛", "피스타치오",
    "브라질너트", "피칸", "해바라기씨", "호박씨", "치아씨드", "햄프씨드", "귀리 베타글루칸", "현미", "보리", "메밀",
    "율무", "조", "수수", "퀴노아", "병아리콩", "렌틸콩", "검은콩", "완두콩", "강낭콩", "작두콩",
    "생강", "울금 커큐민", "계피", "고추", "후추", "산초", "바질", "로즈마리", "파슬리", "고수",
    
    # 육류/해산물/단백질 (100개)
    "닭가슴살", "소고기 안심", "돼지고기 뒷다리살", "오리고기", "양고기", "연어 오메가3", "고등어 DHA", "굴 아연", "전복", "장어",
    "멸치 칼슘", "새우", "꽃게 타우린", "문어", "오징어 셀레늄", "달걀 콜린", "두부", "낫또", "청국장", "어묵",
    "명태", "대구", "갈치", "조기", "임연수", "가자미", "꽁치", "참치", "숭어", "방어",
    "바지락", "재첩", "홍합", "꼬막", "가리비", "멍게", "해삼", "개불", "소라", "우렁이",
    "소고기 사태", "돼지 앞다리살", "닭다리살", "닭안심", "오리훈제", "추어탕", "염소고기", "사골", "도가니", "우족",
    
    # 영양제/증상/생활습관 (100개)
    "비타민C", "비타민D", "종합비타민", "유산균", "오메가3", "마그네슘", "칼슘", "아연", "철분", "엽산",
    "밀크씨슬", "보스웰리아", "콘드로이친", "글루코사민", "MSM", "쏘팔메토", "루테인", "코엔자임Q10", "아르기닌", "L-카르니틴",
    "스피루리나", "클로렐라", "프로폴리스", "로열젤리", "화분 효능", "맥주효모", "비오틴", "콜라겐", "히알루론산", "엘라스틴",
    "고혈압 낮추는법", "당뇨 혈당", "고지혈증", "지방간", "위염", "장건강", "면역력", "피로회복", "눈건강", "뼈건강",
    "관절", "혈행개선", "기억력", "집중력", "스트레스 해소", "우울증 음식", "불면증", "피부미용", "다이어트", "디톡스",
    "반신욕", "족욕", "명상", "복식호흡", "스트레칭", "유산소 운동", "근력 운동", "스쿼트", "플랭크", "걷기 운동",
    "수분 섭취", "수면", "금연", "금주", "자세 교정", "거북목", "허리 통증", "무릎 통증", "어깨 결림", "손목 터널 증후군",
    "대사증후군", "골다공증", "빈혈", "부종", "냉증", "갱년기", "치매 예방", "구강 건강", "탈모 예방", "아토피"
]

# ==========================================
# [3. 기술 모듈: 이미지 & 상품 검색]
# ==========================================
def get_image_html(kw):
    """이미지 엑박 문제를 해결하기 위해 더 안정적인 서버를 사용합니다."""
    search_term = urllib.parse.quote(kw)
    img_url = f"https://loremflickr.com/800/500/{search_term},health"
    return f"""
    <div style="margin: 20px 0; text-align: center;">
        <img src="{img_url}" alt="{kw}">
        <p style="color: #888; font-size: 13px; margin-top: 10px;">▲ {kw} 관련 건강 참고 이미지</p>
    </div>
    """

def fetch_product(kw):
    """쿠팡 403 에러 방지를 위한 정밀 인코딩 기술을 적용합니다."""
    method = "GET"
    path = "/v2/providers/affiliate_open_api/apis/opensource/v1/search"
    query_string = f"keyword={urllib.parse.quote(kw)}&limit=1"
    url = f"https://link.coupang.com{path}?{query_string}"
    try:
        timestamp = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        message = timestamp + method + path + query_string
        signature = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, timestamp={timestamp}, signature={signature}"
        res = requests.get(url, headers={"Authorization": auth, "Content-Type": "application/json"}, timeout=15)
        return res.json().get('data', {}).get('productData', []) if res.status_code == 200 else []
    except: return []

# ==========================================
# [4. AI 지능형 콘텐츠 생성]
# ==========================================
def generate_content(post_type, keyword, product=None):
    genai.configure(api_key=GEMINI_API_KEY)
    # 최신 모델 사용으로 404 에러 방지
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    system_prompt = "당신은 건강 의학 전문 에디터입니다. 신뢰감 있는 전문 문체로 HTML 포스팅을 작성하세요."
    table_instruction = "<table>은 반드시 <div class='table-container'>로 감싸서 가로 스크롤이 가능하게 만드세요."
    
    if post_type == "AD":
        prompt = f"{system_prompt} 주제: '{keyword}' 효능과 '{product['productName']}' 추천. 1,500자 이상 HTML 작성. {table_instruction} 링크: <a href='{product['productUrl']}'>▶ 상세정보 및 최저가 확인</a>"
        footer = "<br><p style='color:gray; font-size:12px;'>이 포스팅은 쿠팡 파트너스 활동의 일환으로 수수료를 제공받을 수 있습니다.</p>"
    else:
        prompt = f"{system_prompt} 주제: '{keyword}'에 대한 정밀 가이드. 1,500자 이상 HTML 작성. {table_instruction} 판매 링크 제외."
        footer = ""

    try:
        res = model.generate_content(prompt).text
        # 불필요한 마크다운 기호 정제
        clean_text = re.sub(r'\*\*|##|`|#', '', res)
        # 이미지 + CSS 스타일 + 본문 결합
        return STYLE_FIX + get_image_html(keyword) + clean_text + footer
    except: return None

# ==========================================
# [5. 블로그 발행 (인증 에러 해결)]
# ==========================================
def post_to_blog(title, content):
    try:
        # 웹 애플리케이션 클라이언트 ID 사용
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
# [6. 메인 컨트롤러 (2:1 비율)]
# ==========================================
def main():
    hour_idx = datetime.now().hour // 4 
    if hour_idx >= 3: # 하루 3회 발행 슬롯
        print(f"💤 휴식 슬롯({hour_idx}).")
        return

    # 정보(0, 2) : 광고(1) 비율 전략
    is_ad = (hour_idx == 1)
    post_type = "AD" if is_ad else "INFO"
    kw = random.choice(HEALTH_KEYWORDS)
    
    print(f"📢 {post_type} 발행 시작: {kw}")
    
    if post_type == "AD":
        products = fetch_product(kw.split()[0])
        if products:
            html = generate_content("AD", kw, products[0])
            if html:
                url = post_to_blog(f"[추천] {kw} 건강 관리를 위한 효율적인 가이드", html)
                if url: print(f"✅ 발행 성공: {url}")
        else:
            print("📦 상품 검색 실패. 정보글로 전환합니다.")
            post_type = "INFO"

    if post_type == "INFO":
        html = generate_content("INFO", kw)
        if html:
            url = post_to_blog(f"전문 가이드: {kw}의 놀라운 효능과 활용법", html)
            if url: print(f"✅ 발행 성공: {url}")

if __name__ == "__main__":
    main()
