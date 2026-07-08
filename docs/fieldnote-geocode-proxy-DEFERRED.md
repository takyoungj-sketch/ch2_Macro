# [보류] FieldNote 지오코딩 프록시 (Macro)

> **상태:** ⏸ FieldNote 주소표 지도 작업과 함께 보류  
> **재개:** [ch2_FieldNote/docs/fieldnote-address-map-markers-DEFERRED.md](../ch2_FieldNote/docs/fieldnote-address-map-markers-DEFERRED.md)

## 요약

- **브랜치:** `feature/fieldnote-geocode-proxy`
- **파일:** `backend/app/routers/geocode.py` — `POST /api/geocode/kakao`
- **역할:** FieldNote 주소→좌표용 카카오 Local API **프록시만** (Macro 통계와 무관)
- **`main` 미머지** — 사업자 등록·`KAKAO_REST_API_KEY` 확보 후 FieldNote와 함께 검증·배포

## 환경 변수

```env
KAKAO_REST_API_KEY=...
```

## 장기

`ch2data.com/api/geocode/*` 플랫폼 API로 이전 후 Macro에서 제거 예정.
