# Fingerprint Twin (1차 러너)

> **상태:** 랩 실험. 제품 Twin 선정은 바꾸지 않음.  
> **창:** 새 문 없음. 관리자 `?tool=twin` → **V1 풀 실험**에서 `fingerprint-twin-pilot` 선택.  
> **러너:** `pipeline/bench_fingerprint_twin.py`

## 질문

같은 V2 풀 Twin 우주에서, **프로필 1위**를 붙일 때와 **공통식 지문 1위**를 붙일 때, Local 대비 **확인 CV**가 나아지는가. 같은 우주 **무작위**가 대조.

## 고정

- 지문 곡물: **시군구**(코드 5자리). 읍면동 최적식 금지.
- 공통식: \(\ln P = \beta_0 + \beta_1\ln(\text{연면적}) + \beta_2\ln(\text{대지}) + \text{도로더미}\)
- 거리: 가상 물건 ŷ(로그)에서 **절편(평균)을 뺀** 상관. \(d=1-r\)
- 붙임: Local 식 고정 + Twin 1위 표본만 (D-073 diagnose)
- 승패: 확인 CV. 탐색 CV는 confirm이 없을 때만 대체하고 `note`에 표시.

## 실행

```text
cd pipeline
python bench_fingerprint_twin.py
python bench_fingerprint_twin.py --fixture fixtures/twin_bench_commercial_chungbuk12.json --id fingerprint-twin-chungbuk12
python bench_fingerprint_twin.py --fixture fixtures/twin_bench_commercial_gyeonggi12.json --id fingerprint-twin-gyeonggi12
```

관리자 `?tool=twin&pane=mape` 실험 목록:

- `fingerprint-twin-pilot` — 충북 파일럿 4
- `fingerprint-twin-chungbuk12` — 충북 상업 12 (8 dev + 4 holdout, n≥50)
- `fingerprint-twin-gyeonggi12` — 경기 상업 12 (일반구 제외 샘플)

## 1차 실측 (확인 CV, Local 식 고정 + Twin 1위)

숫자는 중앙값 lift(Local 대비). 음수면 Twin이 Local보다 나쁨. 이긴 횟수는 4팔 중 확인 CV 최저.

| 런 | n | 같은 1위 | FP 승 | 프로필 승 | Local 승 | 무작위 승 | FP 중앙 lift | 프로필 중앙 lift |
|---|---|---|---|---|---|---|---|---|
| 파일럿 4 | 4 | 1 | 1 | 1 | 2 | 0 | — | — |
| 충북 12 | 12 | 6 | 2 | 1 | 5 | 4 | −0.20 | −0.28 |
| 경기 12 | 12 | 8 | 0 | 1 | 9 | 2 | −0.41 | −0.58 |

충북에서 지문과 프로필이 **다른 동**을 고른 6곳 중 지문이 이긴 곳은 흥덕(모충동)·증평(오창읍) 두 곳. 경기는 12곳 중 8곳이 같은 1위라 재순위 효과가 거의 없고, 확인 CV 승자는 거의 Local이다.

경기 **전체** 중앙 CV-MAPE: Local 24.3 · 프로필/지문 35.5 · 무작위 27.8. 화면의 18.4 / 63.8 / 53.0 / 34.9는 holdout 4곳이다. 서사 주표로 쓰지 않는다.

제품 Twin 선정은 바꾸지 않는다.

## 다음 (중지 지점 · 2026-09-12)

선정 알고리즘을 바꾸지 않는다. **같은 프로필 1위 Twin을 어떻게 붙이는지**만 본다. 새 랩 문·새 D-xxx 없음.

한 런 네 팔:

1. Local (r0)
2. 단순 pooling — 현재 diagnose, 이미 실패
3. Twin 절편 분리 — 거래는 쓰되 Local/Twin 더미로 가격수준만 분리
4. Twin 무게 제한 — 가중 0.25 또는 Twin n ≤ Local n

절편 분리를 먼저 해석한다. 지문은 절편을 빼고 골랐는데 붙임은 절편을 공유한다. 계층 베이즈·Fingerprint→pooling weight는 붙임이 Local을 이긴 뒤에만.

랩 표시: 다음에 mape를 손보면 Median Lift 대신 Δ CV-MAPE(%p).
