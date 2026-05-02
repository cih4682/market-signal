# Market Signal

리뷰 · 댓글 · 트렌드 · 뉴스를 한 곳에서 수집·요약해 엑셀로 내려받는 멀티 소스 데이터 도구.

## 기능

- **Naver** — 스마트스토어 / 브랜드스토어 상품 리뷰
- **Coupang** — 상품 후기 (베스트순 / 최신순 / 별점 필터)
- **YouTube** — 영상 댓글 (댓글 + 답글)
- **Trends** — 검색어로 알고리즘 노출 영상 발굴 (break-out 점수)
- **News** — Google News RSS 기반 뉴스 + TOP 키워드 + 본문 요약 모달

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## API 키

- **YouTube / Trends 탭**: 사용자가 직접 발급한 [YouTube Data API v3](https://console.cloud.google.com) 키 입력
- 다른 탭은 키 불필요

## 스택

- Streamlit · Pretendard · Lucide-style icons
- curl_cffi (Coupang/Naver TLS 핑거프린트 우회)
- BeautifulSoup + lxml (HTML 파싱)
- Google News RSS + googlenewsdecoder (원문 URL 디코드)
- pandas + openpyxl (엑셀)

## 라이선스

개인 학습·분석 목적. 상업적 이용 금지.
