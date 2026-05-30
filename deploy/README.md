# CH2 Macro — Dev/Test VPS (AWS Lightsail) 배포 가이드

로컬 PC에서 운영 중인 CH2 Macro를 **AWS Lightsail (서울) 1대**에 올려  
집·사무실·노트북에서 동일하게 접속·테스트하기 위한 문서 모음입니다.

> **범위:** dev/test 서버. Managed DB·ECS·EKS·RDS·Lambda 등은 사용하지 않습니다.  
> **배치:** Selenium 수집·월간 V2 집계는 **로컬 PC** 유지 → 검증 후 `pg_dump` Promote.

---

## 문서 목록

| 순서 | 문서 | 내용 |
|------|------|------|
| 0 | [00-project-analysis.md](./00-project-analysis.md) | 프로젝트 구조·환경변수·배포 파일 목록 |
| 1 | [01-aws-account-and-lightsail.md](./01-aws-account-and-lightsail.md) | AWS 계정·Lightsail 인스턴스 생성 |
| 2 | [02-server-build-checklist.md](./02-server-build-checklist.md) | Ubuntu·PostgreSQL·Nginx·systemd 구축 |
| 3 | [03-data-migration.md](./03-data-migration.md) | pg_dump / pg_restore·검증 |
| 4 | [04-deploy-checklist.md](./04-deploy-checklist.md) | 앱 배포·HTTPS·보안·git pull 재배포 |
| 5 | [05-operations-checklist.md](./05-operations-checklist.md) | 일상 운영·월간 Promote |
| 6 | [06-recovery.md](./06-recovery.md) | 장애·롤백 절차 |
| 7 | [07-verification-checklist.md](./07-verification-checklist.md) | 기능·HTTPS·CORS·DB 검증 |

---

## 템플릿·스크립트

```
deploy/
├── templates/
│   ├── backend.env.production.example   # backend/.env 참고
│   ├── frontend.env.production.example  # frontend/.env (빌드 시)
│   ├── nginx-ch2-macro.conf             # Nginx 사이트 설정
│   ├── ch2-macro-backend.service        # systemd 유닛
│   └── postgresql-4gb.conf.snippet      # 4GB RAM 튜닝 참고
└── scripts/
    ├── redeploy.sh                      # git pull → build → restart
    └── health-check.sh                  # /health 스모크 테스트
```

---

## 권장 Lightsail 플랜 (비용 최소 + 현 DB 기준)

| 항목 | 권장 |
|------|------|
| 리전 | **ap-northeast-2 (서울)** |
| OS | **Ubuntu 22.04 LTS** |
| 플랜 | **Medium — 4 GB RAM / 2 vCPU / 80 GB SSD** (~$24/월) |
| 런타임 | **systemd + 네이티브 PostgreSQL** (Docker 미사용 — 4GB에서 RAM 절약) |

**주의:** DB ~7.2 GB + 인덱스·WAL·덤프 여유를 고려하면 80 GB SSD는 **빡빡하지만 dev/test에는 가능**합니다.  
유료 필터가 OOM 나거나 디스크 부족 시 **8 GB / 160 GB 플랜**으로만 업그레이드하세요.

---

## 한눈에 보는 이전 흐름

```
[로컬 PC]                          [Lightsail VPS]
 pipeline (수집·집계)    pg_dump ──► PostgreSQL (restore)
 git push ──────────────► git clone / pull
                        FastAPI (systemd :8000)
                        Nginx (:443) → static + /api proxy
                        Let's Encrypt HTTPS
```

---

## 빠른 시작 (경험자용)

1. [01-aws-account-and-lightsail.md](./01-aws-account-and-lightsail.md) — 인스턴스 생성
2. [02-server-build-checklist.md](./02-server-build-checklist.md) — OS·DB·앱 뼈대
3. [03-data-migration.md](./03-data-migration.md) — 덤프 업로드·복원
4. [04-deploy-checklist.md](./04-deploy-checklist.md) — env·빌드·HTTPS
5. [07-verification-checklist.md](./07-verification-checklist.md) — 전체 검증

관련 레포 문서: [`docs/MONTHLY_UPDATE_SOP.md`](../docs/MONTHLY_UPDATE_SOP.md) §9 (Promote), [`docs/DECISIONS.md`](../docs/DECISIONS.md) D-007 (API_TOKEN).
