"""건축HUB 건축물대장정보 API(data.go.kr 15134735) 얇은 클라이언트 — C-2 불확실 쌍 확인용(읽기 전용 조회).

- 키: 환경변수 DATA_GO_KR_BLD_KEY(없으면 Windows 사용자 환경변수 레지스트리에서 읽음). **출력·기록하지 않는다.**
  오류 메시지·로그에는 요청 주소를 넣지 않는다(키가 쿼리에 들어 있으므로).
- 응답 원문은 logs/collective_p2/bld_api_cache/ 에만 저장(지번 포함, 커밋하지 않음). 같은 요청은 캐시로 다시 쓰고 부르지 않는다.
- 호출 사이 간격(기본 1초), 이번 실행 한도(--max-calls), 한도 초과 응답(LIMITED_NUMBER…·코드 22)이면 즉시 멈춘다.
- PK 는 이번 조회 결과 안에서만 쓴다(건축HUB 전환으로 예전 PK 와 다름).
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://apis.data.go.kr/1613000/BldRgstHubService"
OPS = {"recap": "getBrRecapTitleInfo", "title": "getBrTitleInfo", "atch": "getBrAtchJibunInfo"}
ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "logs" / "collective_p2" / "bld_api_cache"


class ApiStop(RuntimeError):
    """한도 초과·인증 오류·연속 실패 — 더 부르지 않고 멈춘다."""


class ApiSkip(RuntimeError):
    """이 요청만 실패(일시 오류를 다시 시도한 뒤에도) — 이 지번은 건너뛰고 계속."""


def _key() -> str:
    k = os.environ.get("DATA_GO_KR_BLD_KEY")
    if not k:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                k = winreg.QueryValueEx(h, "DATA_GO_KR_BLD_KEY")[0]
        except OSError:
            k = None
    if not k:
        raise ApiStop("DATA_GO_KR_BLD_KEY 없음")
    return str(k).strip()


class Client:
    def __init__(self, *, gap: float = 1.0, max_calls: int = 900):
        self.gap, self.max_calls = gap, max_calls
        self.calls = 0
        self.cached = 0
        self.fails = 0            # 연속 실패
        self.skipped = 0
        self._last = 0.0
        CACHE.mkdir(parents=True, exist_ok=True)

    def _url(self, op: str, params: dict) -> str:
        k = _key()
        # 인코딩된 키(% 포함)는 그대로, 아니면 인코딩
        kq = k if "%" in k else urllib.parse.quote(k, safe="")
        return f"{BASE}/{OPS[op]}?serviceKey={kq}&" + urllib.parse.urlencode(params)

    def get(self, op: str, sigungu: str, bjdong: str, bun: str, ji: str | None = None, *, page: int = 1,
            rows: int = 100) -> dict:
        params = {"sigunguCd": sigungu, "bjdongCd": bjdong, "platGbCd": "0", "bun": str(bun).zfill(4),
                  "numOfRows": rows, "pageNo": page, "_type": "json"}
        if ji is not None:
            params["ji"] = str(ji).zfill(4)
        f = CACHE / f"{op}_{sigungu}_{bjdong}_{params['bun']}_{params.get('ji', 'all')}_p{page}.json"
        if f.is_file():
            self.cached += 1
            return json.loads(f.read_text(encoding="utf-8"))
        if self.calls >= self.max_calls:
            raise ApiStop(f"이번 실행 호출 한도 {self.max_calls} 도달 — 나머지는 다음 실행(캐시로 이어서)")
        wait = self.gap - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        import urllib.error

        last_err = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(self._url(op, params), timeout=20) as r:
                    body = r.read().decode("utf-8", "replace")
                self.calls += 1                      # 실제로 나간 요청 수(재시도 포함)
                if not body.strip():                 # 빈 응답(호출이 잦을 때 나옴) → 일시 오류로 보고 다시
                    last_err = "빈 응답"
                    time.sleep(5 * (2 ** attempt))
                    continue
                break
            except urllib.error.HTTPError as ex:   # 주소(키)를 메시지에 넣지 않는다 — 코드만
                last_err = f"HTTP {ex.code}"
                if ex.code in (401, 403):
                    raise ApiStop(f"인증 오류 {last_err} — 멈춤") from None
                time.sleep(5 * (2 ** attempt))      # 429·5xx 등: 5·10·20·40초
            except Exception as ex:  # noqa: BLE001
                last_err = type(ex).__name__
                time.sleep(5 * (2 ** attempt))
        else:
            self.fails += 1
            self.skipped += 1
            if self.fails >= 5:
                raise ApiStop(f"연속 {self.fails}회 실패({last_err}) — 멈춤")
            raise ApiSkip(f"호출 실패({last_err}) — {op} {sigungu}{bjdong} {params['bun']}")
        self.fails = 0
        self._last = time.time()
        if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body or "SERVICE_KEY_IS_NOT_REGISTERED" in body \
                or "<returnReasonCode>22<" in body or "<returnReasonCode>30<" in body:
            raise ApiStop("한도 초과 또는 키 미등록 응답 — 멈춤")
        try:
            data = json.loads(body)
        except ValueError:
            raise ApiStop(f"JSON 이 아닌 응답(앞 80자: {body[:80]!r})") from None
        head = (data.get("response") or {}).get("header") or {}
        if str(head.get("resultCode")) not in ("00", "0"):
            raise ApiStop(f"오류 응답 {head.get('resultCode')} {head.get('resultMsg')}")
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def items(self, op: str, sigungu: str, bjdong: str, bun: str, ji: str | None = None) -> list[dict]:
        """페이지를 모두 돌아 item 목록."""
        out, page = [], 1
        while True:
            d = self.get(op, sigungu, bjdong, bun, ji, page=page)
            body = (d.get("response") or {}).get("body") or {}
            it = (body.get("items") or {})
            it = it.get("item", []) if isinstance(it, dict) else []
            if isinstance(it, dict):
                it = [it]
            out += it
            total = int(body.get("totalCount") or 0)
            if page * int(body.get("numOfRows") or 100) >= total or not it:
                return out
            page += 1
