"""Chapter 29: nearest neighbors, scale, and the supplied lesson text."""
from pathlib import Path
from statistics import mean, pstdev
from html import escape
import json, re, math
ROOT = Path(__file__).resolve().parent


def build():
    x = [1, 2, 4, 6, 8]
    y = [2, 3, 5, 4, 8]
    query = 3.2

    def neighbors(v, k):
        return sorted(range(5), key=lambda i: (abs(x[i] - v), i))[:k]

    def predict(v, k):
        return mean(y[i] for i in neighbors(v, k))

    chosen3 = neighbors(query, 3)
    weights = [1 / abs(x[i] - query) for i in chosen3]
    weighted = sum(weights[j] * y[chosen3[j]] for j in range(3)) / sum(weights)
    assert abs(weighted - 255 / 67) < 1e-12
    points = [[50, 1], [60, 10], [100, 5], [110, 6]]
    q = [62, 2]
    scales = [pstdev(p[j] for p in points) for j in range(2)]
    raw = [math.dist(p, q) for p in points]
    scaled = [math.sqrt(sum(((p[j] - q[j]) / scales[j]) ** 2 for j in range(2))) for p in points]
    assert raw.index(min(raw)) == 1 and scaled.index(min(scaled)) == 0
    grid = [dict(x=i / 20, k1=predict(i / 20, 1), k3=predict(i / 20, 3), k5=predict(i / 20, 5)) for i in range(201)]
    assert all(abs(row['k5'] - mean(y)) < 1e-12 for row in grid)
    payload = dict(
        description='최근접 이웃의 계산을 설명하기 위한 별도 가상 자료.',
        x=x, y=y, query=query, neighbors=chosen3,
        k1=predict(query, 1), k3=predict(query, 3), k5=predict(query, 5),
        weighted_k3=weighted, grid=grid,
        scaling=dict(points=points, query=q, scales=scales, raw=raw, scaled=scaled),
        vote=dict(labels=[1, 0, 1], probability=2 / 3),
        distance_zero='선택한 K개 안에 거리 0이 있으면 그 관측만 같은 비중으로 평균한다.',
    )
    (ROOT / 'knn-example.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def tx(px, py, s):
        return f'<text x="{px}" y="{py}">{escape(str(s))}</text>'

    def ln(x1, y1, x2, y2, color='#94a3b8'):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}"/>'

    def fig(fid, title, body, cap, box='0 0 640 410'):
        return (
            f'<figure class="learn-chart learn-chart--wide knn-chart"><svg viewBox="{box}" role="img" aria-labelledby="{fid}-title {fid}-desc">'
            f'<title id="{fid}-title">{title}</title><desc id="{fid}-desc">{cap}</desc>{body}</svg>'
            f'<figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
        )

    def steps(key):
        pts = []
        for i, row in enumerate(grid):
            if i:
                pts.append((70 + row['x'] * 50, 320 - grid[i - 1][key] * 28))
            pts.append((70 + row['x'] * 50, 320 - row[key] * 28))
        return ' '.join(f'{a},{b}' for a, b in pts)

    body = tx(24, 28, 'x=3.2에서 가까운 이웃. 거리는 X만 사용') + ln(70, 310, 570, 310) + ln(70, 55, 70, 310)
    picked = set(chosen3)
    for i, (a, v) in enumerate(zip(x, y)):
        on = i in picked
        body += f'<circle data-index="{i}" cx="{70 + a * 55}" cy="{310 - v * 28}" r="{7 if on else 5}" fill="{"#2563eb" if on else "#94a3b8"}"/>'
        body += tx(78 + a * 55, 292 - v * 28, f'({a}, {v})')
    body += ln(70 + query * 55, 65, 70 + query * 55, 310, '#d97706')
    for v in [0, 2, 4, 6, 8]:
        body += tx(62 + v * 55, 332, v) + tx(28, 314 - v * 28, v)
    body += '<text id="knn-fig1-note" x="24" y="368">가로 입력 X / 세로 목표 Y · 주황선 x=3.2 · 파랑은 선택한 이웃</text>'
    g1 = fig('neighbors', '새로운 입력값과 가까운 이웃 선택', body, '그림 1. 거리는 입력 X만으로 계산합니다. 목표 Y는 이웃을 고른 뒤에 집계합니다. 기본 표시는 K=3이며, 가까운 순서는 X=4, 2, 1입니다.')

    def panel(dist, maxv, title, title_y, axis_y, pid, active):
        stroke = '#d97706' if active else '#cbd5e1'
        out = f'<rect id="{pid}" x="8" y="{title_y - 24}" width="220" height="{axis_y - title_y + 58}" rx="8" fill="none" stroke="{stroke}" stroke-width="2"/>'
        out += tx(16, title_y, title) + ln(24, axis_y, 214, axis_y)
        order = sorted(range(4), key=lambda i: (dist[i], i))
        rank = {i: n + 1 for n, i in enumerate(order)}
        for i, v in enumerate(dist):
            h = v / maxv * 120
            xx = 28 + i * 46
            out += f'<rect x="{xx}" y="{axis_y - h}" width="34" height="{h}" fill="{"#d97706" if rank[i] == 1 else "#2563eb"}"/>'
            out += tx(xx - 6, axis_y - h - 6, f'{v:.2f}' if v >= 10 else f'{v:.3f}')
            out += tx(xx + 10, axis_y + 18, 'ABCD'[i])
        return out

    body = panel(raw, 60, '원래 거리 · 눈금 최대 60', 36, 200, 'knn-panel-raw', True)
    body += panel(scaled, 3, '표준화 거리 · 눈금 최대 3', 300, 470, 'knn-panel-std', False)
    g2 = fig('scale', '표준화 전후의 이웃 거리와 순위', body, '그림 2. A=(50, 1), B=(60, 10), C=(100, 5), D=(110, 6), 질의=(62, 2)입니다. 위는 원래 유클리드 거리, 아래는 학습 4건의 분모 4 표준편차로 나눈 거리입니다. 주황 테두리는 지금 읽는 척도이고, 주황 막대는 그 척도의 최단입니다. 원래 거리는 B, 표준화 거리는 A가 가장 가깝습니다.', '0 0 420 620')

    body = tx(24, 28, '같은 5점의 균등 가중 예측곡선') + ln(70, 320, 570, 320) + ln(70, 55, 70, 320)
    for key, color, width, opacity in [('k1', '#2563eb', '1.4', '0.38'), ('k5', '#0f766e', '1.4', '0.38'), ('k3', '#d97706', '3.2', '1')]:
        body += f'<polyline data-k="{key}" points="{steps(key)}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>'
    for a, v in zip(x, y):
        body += f'<circle cx="{70 + a * 50}" cy="{320 - v * 28}" r="4" fill="#111827"/>'
    body += ln(70 + query * 50, 70, 70 + query * 50, 320, '#d97706')
    for v in [0, 2, 4, 6, 8, 10]:
        body += tx(62 + v * 50, 344, v)
    for v in [0, 4, 8]:
        body += tx(36, 324 - v * 28, v)
    body += tx(24, 378, '파랑 K=1 · 주황 K=3 · 청록 K=5(어디서나 4.4)')
    g3 = fig('complexity', '이웃 수 K에 따른 계단형 예측곡선', body, '그림 3. 그림 1과 같은 학습자료의 균등 가중 곡선입니다. 0.05 간격으로 평가한 계단 표시라 경계가 정확한 중간점과 조금 다를 수 있습니다. K=5는 모든 x에서 4.4입니다. 같은 거리면 앞 번호를 우선합니다.')

    body = tx(16, 24, '회귀와 분류는 집계가 다릅니다')
    body += '<rect id="knn-box-reg" x="12" y="40" width="210" height="100" rx="8" fill="#eaf2ff" stroke="#d97706" stroke-width="3"/>'
    body += tx(24, 68, '회귀 · 같은 X, Y') + tx(24, 94, 'K=3 균등 평균') + tx(24, 120, '(5+3+2)/3 ≈ 3.33')
    body += '<rect id="knn-box-cls" x="12" y="160" width="210" height="100" rx="8" fill="#eaf2ff" stroke="#94a3b8" stroke-width="2"/>'
    body += tx(24, 188, '분류 · 따로 둔 라벨') + tx(24, 214, '1 · 0 · 1') + tx(24, 240, '양성 비율 2/3')
    g4 = fig('tasks', 'KNN 회귀와 KNN 분류의 집계', body, '그림 4. 회귀는 그림 1의 Y를 평균합니다. 분류는 그 Y를 라벨로 바꾼 값이 아니라 따로 둔 1·0·1입니다. 양성 비율 2/3를 보정된 확률로 읽지 않습니다.', '0 0 430 280')

    def scale_table(mode, dist, caption):
        order = sorted(range(4), key=lambda i: (dist[i], i))
        rank = {i: n + 1 for n, i in enumerate(order)}
        rows = []
        for i, name in enumerate('ABCD'):
            diff = [q[j] - points[i][j] for j in range(2)]
            sq = [d * d for d in diff] if mode == 'raw' else [(diff[j] / scales[j]) ** 2 for j in range(2)]
            rows.append(
                '<tr><td>{name}</td><td>{a:g}</td><td>{b:g}</td><td>{c:.4f}</td><td>{d:.4f}</td><td>{dist:.4f}</td><td>{rank}</td></tr>'.format(
                    name=name, a=diff[0], b=diff[1], c=sq[0], d=sq[1], dist=dist[i], rank=rank[i]
                )
            )
        active = ' knn-table-active' if mode == 'raw' else ''
        head = '차이²' if mode == 'raw' else '(차이/표준편차)²'
        return (
            f'<table class="knn-metrics{active}" id="knn-table-{mode}"><caption>{caption}</caption><thead><tr>'
            f'<th>관측</th><th>면적 차이</th><th>층 차이</th><th>면적 {head}</th><th>층 {head}</th><th>거리</th><th>순위</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
        )

    k_both = (
        '<div class="knn-controls" hidden><p>이웃 수 K를 바꾸면 그림 1의 이웃과 그림 3의 곡선이 함께 바뀝니다. 거리 가중은 x=3.2의 예측 숫자만 바꿉니다.</p>'
        '<div class="knn-shortcuts" role="group" aria-label="이웃 수"><button type="button" data-k="1">K=1</button>'
        '<button type="button" data-k="3" aria-pressed="true">K=3</button><button type="button" data-k="5">K=5</button></div>'
        '<div class="knn-shortcuts" role="group" aria-label="가중 방식"><button type="button" data-weight="uniform" aria-pressed="true">균등 가중</button>'
        '<button type="button" data-weight="distance">거리 가중</button></div>'
        '<p id="knn-neighbor-status" role="status">K=3, 균등 가중. 1위 X=4 (거리 0.8, Y=5) → 2위 X=2 (거리 1.2, Y=3) → 3위 X=1 (거리 2.2, Y=2). 예측 3.3333.</p></div>'
    )
    k_curve = (
        '<div class="knn-controls" hidden><p>그림 1과 같은 K입니다. 여기 곡선은 균등 가중만 그립니다.</p>'
        '<div class="knn-shortcuts" role="group" aria-label="예측곡선의 이웃 수"><button type="button" data-k="1">K=1</button>'
        '<button type="button" data-k="3" aria-pressed="true">K=3</button><button type="button" data-k="5">K=5</button></div>'
        '<p id="knn-curve-status" role="status">그림 3은 균등 가중입니다. K=3일 때 x=3.2의 예측은 3.3333입니다. K=5의 균등 가중 예측은 모든 x에서 4.4입니다.</p></div>'
    )
    scale_controls = (
        '<div class="knn-controls" hidden><p>원래 단위와 표준화를 바꿔 순위와 변수 기여를 비교합니다. 두 표는 함께 두고, 선택한 척도에 테두리를 칩니다.</p>'
        '<div class="knn-shortcuts" role="group" aria-label="거리 척도"><button type="button" data-scale="raw" aria-pressed="true">원래 단위</button>'
        '<button type="button" data-scale="std">표준화</button></div>'
        '<p id="knn-scale-status" role="status">원래 단위입니다. 최단은 B(8.2462)이고 A는 2위(12.0416)입니다. 표준화하면 최단이 A(0.5649)로 바뀝니다.</p></div>'
    )
    task_controls = (
        '<div class="knn-controls" hidden><p>회귀와 분류는 서로 다른 예제입니다. 회귀 자료의 Y를 양성·음성으로 바꾸지 않았습니다.</p>'
        '<div class="knn-shortcuts" role="group" aria-label="집계 방식"><button type="button" data-task="reg" aria-pressed="true">회귀</button>'
        '<button type="button" data-task="cls">분류</button></div>'
        '<p id="knn-task-status" role="status">회귀 예제입니다. 그림 1과 같은 X·Y에서 K=3 균등 가중 예측은 (5+3+2)/3≈3.3333입니다.</p></div>'
    )
    parts = []

    def sec(sid, label, title, html):
        parts.append(f'<section class="learn-chapter__step" id="{sid}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{html}</section>')

    sec('quick-start', '서두 · 학습목표', '가장 비슷한 거래를 찾는다는 것은 무엇을 의미할까요?',
        '<p>토지의 거래단가를 분석하려고 합니다. 면적이 100㎡인 토지와 105㎡인 토지는 서로 비슷하다고 볼 수 있을까요? 면적만 살펴보면 상당히 비슷합니다. 하지만 한쪽은 일반상업지역의 대지이고 다른 한쪽은 계획관리지역의 임야라면 어떨까요? 두 토지를 같은 성격의 거래로 보기는 어려울 것입니다.</p>'
        '<p>반대로 면적은 조금 다르더라도 위치와 용도지역, 도로 조건 등이 비슷하다면 비교할 만한 사례일 수 있습니다. 이처럼 <strong>어떤 관측값을 서로 비슷하다고 판단할 것인지</strong>는 부동산 시장 분석에서 매우 중요한 문제입니다.</p>'
        '<p>머신러닝에서도 비슷한 자료를 찾는 대표적인 방법이 있습니다. 바로 <strong>K최근접 이웃(K-nearest neighbors, KNN)</strong>입니다. KNN은 새롭게 입력된 관측값과 가장 가까운 K개의 기존 관측값을 찾고, 이들의 결과를 이용해 예측하는 방법입니다. 하지만 가까움을 계산하는 기준이 바뀌면 선택되는 이웃도 달라집니다.</p>'
        '<p>이번 장에서는 KNN의 원리와 함께 변수의 단위, 표준화, 거리 가중치가 유사한 관측값을 선택하는 데 어떤 영향을 미치는지 알아보겠습니다.</p>'
        '<ul class="learn-objectives"><li>KNN이 가까운 관측값을 선택하는 방법을 이해합니다.</li><li>이웃 탐색과 목표값을 이용한 예측을 구별합니다.</li><li>유클리드 거리와 맨해튼 거리의 차이를 알아봅니다.</li><li>변수의 단위와 표준화가 이웃 순위를 바꾸는 이유를 이해합니다.</li><li>이웃 수 K와 모형의 복잡도 사이의 관계를 살펴봅니다.</li><li>KNN 회귀와 KNN 분류를 구별합니다.</li><li>거리 가중치, 범주형 변수, 고차원 자료의 문제를 알아봅니다.</li><li>CH2 Macro의 유사거래 탐색에 적용할 수 있는 개념을 이해합니다.</li></ul>')
    sec('principle', '최근접 이웃의 기본 원리', '새 관측값과 가까운 기존 자료를 찾아봅니다',
        '<p>KNN의 원리는 비교적 단순합니다. 새로운 입력값이 주어지면 기존 학습자료에서 가장 가까운 관측값을 K개 선택합니다. 그리고 그 관측값들의 결과를 모아 새로운 입력값에 대한 결과를 예측합니다.</p>'
        '<p>예를 들어 기존 거래 다섯 건의 입력 X는 1, 2, 4, 6, 8이고 결과 Y는 2, 3, 5, 4, 8입니다. 새로운 입력값이 X=3.2라면 각 학습 관측과의 거리는 X값의 절대 차이입니다.</p>'
        '<table class="knn-metrics"><caption>X=3.2와의 거리. 정렬에 쓰기 전의 원자료입니다.</caption><thead><tr><th>기존 X</th><th>Y</th><th>거리</th></tr></thead><tbody>'
        '<tr><td>1</td><td>2</td><td>2.2</td></tr><tr><td>2</td><td>3</td><td>1.2</td></tr><tr><td>4</td><td>5</td><td>0.8</td></tr><tr><td>6</td><td>4</td><td>2.8</td></tr><tr><td>8</td><td>8</td><td>4.8</td></tr>'
        '</tbody></table>'
        '<p>가장 가까운 순서는 <strong>X=4 → X=2 → X=1 → X=6 → X=8</strong>입니다. K=1이면 가장 가까운 관측 X=4의 결과 Y=5를 사용하므로 예측값은 5입니다. K=3이면 (5+3+2)/3=10/3≈3.3333입니다. K=5이면 다섯 결과의 평균 22/5=4.4입니다.</p>'
        + k_both + g1 +
        '<p>K값을 바꾸면 같은 X=3.2에서도 예측값이 달라집니다. 어떤 이웃을 몇 개 선택하는지에 따라 결과가 달라지기 때문입니다.</p>'
        '<p><strong>KNN은 회귀식을 계산하지 않나요?</strong> KNN은 일반적인 선형회귀처럼 전체 학습자료를 하나의 기울기와 절편으로 요약하지 않습니다. 대신 학습 관측을 저장하고 새 입력이 들어오면 이웃을 찾아 예측합니다. 따라서 모형의 복잡도가 고정된 회귀계수의 개수만으로 나타나는 것은 아닙니다. 그렇다고 아무런 학습이 필요 없다는 뜻은 아닙니다. 학습자료를 어떻게 정제하고, 변수를 변환하며, 거리와 이웃 수를 정할 것인지 결정해야 하기 때문입니다.</p>')
    sec('target', '이웃은 무엇을 기준으로 선택할까요?', '예측하려는 결과를 미리 사용해서는 안 됩니다',
        '<p>앞의 예제에서는 X를 이용해 가까운 이웃을 선택했습니다. 선택이 끝난 다음에야 그 이웃들의 Y값을 사용했습니다. 이 순서는 중요합니다.</p>'
        '<p>예를 들어 거래단가를 예측하려고 하는데 기존 거래 가운데 단가가 가장 비슷한 거래를 먼저 선택한다면 어떻게 될까요? 아직 모르는 단가를 기준으로 거래를 선택한 것입니다. 이는 목표값에 해당하는 정보를 미리 사용한 것으로, 예측 문제에서는 데이터 누수가 됩니다.</p>'
        '<p><strong>① 이웃 선택.</strong> 예측 시점에 알고 있는 입력변수 X만 사용하여 가까운 관측값을 찾습니다.</p>'
        '<p><strong>② 결과 예측.</strong> 선택한 이웃의 결과 Y를 평균하거나 범주별로 집계합니다.</p>'
        '<p>다만 이미 완료된 거래들의 가격 분포를 비교하고 비슷한 가격대의 집단을 탐색하는 분석에서는 거래단가 자체를 하나의 특징으로 사용할 수도 있습니다. 이 경우는 아직 모르는 단가를 예측하는 문제가 아니라 이미 관측된 시장의 구조를 탐색하는 문제입니다. <strong>같은 변수라도 분석 목적에 따라 사용할 수 있는 정보인지 판단이 달라집니다.</strong></p>')
    sec('distance', '거리의 정의', '여러 변수의 차이를 하나의 숫자로 표현합니다',
        '<p>변수가 하나일 때는 두 값의 절대 차이로 거리를 계산할 수 있습니다. 하지만 실제 부동산 거래자료에는 여러 변수가 존재합니다. 예를 들어 면적, 층, 건축연도 등을 동시에 비교하려면 각 변수의 차이를 하나의 거리로 합쳐야 합니다.</p>'
        '<p>대표적인 방법은 <strong>유클리드 거리(Euclidean distance)</strong>입니다. 각 변수의 차이를 제곱하고 더한 뒤 제곱근을 취합니다. d(x, z)=√[Σ(xⱼ−zⱼ)²]. 두 변수를 사용하는 경우에는 평면에서 두 점 사이의 직선거리에 해당합니다.</p>'
        '<p>다른 방법으로 <strong>맨해튼 거리(Manhattan distance)</strong>가 있습니다. 변수별 절대 차이를 합산합니다. d(x, z)=Σ|xⱼ−zⱼ|. 예를 들어 두 관측의 차이가 각각 3과 4라면 유클리드 거리는 5이고, 맨해튼 거리는 7입니다.</p>'
        '<p>거리 계산 방식에 따라 어떤 관측값이 가장 가까운지 달라질 수 있습니다. 특히 유클리드 거리는 큰 변수 차이를 제곱해서 반영하므로 특정 변수의 큰 차이에 상대적으로 민감합니다. 그러나 유클리드 거리가 모든 문제에서 더 우수하거나 맨해튼 거리가 항상 더 안정적인 것은 아닙니다. 거리의 선택은 변수의 성격과 분석 목적에 따라 달라집니다.</p>')
    sec('scale', '변수의 스케일', '숫자의 크기가 큰 변수가 거리를 지배할 수 있습니다',
        '<p>이번에는 두 가지 입력변수를 사용해 보겠습니다. 첫 번째 변수는 면적(㎡)이고 두 번째 변수는 층입니다. 기존 관측은 A(50㎡, 1층), B(60㎡, 10층), C(100㎡, 5층), D(110㎡, 6층)입니다. 새로운 입력은 <strong>면적 62㎡, 2층</strong>입니다.</p>'
        '<p>면적과 층의 차이를 그대로 사용한 유클리드 거리는 A가 √145≈12.0416, B가 √68≈8.2462, C가 √1453≈38.1182, D가 √2320≈48.1664입니다. 따라서 가장 가까운 관측은 <strong>B</strong>입니다.</p>'
        '<p>그런데 직관적으로 생각해 보면 A와 B 가운데 어느 쪽이 더 비슷할까요? A는 면적이 12㎡ 차이 나지만 층 차이는 1층입니다. B는 면적이 2㎡ 차이 나지만 층 차이는 8층입니다. 어떤 차이가 더 중요한지는 실제 분석 목적에 따라 달라질 수 있습니다. 문제는 원래 숫자를 사용한 유클리드 거리가 면적과 층의 차이를 같은 숫자 단위로 합산한다는 사실입니다.</p>'
        '<p>원래 거리에서는 면적처럼 숫자의 규모가 큰 변수가 상대적으로 큰 영향을 미칠 수 있습니다. 따라서 서로 다른 단위의 변수를 함께 사용할 때는 거리 계산 전에 변수 스케일을 검토해야 합니다.</p>')
    sec('standardize', '표준화하면 이웃이 달라질까요?', '같은 자료도 변수의 상대적인 비중이 달라집니다',
        '<p>변수의 스케일을 조정하는 대표적인 방법이 <strong>표준화(Standardization)</strong>입니다. Zⱼ=(Xⱼ−X̄ⱼ)/sⱼ. 여기서 평균과 표준편차는 학습자료에서 계산합니다.</p>'
        f'<p>이번 가상 학습자료 네 건의 모집단형 표준편차는 면적 약 {scales[0]:.4f}㎡, 층 약 {scales[1]:.4f}층입니다. 표준편차 계산 시 분모에 학습 관측수 4를 사용했습니다. 평균은 면적 80㎡, 층 5.5층이며 두 점의 차이에서 상쇄됩니다. 표준편차로 나누는 효과는 남습니다.</p>'
        '<p>표준화 거리 d_std=√[Σ((Qⱼ−Xᵢⱼ)/sⱼ)²]로 계산하면 A는 약 0.5649, B는 약 2.5000, C는 약 1.7606, D는 약 2.2596입니다. 표준편차를 25.4951과 3.2016으로 반올림한 뒤 B를 다시 계산하면 약 2.501이 됩니다. 그림과 표는 반올림하기 전의 표준편차를 사용하므로 B는 2.5000입니다. 순위는 어느 쪽으로 반올림해도 바뀌지 않습니다.</p>'
        '<p>표준화 후에는 <strong>A가 B보다 가까워졌습니다.</strong> 전체 순위도 원래 거리의 B → A → C → D에서 A → C → D → B로 바뀝니다. 표준화가 데이터의 실제 위치나 층을 바꾼 것은 아닙니다. 각 변수의 차이를 비교하는 기준을 바꾸었을 뿐입니다. <strong>표준화는 단순한 계산 편의가 아니라 유사성을 정의하는 방식에도 영향을 미칩니다.</strong></p>'
        '<p>하지만 표준화한 거리가 반드시 시장에서 더 적절한 거리라는 뜻은 아닙니다. 면적과 층의 실질적인 중요도, 측정 오류, 자료의 분포 등을 함께 검토해야 합니다.</p>'
        + scale_controls + g2
        + scale_table('raw', raw, '원래 단위. 제곱 기여는 차이의 제곱이고, 거리의 제곱은 두 기여의 합입니다.')
        + scale_table('std', scaled, '표준화. 제곱 기여는 (차이/표준편차)²입니다. 눈금이 다르므로 위 표의 거리 숫자와 크기를 직접 비교하지 않습니다.')
        + '<p><strong>상수 변수는 어떻게 처리할까요?</strong> 모든 학습 관측에서 값이 같은 변수는 표준편차가 0입니다. 따라서 일반적인 표준화 공식에서 0으로 나눌 수 없습니다. 상수 변수는 거리 구분에 도움이 되지 않으므로 제거하거나 별도의 일관된 규칙으로 처리할 수 있습니다.</p>'
        '<p>또한 이상치가 존재하면 평균과 표준편차가 크게 달라질 수 있습니다. 이 경우 중앙값과 사분위수 범위 등을 사용하는 강건한 스케일 조정 방법도 검토할 수 있습니다. 하지만 강건 표준화 역시 모든 문제에서 더 나은 이웃을 보장하지는 않습니다.</p>')
    sec('leakage', '표준화와 데이터 누수', '검증자료까지 사용해 표준화 기준을 만들면 안 됩니다',
        '<p>23장과 26장에서는 학습·검증 자료의 경계를 구별하는 이유를 배웠습니다. KNN에서는 이러한 구분이 더욱 중요할 수 있습니다. 이웃을 결정하는 거리 자체가 변수의 스케일에 영향을 받기 때문입니다.</p>'
        '<p>예를 들어 교차검증에서 전체 자료를 먼저 표준화한 뒤 학습과 검증으로 나눈다고 가정하겠습니다. 그러면 검증자료의 면적과 층 정보가 평균과 표준편차 계산에 사용됩니다. 따라서 이웃을 찾는 기준에 검증자료의 정보가 미리 반영될 수 있습니다.</p>'
        '<p>올바른 절차는 다음과 같습니다. <strong>각 폴드에서 학습자료 선택 → 표준화 기준 계산 → 학습자료 변환 → 같은 기준으로 검증자료 변환 → 거리 계산과 예측.</strong> 이 원칙은 표준화 외에도 결측치 대체, 범주형 인코딩, 차원축소 등 자료에서 기준을 학습하는 전처리에 적용됩니다. 또한 최적 K와 거리 가중치 등도 검증 절차에 맞춰 선택해야 합니다.</p>'
        '<p><strong>거리 계산을 시작하기 전에 전처리 기준이 어느 자료에서 결정되었는지 확인해야 합니다.</strong></p>')
    sec('complexity', 'K값과 모형의 복잡도', '이웃을 적게 사용할수록 가까운 거래의 영향을 크게 받습니다',
        '<p>KNN에서 K는 예측에 사용할 이웃의 수입니다. K가 작으면 아주 가까운 소수 관측값의 결과를 반영합니다. 반대로 K가 크면 더 많은 관측값을 모아 평균합니다.</p>'
        '<table class="knn-metrics"><caption>X=3.2, 균등 가중. 선택된 Y는 가까운 순서입니다.</caption><thead><tr><th>K</th><th>선택된 이웃의 Y</th><th>예측값</th></tr></thead><tbody>'
        '<tr><td>1</td><td>5</td><td>5.00</td></tr><tr><td>3</td><td>5, 3, 2</td><td>3.33</td></tr><tr><td>5</td><td>5, 3, 2, 4, 8</td><td>4.40</td></tr></tbody></table>'
        '<p>이번 예제에서 K=5는 모든 학습 관측을 사용합니다. 따라서 입력값이 어디에 있든 K=5의 균등 가중 회귀 예측은 전체 학습 Y의 평균인 4.4가 됩니다.</p>'
        + k_curve + g3 +
        '<p>K가 작은 경우에는 가까운 관측값 하나의 결과가 예측에 크게 반영됩니다. 따라서 예측곡선이 국소적인 변화에 민감할 수 있습니다. 반면 K가 커지면 예측이 상대적으로 부드러워질 수 있지만, 중요한 국소적 관계를 놓칠 수도 있습니다. 이것은 24장에서 배운 편향–분산의 균형과 연결됩니다. 하지만 <strong>K가 커질수록 예측오차가 반드시 감소하는 것은 아닙니다.</strong> 적절한 K값은 자료의 규모와 특성, 검증 결과에 따라 달라집니다.</p>')
    sec('training-error', 'K=1의 학습오차가 0이면 좋은 모형일까요?', '자기 자신을 가장 가까운 이웃으로 찾았을 수 있습니다',
        '<p>학습자료의 입력 X가 서로 중복되지 않는다고 가정하겠습니다. 그리고 각 학습 관측을 다시 K=1 모형에 입력합니다. 이 경우 가장 가까운 관측은 자기 자신입니다. 자기 자신과의 거리는 0입니다. 따라서 자기 자신의 Y값을 그대로 반환할 수 있고, 학습자료에 대한 예측오차는 0이 됩니다.</p>'
        '<p>하지만 이것이 새로운 거래를 정확하게 예측한다는 뜻은 아닙니다. 이미 알고 있는 답을 다시 반환했기 때문입니다. 새로운 자료에서 예측 성능을 확인하려면 학습에 포함되지 않은 관측으로 평가해야 합니다.</p>'
        '<p>또한 자기 자신을 제외하고 가장 가까운 다른 관측을 찾는 방법도 생각할 수 있습니다. 하지만 동일 거래의 중복 자료나 같은 단지의 반복 거래가 존재한다면 자기 자신만 제외해도 지나치게 쉬운 평가가 될 수 있습니다. 따라서 23장과 26장에서 살펴본 시간·집단 분할도 함께 고려해야 합니다. <strong>학습자료를 얼마나 잘 재현했는지와 새로운 자료를 얼마나 잘 예측할 수 있는지는 서로 다른 문제입니다.</strong></p>')
    sec('tasks', 'KNN 회귀와 분류', '같은 이웃을 찾더라도 결과를 집계하는 방법이 다릅니다',
        '<p>KNN은 회귀와 분류 모두에 사용할 수 있습니다. 두 방법의 차이는 이웃을 찾는 원리보다 이웃들의 결과를 어떻게 모으는지에 있습니다.</p>'
        '<p><strong>① KNN 회귀.</strong> 이웃들의 수치형 Y값을 평균하는 방법입니다. 그림 1과 같은 자료에서 가장 가까운 세 관측의 결과가 5, 3, 2라면 예측은 (5+3+2)/3≈3.3333입니다.</p>'
        '<p><strong>② KNN 분류.</strong> 이웃들이 속한 범주를 집계합니다. 예를 들어 가장 가까운 다섯 관측의 라벨이 양성, 양성, 음성, 양성, 음성이라면 양성이 세 건, 음성이 두 건입니다. 균등 가중 다수결을 사용하면 양성으로 판정하고, 양성 이웃 비율은 3/5=0.6입니다. 이 값은 양성에 대한 확률형 점수로 사용할 수 있습니다. 하지만 0.6이라는 이웃 비율이 실제 발생확률 60%로 잘 보정되어 있다는 보장은 없습니다. 28장에서 배운 확률 보정과 예측 성능 검증이 별도로 필요합니다.</p>'
        '<p>그림의 분류 상자는 이 다섯 라벨이 아닙니다. 회귀 자료의 Y를 양성·음성으로 바꾸지 않고, 따로 둔 라벨 1·0·1의 양성 비율 2/3을 사용합니다. 2/3 역시 보정된 확률이라고 읽지 않습니다.</p>'
        + task_controls + g4 +
        '<p>회귀는 수치를 평균하고, 분류는 범주를 집계한다는 사실을 기억하면 두 방법의 차이를 이해할 수 있습니다.</p>')
    sec('weights', '거리 가중치', '가장 가까운 이웃과 조금 먼 이웃을 같은 비중으로 볼까요?',
        '<p>지금까지는 선택한 K개 이웃에 같은 비중을 부여했습니다. 이를 <strong>균등 가중(Uniform weighting)</strong>이라고 합니다. 가장 가까운 거래를 더 중요하게 반영하고 싶다면 거리의 역수를 가중치로 사용할 수 있습니다. wᵢ=1/dᵢ. 가중 KNN 회귀의 예측은 Σwᵢyᵢ/Σwᵢ입니다.</p>'
        '<p>X=3.2의 세 이웃은 다음과 같습니다. 거리는 반올림하기 전의 절대 차이이고, 표의 가중치는 그 역수를 소수점 넷째 자리로 보인 것입니다.</p>'
        '<table class="knn-metrics"><caption>K=3 역거리 가중. 예측은 반올림한 가중치가 아니라 1/거리로 계산합니다.</caption><thead><tr><th>이웃 X</th><th>거리</th><th>결과 Y</th><th>역거리 가중치</th></tr></thead><tbody>'
        '<tr><td>4</td><td>0.8</td><td>5</td><td>1.2500</td></tr><tr><td>2</td><td>1.2</td><td>3</td><td>0.8333</td></tr><tr><td>1</td><td>2.2</td><td>2</td><td>0.4545</td></tr></tbody></table>'
        f'<p>균등 가중 예측값은 10/3≈3.3333입니다. 역거리 가중 예측값의 정확한 값은 255/67≈{weighted:.4f}이며, 약 3.81로 반올림됩니다. 본문에 적힌 반올림 가중치 1.25, 0.8333, 0.4545로 다시 계산해도 약 3.81입니다. 가까운 이웃 X=4의 Y=5가 더 크게 반영되어 예측값이 높아졌습니다. 그림 1에서 거리 가중을 누르면 이 값이 상태에 표시되고, 그림 3의 곡선은 균등 가중으로 유지됩니다.</p>'
        '<p>그러나 거리 가중치가 항상 예측 성능을 개선하는 것은 아닙니다. 아주 가까운 관측값이 이상치라면 그 관측의 영향력이 오히려 과도하게 커질 수 있습니다. 또한 거리가 0이라면 1/d를 그대로 계산할 수 없습니다. 이 페이지의 규칙은, 선택한 K개 안에 거리 0인 관측이 있으면 그 관측들만 같은 비중으로 평균하는 것입니다. K를 채울 때 거리가 같으면 학습자료의 앞 번호를 우선합니다. 거리 0으로 나누어 계산이 깨지지 않습니다.</p>'
        '<p><strong>거리 가중치를 사용한다면 가중함수와 거리 0의 처리방식을 함께 명시해야 합니다.</strong></p>')
    sec('ties', '동점과 중복 관측', '같은 거리의 거래가 여러 건 있다면 어떻게 해야 할까요?',
        '<p>KNN에서는 이웃의 순서를 결정해야 합니다. 그런데 두 관측값이 새 입력에서 정확히 같은 거리에 있을 수 있습니다. 예를 들어 K번째 이웃과 K+1번째 이웃의 거리가 같다면 어느 쪽을 선택해야 할까요? 두 관측의 Y가 다르다면 어떤 이웃을 포함하는지에 따라 예측값도 달라질 수 있습니다.</p>'
        '<p>따라서 같은 거리에 대한 일관된 규칙이 필요합니다. 이번 학습 예제에서는 동점일 때 학습자료의 앞 번호를 우선합니다. 하지만 이는 편의를 위한 계산 규칙이지 통계적으로 반드시 최선의 방법이라는 뜻은 아닙니다.</p>'
        '<p>실제 분석에서는 동일 거리의 관측을 어떤 순서로 선택하는지, 동일한 입력이 여러 번 관측되었다면 어떻게 처리하는지, 완전히 동일한 거래가 중복 저장된 것은 아닌지, 같은 단지의 반복 거래가 지나치게 큰 비중을 차지하지 않는지를 검토할 수 있습니다. 또한 K가 홀수라고 해서 모든 동점이 사라지는 것은 아닙니다. 다중 범주 분류나 거리 가중 투표에서는 홀수 K에서도 동점이 발생할 수 있습니다.</p>')
    sec('categorical', '범주형 변수의 거리', '용도지역이나 구조를 숫자로 바꾸는 것만으로 충분할까요?',
        '<p>부동산 자료에는 수치형 변수뿐 아니라 범주형 변수도 있습니다. 예를 들어 용도지역, 지목, 구조, 건물 유형 등이 있습니다. 그런데 제1종일반주거지역을 1, 제2종일반주거지역을 2, 일반상업지역을 3으로 두고 유클리드 거리에 그대로 넣으면, 임의로 부여한 번호가 용도지역 사이의 거리처럼 해석됩니다. 제1종과 제2종의 차이는 1, 제1종과 일반상업지역의 차이는 2가 됩니다. 이 숫자가 실제 시장에서의 유사성을 적절하게 표현한다는 보장은 없습니다.</p>'
        '<p>이 문제를 다루기 위한 표현으로 원핫 인코딩, 범주의 일치·불일치, 수치형과 범주형을 나누는 혼합형 거리를 검토할 수 있습니다. 다만 원핫 인코딩했다고 해서 범주형 변수의 중요도 문제가 자동으로 해결되지는 않습니다. 범주의 개수와 빈도, 수치형 변수와의 스케일, 거리 계산 방식에 따라 범주형 변수가 거리에 미치는 영향이 달라질 수 있기 때문입니다.</p>'
        '<p><strong>중요한 것은 범주형 변수를 어떤 숫자로 저장했는지가 아니라, 서로 다른 범주를 얼마나 다르게 취급할 것인지 결정하는 것입니다.</strong> 이번 학습페이지는 실제 서비스의 가중치 정책을 새로 정하지 않습니다.</p>')
    sec('geography', '지리적 거리와 특성상의 거리', '가까운 위치의 거래가 반드시 비슷한 거래는 아닙니다',
        '<p>부동산에서는 위치가 중요한 변수입니다. 그런데 거리라는 표현에는 두 가지 서로 다른 의미가 있습니다.</p>'
        '<p><strong>① 지리적 거리.</strong> 지도상 두 부동산 사이의 물리적인 거리입니다.</p>'
        '<p><strong>② 특성 공간의 거리.</strong> 면적, 용도지역, 도로 조건, 건물 유형 등 여러 특징이 얼마나 비슷한지 나타내는 거리입니다.</p>'
        '<p>두 거리는 서로 다릅니다. 지리적으로 가까운 두 필지라도 용도지역이나 도로 조건, 개발 가능성이 크게 다를 수 있습니다. 반대로 지리적으로 조금 떨어져 있어도 규모와 이용상황, 가격 형성 요인이 비슷할 수 있습니다. 따라서 위치를 거리 계산에 포함한다면 어떤 목적에서 반영할지 결정해야 합니다.</p>'
        '<p>또한 위도와 경도를 사용하는 경우에는 도 단위를 그대로 미터 단위의 평면거리로 해석해서는 안 됩니다. 필요에 따라 적절한 좌표계나 구면거리 계산을 사용해야 합니다. <strong>지리적으로 가까운 사례를 찾는 것과 경제적·물리적 특성이 비슷한 사례를 찾는 것은 서로 다른 문제입니다.</strong></p>')
    sec('design', '유사거래의 가중치 설계', '모든 변수에 동일한 비중을 부여하는 것이 타당할까요?',
        '<p>실제 부동산 거래를 비교할 때는 변수마다 중요도가 다를 수 있습니다. 예를 들어 토지 거래에서는 용도지역과 지목, 도로 조건, 면적 등이 중요한 비교 요소가 될 수 있습니다. 아파트에서는 단지, 면적, 층, 건축연도, 세대수 등의 특성이 영향을 줄 수 있습니다.</p>'
        '<p>표준화한 수치형 변수에 d_w(x, z)=√[Σ wⱼ((xⱼ−zⱼ)/sⱼ)²]처럼 비음수 가중치 wⱼ를 둘 수 있습니다. 가중치가 크면 해당 변수의 차이가 전체 거리에 더 크게 반영됩니다. 가중치가 0이면 해당 변수는 거리 계산에서 제외됩니다. 하지만 가중치를 많이 부여했다고 해서 그 변수가 실제 가격에 미치는 영향이 반드시 크다는 뜻은 아닙니다. 거리 가중치는 <strong>어떤 관측값을 비슷하게 볼 것인지에 대한 설계</strong>입니다. 회귀계수나 인과효과와 같은 의미가 아닙니다.</p>'
        '<p>가중치를 정할 때는 어떤 부동산을 비교하려는가, 어떤 변수의 차이를 중요하게 볼 것인가, 필수적으로 일치해야 하는 조건이 있는가, 자료에서 유사한 이웃을 충분히 찾을 수 있는가, 선택한 가중치가 새로운 자료에서 유용한 결과를 만드는가를 묻는 일이 중요합니다.</p>'
        '<p>유사거래 분석에서는 모든 특성을 하나의 숫자로 합산하기보다 일부 필수 조건을 먼저 적용하는 방식도 검토할 수 있습니다. 예를 들어 용도지역과 부동산 유형을 먼저 제한한 뒤 그 안에서 면적과 다른 조건의 거리를 계산할 수 있습니다. 다만 이렇게 검색 대상을 엄격하게 제한하면 거래가 적은 지역에서는 이웃 자체가 부족해질 수 있습니다. 따라서 <strong>유사성의 엄격함과 이용 가능한 거래 건수 사이의 균형</strong>도 중요합니다.</p>')
    sec('dimension', '차원의 저주', '변수를 많이 넣으면 항상 더 비슷한 거래를 찾을까요?',
        '<p>유사거래를 찾는 데 사용할 변수를 계속 추가한다고 가정해 보겠습니다. 면적, 층, 건축연도, 도로 조건, 용도지역, 구조, 주차대수 등 여러 변수를 하나씩 추가합니다. 그런데 실제 가격과 관련이 약하거나 중복된 변수가 많다면, 관측값 사이의 거리가 여러 변수의 차이를 포함하게 되면서 실제로 중요한 유사성을 구별하기 어려워질 수 있습니다.</p>'
        '<p>이러한 문제는 고차원 자료에서 나타나는 <strong>차원의 저주(Curse of dimensionality)</strong>와 관련이 있습니다. 차원이 증가하면 같은 수의 관측값으로 채워야 하는 공간이 훨씬 넓어집니다. 따라서 관측자료가 충분하지 않으면 새로운 입력 주변에 가까운 관측값이 거의 없을 수 있습니다. 또한 중요하지 않은 변수들이 거리 계산에 포함되면 실제로 비슷한 관측값을 찾는 능력이 떨어질 수 있습니다.</p>'
        '<p>이를 완화하기 위해 변수 선택이나 차원축소, 가중치 조정 등을 검토할 수 있습니다. 하지만 선택이나 차원축소에 사용할 기준도 학습자료에서 결정해야 합니다. 또한 변수를 적게 사용하는 것이 언제나 최선의 방법은 아닙니다. 중요한 변수를 제거하면 시장의 실질적인 차이를 놓칠 수 있기 때문입니다. <strong>유사거래 탐색에서 중요한 것은 변수의 개수보다 어떤 차이가 의미 있는 차이인지 결정하는 것입니다.</strong></p>')
    sec('reliability', '이웃의 거리와 신뢰성', '가장 가까운 거래라도 충분히 비슷하지 않을 수 있습니다',
        '<p>KNN은 원칙적으로 학습자료에서 가장 가까운 K개 관측을 선택합니다. 하지만 학습자료가 드문 지역에서는 가장 가까운 거래조차 매우 멀리 떨어져 있을 수 있습니다. 어떤 지역의 거래자료가 충분하다면 면적과 이용상황이 비슷한 거래를 여러 건 찾을 수 있습니다. 반면 농촌 지역이나 특수한 부동산 유형에서는 조건이 비슷한 거래가 거의 없을 수 있습니다.</p>'
        '<p>이때 무조건 K=5를 적용하면 다섯 번째 이웃까지 포함하기 위해 실제로는 상당히 다른 거래를 선택해야 할 수도 있습니다. 따라서 KNN에서는 이웃 수뿐 아니라 <strong>가장 먼 선택 이웃까지의 거리</strong>도 확인하는 것이 좋습니다.</p>'
        '<p>또한 일정한 반경 안에서 이웃을 찾는 <strong>반경 이웃(Radius neighbors)</strong> 방식이 있습니다. 이 방법은 일정한 거리 안의 관측값만 선택합니다. 그러나 거래가 드문 곳에서는 해당 범위에 관측값이 하나도 없을 수 있습니다. 이 경우 결과를 어떻게 처리할 것인지도 미리 정해야 합니다. 무조건 예측값을 산출하기보다 유사거래가 부족하다는 사실을 알려주는 것이 더 적절할 수 있습니다. <strong>가장 가까운 이웃이라는 사실과 충분히 유사한 이웃이라는 사실은 다릅니다.</strong></p>'
        '<p>KNN은 학습 입력 범위를 벗어난 곳에서도 이웃의 결과를 반환할 수 있습니다. 다만 그 값이 범위 밖의 추세를 연장한 예측은 아닙니다.</p>')
    sec('validation', 'K와 거리, 가중치는 어떻게 선택할까요?', '개별 설정이 아니라 전체 절차를 함께 검증해야 합니다',
        '<p>KNN의 결과는 이웃 수 K, 거리 계산 방법, 변수의 표준화 방식, 거리 가중치, 범주형 변수의 표현 방식, 탐색 대상의 범위에 영향을 받습니다. 따라서 K만 변경하면서 최적값을 찾았다고 해서 전체 유사거래 탐색 절차가 검증되었다고 볼 수는 없습니다. K=3과 K=5를 비교한다면 사용한 거리와 표준화 방법도 명확하게 고정하거나 함께 탐색해야 합니다.</p>'
        '<p>교차검증에서는 각 폴드마다 학습자료로 결측 대체와 표준화, 거리 변환, 변수 선택과 가중치를 정합니다. 그다음 학습자료에서 이웃 후보를 준비하고, 검증자료의 입력 X만으로 이웃을 검색합니다. 선택한 이웃의 학습 Y로 예측한 뒤 검증자료의 실제 Y와 비교합니다. 검증자료의 Y를 이웃 검색에 사용하지 않고, 전체 자료를 먼저 표준화한 뒤 나누지도 않습니다.</p>'
        '<p>회귀라면 MAE나 RMSE 등을 비교할 수 있고, 분류라면 정확도와 재현율, 확률 평가 등을 검토할 수 있습니다. 다만 KNN의 목적이 예측이 아니라 유사거래의 탐색과 설명이라면 예측오차 하나만으로 유사성의 타당성을 평가하기 어렵습니다. 거래의 실제 특성과 선정 결과의 해석 가능성도 중요합니다.</p>'
        '<p>부동산에서는 동일 단지와 지역의 반복 거래, 시간 변화, 특수 거래 여부 등을 고려해 평가자료를 구성해야 합니다. 동일 거래의 중복을 서로 다른 독립 거래처럼 두지 않고, 새 단지를 예측하는 목적이라면 같은 단지가 학습과 평가에 함께 들어가지 않게 하며, 미래 예측이라면 당시 공개되지 않은 거래정보를 사용하지 않습니다. 선택에 사용한 가장 좋은 교차검증 점수를 독립된 시험 성능으로 말하지 않습니다. <strong>검증에서 가장 좋은 점수를 보인 설정이 모든 지역과 유형에서 가장 적절한 유사성 기준이라고 단정해서는 안 됩니다.</strong></p>')
    sec('practice', '확인 문제', '가까움과 예측의 의미를 구별해 보세요',
        '<ol class="learn-exercises">'
        '<li>K=1인 KNN의 학습오차가 0이면 좋은 예측모형일까요?<details><summary>답과 해설</summary><p><strong>반드시 그렇지는 않습니다.</strong> 학습 관측이 자기 자신을 가장 가까운 이웃으로 사용한 결과일 수 있습니다. 새로운 자료에서의 예측오차를 따로 확인해야 합니다.</p></details></li>'
        '<li>표준화하면 가장 가까운 이웃의 순서는 항상 유지될까요?<details><summary>답과 해설</summary><p><strong>아닙니다.</strong> 변수마다 표준편차가 다르면 거리 계산에서 상대적인 비중이 달라지므로 이웃의 순서도 바뀔 수 있습니다.</p></details></li>'
        '<li>거래단가를 예측하면서 같은 거래의 실제 단가를 이용해 이웃을 골라도 될까요?<details><summary>답과 해설</summary><p><strong>적절하지 않습니다.</strong> 아직 모르는 목표값을 이웃 선택에 사용하면 데이터 누수가 발생합니다. 이웃은 예측 시점에 알고 있는 입력변수로 선택해야 합니다.</p></details></li>'
        '<li>가장 가까운 거래 다섯 건을 찾았다면 유사거래가 충분하다고 볼 수 있을까요?<details><summary>답과 해설</summary><p><strong>그렇지 않습니다.</strong> 다섯 번째 이웃까지의 거리나 조건의 차이가 매우 클 수 있습니다. 선택된 이웃이 실제로 얼마나 비슷한지, 탐색 범위에 충분한 거래가 존재하는지 확인해야 합니다.</p></details></li>'
        '</ol>')
    sec('macro', 'CH2 Macro에서 읽기', '쌍둥이 거래에서는 어떤 거래를 비슷하게 볼 것인지가 중요합니다',
        '<p>CH2 Macro에서 유사거래나 쌍둥이 거래를 비교하는 기능을 생각해 보겠습니다. 이러한 분석에서는 어떤 거래가 가까운 이웃인지 계산하는 원리가 중요합니다. 다만 쌍둥이 거래 분석이 반드시 KNN 알고리즘을 사용해야 한다는 뜻은 아닙니다. 유사거래는 다양한 규칙으로 선정할 수 있으며, KNN은 그중 하나의 이해 방법입니다.</p>'
        '<p><strong>① 비교 대상의 범위.</strong> 토지와 아파트, 단독주택처럼 성격이 다른 자료를 무조건 같은 거리 기준으로 비교하는 것은 적절하지 않을 수 있습니다. 지역, 부동산 유형, 용도지역 등 어떤 범위에서 거래를 찾을지 먼저 결정할 필요가 있습니다.</p>'
        '<p><strong>② 변수의 중요도.</strong> 면적과 층, 건축연도, 도로 조건, 구조, 주차 등의 차이를 모두 동일하게 반영해야 할까요? 특히 부동산 유형에 따라 중요한 변수의 조합이 달라질 수 있습니다. 따라서 거리 계산에 포함한 변수와 가중치가 어떤 의미를 갖는지 확인해야 합니다.</p>'
        '<p><strong>③ 표준화와 범주형 변수.</strong> 면적과 층처럼 단위가 다른 변수는 적절한 스케일 조정이 필요할 수 있습니다. 또한 용도지역이나 구조 등 범주형 변수는 임의의 숫자 차이가 실제 거리로 사용되지 않도록 주의해야 합니다.</p>'
        '<p><strong>④ 거래단가와 데이터 누수.</strong> 거래단가를 예측하는 목적이라면 해당 거래의 실제 단가를 이웃 선택 기준으로 사용할 수 없습니다. 반면 완료된 거래들 사이에서 가격대가 유사한 집단을 탐색하려는 목적이라면 거래단가를 비교 특징으로 사용할 수도 있습니다.</p>'
        '<p><strong>⑤ 이웃의 충분성과 시장 유동성.</strong> 도시의 거래 밀집지역과 농촌의 저거래지역은 이용 가능한 비교 거래의 수가 다릅니다. 따라서 같은 K값을 적용하더라도 선정되는 이웃의 실제 유사성은 크게 달라질 수 있습니다. 거래가 부족한 지역에서는 가장 가까운 이웃의 거리와 검색 범위, 유효 거래 건수를 함께 표시하는 것이 중요할 수 있습니다.</p>'
        '<p><strong>⑥ 회귀분석과 쌍둥이 분석의 역할.</strong> 회귀분석은 여러 설명변수와 가격 사이의 관계를 모형으로 표현합니다. 쌍둥이 분석은 일정한 유사성 기준을 바탕으로 비슷한 거래들을 비교하는 데 초점을 둘 수 있습니다. 둘은 서로 보완적이지만 같은 분석은 아닙니다. 특히 회귀계수의 통계적 유의성과 유사거래의 거리 가중치를 동일한 개념으로 해석해서는 안 됩니다.</p>'
        '<p><strong>CH2 Macro에서 유사거래 분석의 핵심은 가장 가까운 거래를 기계적으로 찾는 것이 아니라, 어떤 조건이 비슷한지와 어떤 차이가 중요한지 이해할 수 있도록 하는 것</strong>입니다. 다만 이번 장의 KNN 예제는 머신러닝의 원리를 설명하는 학습자료입니다. 실제 CH2 Macro의 쌍둥이 거래 기능이 동일한 변수, 가중치, 거리 공식이나 KNN 회귀를 사용한다고 전제해서는 안 됩니다. 또한 유사거래의 단가 평균을 개별 부동산의 감정평가상 적정가격으로 자동 확정해서는 안 됩니다.</p>'
        '<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>'
        '<details class="learn-more"><summary>확인한 서비스 범위</summary><div class="learn-more__body">'
        '<p>집합 아파트의 쌍둥이 목록은 개별 매매의 KNN이 아닙니다. 적격 단지가 20곳 이상인 읍면동 재고 프로필을, 그 후보 풀의 평균과 분모 N 표준편차로 표준화한 유클리드 거리로 비교합니다. 표준편차가 0이면 1로 바꿉니다. 구조 거리가 짧은 20곳 안에서 가격분포 거리가 짧은 5곳을 보여 준 뒤, 고른 지역을 지역회귀에 합칠 수 있습니다. 구조에는 단지 수, 거래 수, 연식·층·세대·주차의 중앙값과 사분위 범위, 공시지가의 중앙값과 범위가 들어갑니다. 가격분포에는 가격의 사분위, 평균, 변동계수가 들어갑니다. 이는 이미 관측된 읍면동 프로필의 비교이며, 아직 모르는 개별 거래단가를 이 거리로 예측하는 절차가 아닙니다.</p>'
        '<p>복합의 쌍둥이는 지역 프로필 이웃에 같은 시도이거나 인접 시도인 조건을 두고, 거래가격 중위 비율은 선정 문으로 쓰지 않습니다. 붙일지는 검증으로 봅니다. 토지 랩의 쌍둥이는 지목 비중으로 후보를 좁힌 뒤 젠슨-섀넌 발산과 가격형태로 순위를 매깁니다. 세 경우 모두 이번 장의 K, 가중치, 가상 거리 공식과 같다고 읽지 않습니다.</p>'
        '</div></details>')
    sec('recap', '결론 · 학습 요약', '어떤 관측값을 비슷하다고 볼 것인지 먼저 결정해야 합니다',
        '<p>KNN은 새로운 입력과 가까운 관측값을 찾고 그 결과를 이용해 예측하는 방법입니다. 하지만 이웃의 선택은 입력변수와 거리 계산, 표준화, K값 및 가중치에 따라 달라집니다. 따라서 KNN에서 중요한 것은 계산된 거리의 숫자만이 아닙니다. 그 거리가 어떤 의미를 갖는지 이해하는 것입니다.</p>'
        '<ul class="learn-recap-list">'
        '<li><strong>KNN:</strong> 새 입력에서 가까운 K개 관측값을 찾아 결과를 집계합니다.</li>'
        '<li><strong>입력과 목표:</strong> 이웃은 예측 시점에 알고 있는 X로 선택하고 결과 Y는 집계에 사용합니다.</li>'
        '<li><strong>거리:</strong> 유클리드 거리와 맨해튼 거리 등 서로 다른 계산 방법을 사용할 수 있습니다.</li>'
        '<li><strong>변수 스케일:</strong> 단위와 분포가 다르면 이웃 순서도 달라질 수 있습니다.</li>'
        '<li><strong>표준화:</strong> 변수별 숫자 규모를 조정하지만 언제나 최적의 유사성을 보장하지는 않습니다.</li>'
        '<li><strong>K값:</strong> 작은 K는 국소적인 변동에 민감하고 큰 K는 더 넓게 평균합니다.</li>'
        '<li><strong>회귀·분류:</strong> 수치 결과는 평균하고 범주 결과는 집계합니다.</li>'
        '<li><strong>거리 가중:</strong> 가까운 이웃에 더 높은 비중을 줄 수 있습니다.</li>'
        '<li><strong>범주형 변수:</strong> 임의의 숫자 코드가 현실의 유사성을 나타내지는 않습니다.</li>'
        '<li><strong>차원의 저주:</strong> 변수를 많이 추가해도 가까운 이웃을 더 잘 찾는 것은 아닙니다.</li>'
        '<li><strong>이웃의 충분성:</strong> 가장 가까운 거래도 실제로는 충분히 비슷하지 않을 수 있습니다.</li>'
        '<li><strong>유사거래 분석:</strong> 어떤 조건을 중요하게 볼 것인지와 실제 비교 가능한 거래가 있는지 함께 확인해야 합니다.</li>'
        '</ul>'
        '<p>다음 <a href="/learn/stats/decision-tree/">30장 「의사결정나무」</a>에서는 하나의 거리 대신 여러 조건으로 자료를 나누어 예측하는 방법을 살펴보겠습니다.</p>'
        '<details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul>'
        '<li><a href="https://scikit-learn.org/stable/modules/neighbors.html">scikit-learn: Nearest Neighbors</a></li>'
        '<li><a href="../knn-example.json">가상 이웃·거리·예측 계산 자료</a></li>'
        '</ul><p class="learn-source-note">본문과 그림은 별도 가상 예제로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')

    page = ROOT / 'knn' / 'index.html'
    html = page.read_text(encoding='utf-8')
    html = re.sub(
        r'<article.*?</article>',
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="최근접 이웃과 변수의 스케일">' + '\n'.join(parts) + '</article>',
        html, count=1, flags=re.S,
    )
    html = re.sub(
        r'(name="description"\s+content=").*?("\s*/>)',
        r'\1최근접 이웃의 거리·표준화·K와 회귀·분류 집계를 가상 예제로 학습합니다.\2',
        html, count=1, flags=re.S,
    )
    html = html.replace(
        'aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span>',
        'aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span>',
    )
    if 'knn/chapter.css' not in html:
        html = html.replace('</head>', '<link rel="stylesheet" href="/learn/stats/knn/chapter.css?v=20261025-1" /></head>')
    if 'id="knn-data"' not in html:
        html = html.replace('</body>', '<script type="application/json" id="knn-data">' + json.dumps({'x': x, 'y': y, 'query': query}, ensure_ascii=False) + '</script>\n</body>')
    html = html.replace('knn/experiment.js?v=20261025-1', 'knn/experiment.js?v=20261025-3')
    html = html.replace('knn/experiment.js?v=20261025-2', 'knn/experiment.js?v=20261025-3')
    if 'knn/experiment.js' not in html:
        html = html.replace('</body>', '<script type="module" src="/learn/stats/knn/experiment.js?v=20261025-3"></script>\n</body>')
    if '[그림 ' in html:
        raise SystemExit('figure placeholder remains')
    if html.count('<summary>답과 해설</summary>') != 4:
        raise SystemExit('exercise count changed')
    page.write_text(html, encoding='utf-8')
    block = '"slug": "knn",\n        "title": "최근접 이웃과 변수의 스케일",\n        "soon": false,\n        "macro_relevance": 1'
    replacement = block.replace('"macro_relevance": 1', '"macro_relevance": 3')
    for path in [ROOT / 'course.json', ROOT / 'learn-stats-toc.js']:
        text = path.read_text(encoding='utf-8')
        if block in text:
            path.write_text(text.replace(block, replacement, 1), encoding='utf-8')
    home = ROOT / 'index.html'
    home_text = home.read_text(encoding='utf-8')
    home_old = 'data-macro-relevance="1"><a href="/learn/stats/knn/">29. 최근접 이웃과 변수의 스케일 <span class="learn-relevance" aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span></span>'
    home_new = home_old.replace('data-macro-relevance="1"', 'data-macro-relevance="3"').replace('1단계, 심화', '3단계, 핵심').replace('★☆☆', '★★★')
    if home_old in home_text:
        home.write_text(home_text.replace(home_old, home_new, 1), encoding='utf-8')
    print(f'k1={payload["k1"]} k3={payload["k3"]:.4f} k5={payload["k5"]} weighted={weighted:.6f}')
    print('raw', [round(v, 4) for v in raw])
    print('scaled', [round(v, 4) for v in scaled])
    print('scales', [round(v, 4) for v in scales])


if __name__ == '__main__':
    build()
