# 1. AWS 계정 생성 · Lightsail 인스턴스 생성

---

## 1.1 AWS 계정 생성 후 순서

| # | 작업 | 비고 |
|---|------|------|
| 1 | [AWS](https://aws.amazon.com/) 회원가입 | 이메일·카드 등록 |
| 2 | **루트 계정 MFA** 활성화 | IAM → 보안 자격 증명 |
| 3 | **IAM 사용자** 생성 (일상용) | `AdministratorAccess` 또는 Lightsail 전용 정책 |
| 4 | IAM 액세스 키 **생성하지 않음** (콘솔만 사용해도 됨) | CLI 필요 시만 생성 |
| 5 | **결제 알림** 설정 | Budgets → 월 $30~50 알림 (dev) |
| 6 | **리전** 확인 | 콘솔 우상단 → **Asia Pacific (Seoul) ap-northeast-2** |
| 7 | Lightsail 콘솔 이동 | [Lightsail](https://lightsail.aws.amazon.com/) |

> 루트 계정으로 Lightsail만 쓰지 말고, IAM 사용자 + MFA를 권장합니다.

---

## 1.2 Lightsail 인스턴스 생성 절차

### Step 1 — 인스턴스 만들기

1. Lightsail → **Create instance**
2. **Instance location:** Seoul (ap-northeast-2)
3. **Platform:** Linux/Unix
4. **Blueprint:** OS Only → **Ubuntu 22.04 LTS**
5. **Instance plan:**

   | 플랜 | 스펙 | 월 (대략) | 선택 |
   |------|------|-----------|------|
   | **Medium** | 4 GB / 2 vCPU / 80 GB SSD | ~$24 | ✅ dev/test 기본 |
   | Large | 8 GB / 2 vCPU / 160 GB SSD | ~$44 | OOM·디스크 부족 시 |

6. **Identify your instance:** `ch2-macro-dev`
7. (선택) **Launch script** — 비워 두고 SSH 접속 후 [02-server-build-checklist.md](./02-server-build-checklist.md) 수행
8. **Create instance**

### Step 2 — 고정 IP (Static IP)

1. Lightsail → **Networking** → **Create static IP**
2. Region: Seoul, Attach to: `ch2-macro-dev`
3. 기록: `DEV_PUBLIC_IP=xxx.xxx.xxx.xxx`

### Step 3 — 방화벽 (Lightsail Networking)

인스턴스 → **Networking** → **IPv4 Firewall**:

| 포트 | 프로토콜 | 허용 | 용도 |
|------|----------|------|------|
| 22 | TCP | ✅ | SSH (나중에 IP 제한 권장) |
| 80 | TCP | ✅ | Let's Encrypt HTTP-01 |
| 443 | TCP | ✅ | HTTPS |
| 8000 | TCP | ❌ | Uvicorn — **외부 차단** (Nginx만 공개) |
| 5432 | TCP | ❌ | PostgreSQL — **외부 차단** |

### Step 4 — SSH 키

1. Lightsail → Account → **SSH keys** → 기본 키 다운로드 (`.pem`)
2. Windows: `%USERPROFILE\.ssh\` 에 저장, 권한 제한
3. 접속:

```powershell
ssh -i $env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem ubuntu@DEV_PUBLIC_IP
```

Lightsail 콘솔의 **Connect using SSH** 버튼도 사용 가능.

### Step 5 — (선택) DNS

도메인이 있으면:

- `dev-macro.ch2data.com` → Static IP **A 레코드**
- 없으면 초기에는 `https://DEV_PUBLIC_IP` 는 Let's Encrypt **불가** → **도메인 1개 필요** (무료 서브도메인 가능)

Let's Encrypt는 **도메인 + 80/443** 이 필요합니다. IP만으로는 인증서 발급이 어렵습니다.

---

## 1.3 생성 직후 확인

```bash
# 서버에서
uname -a
free -h
df -h /
lsb_release -a
```

| 확인 | 기대 |
|------|------|
| RAM | ~3.8 GiB usable |
| Disk | ~80 GB, 사용 ~5% |
| OS | Ubuntu 22.04 |

---

## 1.4 다음 단계

→ [02-server-build-checklist.md](./02-server-build-checklist.md) 서버 구축 시작

---

## 1.5 비용 절감 팁

- 사용하지 않을 때 **인스턴스 중지** (Static IP는 소액 과금 — dev 장기 중지 시 IP 해제 검토)
- **스냅샷**은 주 1회만 (Lightsail snapshot 요금)
- dev/test 단계에서 **RDS·ALB·CloudFront 사용 안 함**
