# FieldNote 앱 지원 서버 (FN-008)

기준: `CH2_SHARED_OPS/tasks/FN-008/PLAN.md` v2 확정, 2026-11-20 T 승인. 구현·검수 중이며 운영 배포를 뜻하지 않는다.

## 앱 로그인 수명

- `FIELDNOTE_APP_TOKEN_EXPIRE_DAYS`: 기본 **7일**, 양의 정수. 일반 사용자 `app:ch2fieldnote://...` OAuth 로그인에만 적용한다. 변경은 이후 새로 발급하는 토큰에 적용되며 이미 발급한 JWT의 만료는 바뀌지 않는다.
- `_finish_web_or_app_login`이 콜백 시 `_get_or_create_oauth_user`가 DB `users` 행에서 반환한 role로 판단한다. 요청 state·쿼리·프로필·기존 토큰 claim으로 관리자 여부나 수명을 정하지 않는다.
- DB role이 `admin`이면 앱도 기존 `access_token_expire_minutes` 수명이다. 웹 JWT·쿠키는 기존 설정과 발급 방식을 유지한다. 코드 기본은 60분이며 운영 설정값이 우선이다.
- 운영 실제 수명은 이번에 조회하지 않았다. Cursor가 배포 전 값만 읽기 전용으로 확인한다. 이미 7일 이상이면 분리 의미가 달라지므로 T에게 보고하고 판단을 받는다. 비밀값이나 `.env` 내용을 보고서에 복사하지 않는다.
- 리프레시 토큰·폐기 목록·aud 제한은 없다. 앱 토큰도 공용 JWT이므로 Bearer로 결제 해지·게시판 수정 등 기존 API를 호출할 수 있다. `ch2fieldnote://` 커스텀 스킴 가로채기 위험은 남는다. 짧은 토큰+안전한 갱신, App Links·PKCE·토큰 용도 제한은 별도 개선 과제다.

## 공개 앱 설정

`GET /api/platform/fieldnote/app-config`는 로그인·DB 없이 다음 네 필드를 반환한다.

```json
{"min_version_code":0,"latest_version_code":0,"message":"","blocked_features":[]}
```

- `FIELDNOTE_APP_MIN_VERSION_CODE`: 기본 0(막지 않음), 0 이상 정수. 구버전을 막으려면 최소 허용 Android versionCode로 올린다. 예: 4이면 3 이하 앱이 업데이트 대상으로 판단한다.
- `FIELDNOTE_APP_LATEST_VERSION_CODE`: 기본 0, 0 이상 정수. 최신 Android versionCode 안내용이다.
- `FIELDNOTE_APP_UPDATE_MESSAGE`: 기본 빈 문자열. 업데이트 안내문. 공개 응답이므로 비밀값을 넣지 않는다.
- `FIELDNOTE_APP_BLOCKED_FEATURES`: 기본 빈 문자열, 쉼표 목록. 예: `backup_restore,ai`. 앞뒤 공백·빈 항목을 제거하고 중복은 첫 순서만 유지한다. 응답 예: `["backup_restore","ai"]`. 이름의 해석은 FN-005 앱 계약을 따른다. 앱이 모르는 이름은 무시한다.

설정은 서버 시작 때 읽는다. 변경 반영은 승인된 배포·재시작 절차를 따른다. 해제하려면 min을 0으로, blocked_features를 빈 값으로 돌린다. 공개 API에 쓰기 기능은 없다.

최소 버전·blocked_features는 **앱의 동작 안내**다. 이 API가 서버 기능을 직접 차단하거나 기존 앱에 강제로 적용하지 않는다. FN-005에서 시작·포그라운드 복귀 때 읽고, min 미만이면 AI·지도 허브를 막되 기록·백업·내보내기 등 로컬 기능은 유지한다. blocked_features는 앱이 지원하는 이름에만 적용한다. 데이터 손상 기능을 긴급 잠글 때도 FN-005가 해당 이름을 처리하는지 먼저 확인한다.

## 검수·배포 경계

FN-008은 DB 구조·기존 API 접근 범위를 바꾸지 않는다. 운영 실제 토큰 만료값 확인, FN-005와 앱 연계·업데이트/차단 시험, 독립 검수와 T 배포 승인이 남는다. 이 문서는 main 병합·운영 배포 승인이 아니다.
