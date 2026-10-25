"""Chapter 30: decision tree text, shared-data splits, and leaf predictions."""
from pathlib import Path
from statistics import mean
from html import escape
import json, math, re
ROOT = Path(__file__).resolve().parent


def num(v):
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f'{v:.10g}'


def build():
    rows = json.loads((ROOT / 'example-data.json').read_text(encoding='utf-8'))['rows']
    train, test = rows[:20], rows[20:]

    def sse(rr):
        if not rr:
            return 0
        center = mean(v['price'] for v in rr)
        return sum((r['price'] - center) ** 2 for r in rr)

    def candidates(rr):
        xx = sorted(set(r['area'] for r in rr))
        out = []
        for a, b in zip(xx, xx[1:]):
            t = (a + b) / 2
            left = [r for r in rr if r['area'] <= t]
            right = [r for r in rr if r['area'] > t]
            sl, sr = sse(left), sse(right)
            out.append(dict(
                threshold=t, sse=sl + sr, n_left=len(left), n_right=len(right),
                mean_left=mean(r['price'] for r in left), mean_right=mean(r['price'] for r in right),
                sse_left=sl, sse_right=sr,
            ))
        return out

    cand = candidates(train)
    t1 = min(cand, key=lambda r: r['sse'])['threshold']
    right = [r for r in train if r['area'] > t1]
    t2 = min(candidates(right), key=lambda r: r['sse'])['threshold']
    groups = [
        [r for r in train if r['area'] <= t1],
        [r for r in train if t1 < r['area'] <= t2],
        [r for r in train if r['area'] > t2],
    ]
    av = [mean(r['price'] for r in g) for g in groups]

    def pred(r):
        return av[0 if r['area'] <= t1 else 1 if r['area'] <= t2 else 2]

    metrics = {name: mean(abs(r['price'] - pred(r)) for r in rr) for name, rr in [('train_mae', train), ('test_mae', test)]}
    xs = [r['area'] for r in train]
    ys = [r['price'] for r in train]
    mx, my = mean(xs), mean(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    intercept = my - slope * mx
    linear_test = mean(abs(r['price'] - (intercept + slope * r['area'])) for r in test)
    risks = [
        dict(leaves=1, risk=sse(train) / 20),
        dict(leaves=2, risk=min(v['sse'] for v in cand) / 20),
        dict(leaves=3, risk=sum(sse(g) for g in groups) / 20),
    ]
    for row in cand:
        weighted = row['sse'] / len(train)
        plain = row['sse_left'] / row['n_left'] + row['sse_right'] / row['n_right']
        assert abs(weighted - ((row['n_left'] / 20) * (row['sse_left'] / row['n_left']) + (row['n_right'] / 20) * (row['sse_right'] / row['n_right']))) < 1e-9
        assert plain != weighted
    assert [t1, t2] == [31, 80]
    assert [len(g) for g in groups] == [1, 7, 12]
    assert av[0] == 480 and abs(av[1] - 193.42857142857142) < 1e-12 and abs(av[2] - 105.66666666666667) < 1e-12
    assert abs(metrics['train_mae'] - 23.13809523809524) < 1e-12
    assert abs(metrics['test_mae'] - 60.43333333333333) < 1e-12
    assert abs(linear_test - 41.075441489786265) < 1e-12
    assert abs(risks[0]['risk'] - 8083.89) < 1e-6 and abs(risks[1]['risk'] - 2528.10) < 1e-6 and abs(risks[2]['risk'] - 825.52) < 1e-2
    parent_h = 1
    child_h = -(0.75 * math.log2(0.75) + 0.25 * math.log2(0.25))
    payload = dict(
        source='공통 30건: 출처 미확인 학습 예시. 번호 1~20 학습, 21~30 확인.',
        thresholds=[t1, t2], candidates=cand,
        leaves=[dict(ids=[r['id'] for r in g], mean=m) for g, m in zip(groups, av)],
        metrics={**metrics, 'linear_test_mae': linear_test}, risks=risks,
        classification=dict(parent=[4, 4], left=[3, 1], right=[1, 3], parent_gini=.5, weighted_gini=.375, gain=.125),
    )
    (ROOT / 'decision-tree-example.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def tx(x, y, s):
        return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'

    def ln(x, y, a, b, color='#94a3b8'):
        return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{color}"/>'

    def fig(fid, title, body, cap, box='0 0 640 410'):
        return (
            f'<figure class="learn-chart learn-chart--wide tree-chart"><svg viewBox="{box}" role="img" aria-labelledby="{fid}-title {fid}-desc">'
            f'<title id="{fid}-title">{title}</title><desc id="{fid}-desc">{cap}</desc>{body}</svg>'
            f'<figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
        )

    def node(nid, y, title, sub, on=False):
        stroke = '#d97706' if on else '#94a3b8'
        width = '3' if on else '1.5'
        opacity = '1' if on else '0.55'
        return (
            f'<rect data-node="{nid}" x="12" y="{y}" width="200" height="62" rx="8" fill="#eaf2ff" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>'
            + tx(24, y + 24, title) + tx(24, y + 46, sub)
        )

    body = tx(12, 24, 'X=75는 잎 2로 갑니다')
    body += node('root', 36, '루트 · X ≤ 31?', '학습 20건', True)
    body += node('leaf1', 118, '예 → 잎 1', '1건 · 예측 480.00')
    body += node('split', 200, '아니요 · X ≤ 80?', '오른쪽 19건', True)
    body += node('leaf2', 282, '예 → 잎 2', '7건 · 예측 193.43', True)
    body += node('leaf3', 364, '아니요 → 잎 3', '12건 · 예측 105.67')
    g1 = fig('path', 'X의 조건으로 나누는 세 잎의 회귀나무', body, '그림 1. 첫 질문 뒤 오른쪽만 한 번 더 나눈 3잎 나무입니다. 주황 테두리가 X=75가 지나가는 길입니다. X와 Y는 단위가 없는 학습용 수치입니다.', '0 0 400 450')

    body = tx(24, 28, '첫 분할 후보의 자식 SSE') + ln(65, 325, 590, 325) + ln(65, 65, 65, 325)
    pts = [(65 + r['threshold'] * 1.7, 325 - r['sse'] / 700) for r in cand]
    body += '<polyline points="' + ' '.join(f'{a},{v}' for a, v in pts) + '" fill="none" stroke="#2563eb" stroke-width="2"/>'
    for r, (a, v) in zip(cand, pts):
        chosen = r['threshold'] == t1
        body += f'<circle data-threshold="{num(r["threshold"])}" cx="{a}" cy="{v}" r="{6 if chosen else 4}" fill="{"#d97706" if chosen else "#2563eb"}"/>'
    for v in [0, 100, 200, 300]:
        body += tx(60 + v * 1.7, 350, v)
    body += tx(24, 390, '가로 후보 경계 / 세로 SSE · 주황이 선택 후보')
    g2 = fig('split', '후보 분할 경계별 SSE', body, '그림 2. 점은 서로 다른 학습 X의 중점입니다. 연결선은 순서를 보여 줄 뿐입니다. 기본 선택은 SSE가 가장 작은 X=31이고, 확인 10건은 넣지 않았습니다.')

    body = tx(24, 28, '세 잎의 예측은 구간마다 일정합니다') + ln(65, 325, 590, 325) + ln(65, 55, 65, 325)
    for a, z, v in [(0, t1, av[0]), (t1, t2, av[1]), (t2, 310, av[2])]:
        body += ln(65 + a * 1.65, 325 - v * 0.5, 65 + z * 1.65, 325 - v * 0.5, '#d97706')
    for r in train:
        body += f'<circle cx="{65 + r["area"] * 1.65}" cy="{325 - r["price"] * 0.5}" r="4" fill="#2563eb"/>'
    px = 65 + 75 * 1.65
    body += f'<line id="tree-x-line" x1="{px}" y1="70" x2="{px}" y2="325" stroke="#d97706"/>'
    body += f'<circle id="tree-x-mark" cx="{px}" cy="{325 - av[1] * 0.5}" r="5" fill="#d97706"/>'
    body += f'<text id="tree-x-label" x="{px + 6}" y="62">X=75 · 잎 2 · 193.43</text>'
    for v in [0, 100, 200, 300]:
        body += tx(58 + v * 1.65, 348, v)
    for v in [0, 200, 400]:
        body += tx(18, 330 - v * 0.5, v)
    g3 = fig('prediction', '세 잎 회귀나무의 계단형 예측곡선', body, '그림 3. 파랑은 학습 20건, 주황 가로선은 잎의 평균입니다. X=31과 X=80은 왼쪽 잎에 속합니다. 계단은 예측 규칙이며 실제 평균이 그 경계에서 끊긴다는 뜻은 아닙니다.')

    body = tx(16, 24, '별도 가상 분류 8건')
    body += '<rect x="12" y="40" width="210" height="70" rx="8" fill="#eaf2ff"/>' + tx(24, 66, '부모 8건') + tx(24, 92, '양성 4 · 음성 4 · G=0.5')
    body += '<rect x="12" y="140" width="210" height="70" rx="8" fill="#eaf2ff"/>' + tx(24, 166, '왼쪽 4건') + tx(24, 192, '양성 3 · 음성 1 · G=0.375')
    body += '<rect x="12" y="240" width="210" height="70" rx="8" fill="#eaf2ff"/>' + tx(24, 266, '오른쪽 4건') + tx(24, 292, '양성 1 · 음성 3 · G=0.375')
    body += tx(16, 340, '가중 0.375 · 감소 0.125')
    g4 = fig('classification', '분류나무의 부모·자식과 지니 감소', body, '그림 4. 공통 회귀자료의 Y를 라벨로 바꾼 값이 아닙니다. 감소량 0.125는 범주가 더 나뉘었다는 뜻이지 원인이 생긴 뜻은 아닙니다.', '0 0 400 370')

    options = ''.join(f'<option value="{num(r["threshold"])}"{" selected" if r["threshold"] == t1 else ""}>X={num(r["threshold"])}</option>' for r in cand)
    shortcuts = ''.join(f'<button type="button" data-x="{v}"{" aria-pressed=\"true\"" if v == "75" else ""}>X={v}</button>' for v in ['20', '31', '31.1', '60', '75', '80', '80.1', '100'])
    x_controls = (
        '<div class="tree-controls" hidden><p>입력 X를 바꾸면 그림 1의 경로와 그림 3의 위치가 함께 바뀝니다. 경계에서는 왼쪽 잎을 선택합니다.</p>'
        '<label>입력 X <input class="tree-x" type="number" min="0" max="400" step="0.1" value="75"></label>'
        f'<div class="tree-shortcuts" role="group" aria-label="확인할 입력">{shortcuts}</div>'
        '<p data-path-status role="status">X=75는 31보다 크고 80 이하이므로 잎 2입니다. 학습 관측 7건, 예측 193.43.</p></div>'
    )
    split_controls = (
        '<div class="tree-controls" hidden><p>목록과 그림의 점은 학습 X로 만든 후보만 포함합니다. 아무 숫자를 경계인 것처럼 넣지 않습니다.</p>'
        f'<label>후보 경계 <select id="tree-split">{options}</select></label>'
        '<p id="tree-split-status" role="status">경계 31이 선택되어 있습니다.</p></div>'
    )
    alpha_controls = (
        '<div class="tree-controls" hidden><p>제시된 1잎·2잎·3잎만 비교합니다.</p>'
        '<div class="tree-shortcuts" role="group" aria-label="가지치기 비용"><button type="button" data-alpha="0" aria-pressed="true">α=0</button>'
        '<button type="button" data-alpha="1000">α=1000</button><button type="button" data-alpha="2000">α=2000</button></div>'
        '<p id="tree-alpha-status" role="status">α=0이면 학습 손실이 가장 작은 3잎이 유리합니다.</p></div>'
    )
    parts = []

    def sec(sid, label, title, html):
        parts.append(f'<section class="learn-chapter__step" id="{sid}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{html}</section>')

    sec('quick-start', '서두 · 학습목표', '여러 조건을 차례로 적용하면 자료를 어떻게 구분할 수 있을까요?',
        '<p>부동산 거래자료를 분석한다고 가정해 보겠습니다. 먼저 토지가 주거지역에 속하는지 질문합니다. 주거지역이라면 다시 면적이 일정 규모 이하인지 나눕니다. 주거지역이 아니라면 다른 용도지역이나 이용상황을 살펴볼 수 있습니다. 이처럼 조건을 차례로 적용하면 거래들을 서로 다른 집단으로 구분할 수 있습니다.</p>'
        '<p>그런데 어떤 조건을 먼저 적용하는 것이 좋을까요? 면적을 먼저 구분해야 할까요? 용도지역을 먼저 구분해야 할까요? 또한 면적을 구분한다면 100㎡에서 나누는 것이 좋을까요, 아니면 200㎡에서 나누는 것이 좋을까요?</p>'
        '<p>이러한 질문과 경계를 자료에서 찾아내는 대표적인 머신러닝 방법이 <strong>의사결정나무(Decision tree)</strong>입니다. 의사결정나무는 입력변수에 관한 질문을 반복해 관측값을 여러 집단으로 나누고, 마지막 집단에서 예측값을 계산합니다. 구조는 직관적이지만 어떤 질문을 선택하고 언제 분할을 멈출 것인지는 중요한 통계적 문제입니다.</p>'
        '<p>이번 장에서는 의사결정나무의 계산 원리와 과적합, 가지치기, 해석의 한계를 알아보겠습니다.</p>'
        '<ul class="learn-objectives"><li>의사결정나무의 루트·분기 노드·잎을 구별합니다.</li><li>회귀나무가 잎의 평균을 이용해 예측하는 원리를 이해합니다.</li><li>분할 기준을 잔차제곱합으로 선택하는 과정을 살펴봅니다.</li><li>분류나무의 지니 불순도와 엔트로피를 이해합니다.</li><li>깊이와 최소 잎 크기, 가지치기로 복잡도를 조절하는 이유를 알아봅니다.</li><li>의사결정나무의 변수 중요도와 분할 경계를 주의해서 해석하는 방법을 배웁니다.</li><li>CH2 Macro에서 지역·유형별 시장 구조를 분석할 때 활용할 수 있는 개념을 이해합니다.</li></ul>')
    sec('structure', '의사결정나무의 구조', '질문을 따라 내려가면 하나의 잎에 도착합니다',
        '<p>의사결정나무는 여러 질문을 연결한 구조로 이루어집니다. <strong>루트 노드</strong>는 전체 자료에서 처음 질문을 적용하는 시작점입니다. <strong>분기 노드</strong>는 입력변수의 조건에 따라 관측값을 나누는 지점입니다. <strong>잎</strong>은 더 이상 분할하지 않고 최종 예측값을 제공하는 지점입니다.</p>'
        '<p>이번에는 11장부터 사용한 공통 학습자료 30건의 두 수치열을 X와 Y로 놓습니다. 학습자료는 1~20번 20건이고 확인자료는 21~30번 10건입니다. X와 Y는 단위가 없는 학습용 수치입니다. 실제 거래단가나 면적의 단위가 확인된 자료는 아니므로 부동산 단위를 붙이지 않습니다. 관측번호는 거래일이나 시간 순서가 아닙니다.</p>'
        '<p>이번 예제는 첫 분할 이후 오른쪽 자식만 한 번 더 나눈 <strong>3잎 나무</strong>입니다. 모든 노드를 같은 깊이까지 반드시 나누는 구조는 아닙니다. 첫 질문은 X ≤ 31인가이고, 아니라면 X ≤ 80인가를 묻습니다. 경계에 있는 관측은 왼쪽 잎으로 갑니다.</p>'
        + x_controls + g1 +
        '<p><strong>CART는 무엇인가요?</strong> 이번 장은 CART(Classification and Regression Trees)의 기본 원리를 다룹니다. CART는 일반적으로 하나의 노드를 두 자식으로 나누는 이진 분할을 사용합니다. 수치형 목표를 예측하면 회귀나무, 범주형 목표를 예측하면 분류나무라고 부를 수 있습니다. 나무의 구조는 비슷하지만 분할 기준과 출력은 목표의 유형에 따라 달라집니다.</p>')
    sec('regression', '회귀나무는 무엇을 예측할까요?', '같은 잎에 속한 관측은 같은 예측값을 받습니다',
        '<p>회귀나무는 수치형 결과를 예측합니다. 제곱오차 기준에서는 각 잎에 속한 학습 Y의 평균을 예측값으로 사용합니다. 평균이 제곱오차를 최소화하는 대표값이기 때문이며, 이는 25장과 연결됩니다.</p>'
        f'<table class="tree-metrics"><caption>학습 20건의 세 잎. 예측오차는 반올림 전 평균으로 계산합니다.</caption><thead><tr><th>최종 잎</th><th>X 조건</th><th>학습 관측수</th><th>예측값</th></tr></thead><tbody>'
        f'<tr><td>잎 1</td><td>X ≤ 31</td><td>1건</td><td>{av[0]:.2f}</td></tr>'
        f'<tr><td>잎 2</td><td>31 &lt; X ≤ 80</td><td>7건</td><td>{av[1]:.2f}</td></tr>'
        f'<tr><td>잎 3</td><td>X &gt; 80</td><td>12건</td><td>{av[2]:.2f}</td></tr></tbody></table>'
        '<p>X=60과 X=75는 둘 다 두 번째 잎이므로 예측값은 약 193.43입니다. X=90은 세 번째 잎으로 가서 약 105.67을 예측합니다. 같은 잎의 서로 다른 입력에 같은 예측값을 줄 수 있습니다. 다만 이것이 실제 Y와 X의 관계가 반드시 계단 형태라는 뜻은 아닙니다. <strong>계단 형태는 의사결정나무가 학습한 예측 규칙의 특징입니다.</strong></p>'
        '<details><summary>잎에 속한 학습 번호</summary><p>잎 1은 7번입니다. 잎 2는 3, 5, 12, 16, 18, 19, 20번입니다. 잎 3은 1, 2, 4, 6, 8, 9, 10, 11, 13, 14, 15, 17번입니다. 번호는 시간 순서가 아닙니다.</p></details>')
    sec('split', '나무는 분할 기준을 어떻게 선택할까요?', '양쪽 집단의 제곱오차 합이 작아지는 경계를 찾습니다',
        '<p>X 하나만 사용할 때는 어느 값에서 나눌지가 문제입니다. 후보 경계 s의 왼쪽과 오른쪽에서 각각 평균 Y를 구하고, 실제 Y와의 차이를 제곱해 더합니다. SSE(s)=Σ_L(yᵢ−ȳ_L)²+Σ_R(yᵢ−ȳ_R)². 회귀나무는 허용된 후보 가운데 SSE가 가장 작은 경계를 선택합니다.</p>'
        '<p>이번 예제는 학습자료의 서로 다른 X를 정렬한 뒤 인접한 값의 중점을 후보로 썼습니다. 두 값 사이의 어느 점을 골라도 학습 관측이 좌우로 나뉘는 구성은 같으므로, 그 구성을 대표하는 값으로 중점을 씁니다. 첫 번째 분할에서 선택된 경계는 <strong>X=31</strong>입니다. 확인자료 10건은 이 선택에 쓰지 않았습니다.</p>'
        + split_controls + g2 +
        '<p>선택된 경계가 시장에 실제로 있는 보편적인 임계값이라는 뜻은 아닙니다. 이 학습자료와 후보, 제약 아래에서 가장 유리했던 값입니다. 최소 잎 크기 같은 제약이 있으면 허용되는 후보도 달라집니다. 구현마다 경계의 등호와 부동소수점 처리가 다를 수 있어, 이번 예제는 중점 후보와 경계에서의 ≤ 규칙을 명시합니다.</p>')
    sec('impurity', 'SSE와 노드 불순도', '관측수가 다른 집단은 크기에 맞게 반영해야 합니다',
        '<p>회귀나무에서 각 자식의 MSE는 SSE를 그 자식의 관측수로 나눈 값입니다. 두 자식의 MSE를 그냥 더하면, 2건짜리 집단과 18건짜리 집단이 같은 비중을 갖게 됩니다. 전체 자료의 평균 제곱오차는 (n_L/n)MSE_L+(n_R/n)MSE_R이고, 이는 (SSE_L+SSE_R)/n과 같습니다.</p>'
        '<p>따라서 같은 부모 안에서 후보를 비교할 때 자식 SSE의 합을 최소화하는 방법과 관측수로 가중한 자식 MSE를 최소화하는 방법은 같은 분할을 고릅니다. <strong>작은 집단과 큰 집단이 전체 오차에 기여하는 비중을 올바르게 계산하는 것</strong>이 중요합니다. SSE와 평균 손실은 단위와 정규화가 다릅니다.</p>')
    sec('greedy', '탐욕적 분할', '현재 가장 좋은 질문이 전체적으로 가장 좋은 나무를 보장할까요?',
        '<p>일반적인 의사결정나무는 현재 노드에서 가장 유리한 분할을 고르고, 그 자식에서 다시 분할을 찾습니다. 이를 <strong>탐욕적 선택</strong>이라고 합니다. 나쁜 뜻은 아니고, 현재 단계에서 가장 유리한 선택을 한다는 뜻입니다.</p>'
        '<p>첫 분할이 지금 SSE를 가장 많이 줄여도, 이후 분할까지 포함한 전체 나무가 최선인지는 별개입니다. 처음에는 면적이 더 좋아 보여도, 여러 조건을 더하면 용도지역을 먼저 나눈 나무가 더 나은 구조가 될 수 있습니다. 일반적인 탐욕적 CART는 가능한 모든 나무를 탐색해 전체 최적해를 구하지 않습니다. <strong>분할이 계산으로 선택되었다는 사실과 전체적으로 최적의 나무라는 주장은 구분해야 합니다.</strong></p>')
    sec('curve', '회귀나무의 예측곡선', '입력이 경계를 넘을 때 예측값이 달라집니다',
        f'<p>이 3잎 나무의 예측은 X ≤ 31이면 {av[0]:.2f}, 31 &lt; X ≤ 80이면 {av[1]:.2f}, X &gt; 80이면 {av[2]:.2f}입니다. 각 구간에서는 값이 일정해 계단과 비슷한 모양이 됩니다. X=31은 첫 번째 잎, X=80은 두 번째 잎입니다.</p>'
        + x_controls + g3 +
        '<p>실제 시장의 평균이 31이나 80에서 갑자기 끊긴다는 뜻은 아닙니다. 나무가 구간별로 예측하는 방식일 뿐입니다. 학습에서 보지 않은 매우 큰 X에도 마지막 잎의 평균을 낼 수 있지만, 범위 밖에서도 Y가 일정하다는 뜻은 아닙니다. 첫 잎은 학습 관측 한 건이라 그 관측을 빼면 경계와 예측이 크게 달라질 수 있습니다. 자료가 조금 바뀌면 31과 80이라는 경계도 달라질 수 있으므로, 고정된 시장 기준으로 읽지 않습니다.</p>')
    sec('error', '학습오차와 확인오차', '세밀한 분할이 새로운 자료에서도 좋은 결과를 줄까요?',
        f'<table class="tree-metrics"><caption>같은 1~20번 학습, 21~30번 확인. MAE는 반올림 전 잎 평균으로 계산했습니다.</caption><thead><tr><th>모형·평가 대상</th><th>MAE</th></tr></thead><tbody>'
        f'<tr><td>세 잎 회귀나무 — 학습 20건</td><td>{metrics["train_mae"]:.2f}</td></tr>'
        f'<tr><td>세 잎 회귀나무 — 확인 10건</td><td>{metrics["test_mae"]:.2f}</td></tr>'
        f'<tr><td>비교 직선회귀 — 확인 10건</td><td>{linear_test:.2f}</td></tr></tbody></table>'
        '<p>이 예제에서 나무는 학습자료의 오차가 상대적으로 작습니다. 확인자료에서는 오차가 더 크고, 같은 분할로 맞춘 직선의 확인 MAE보다도 큽니다. 그렇다고 의사결정나무가 직선회귀보다 나쁜 방법이라는 뜻은 아닙니다. 학습 20건과 확인 10건의 작은 자료이고, 첫 잎은 한 건에 의존합니다. 다른 자료와 복잡도에서는 결과가 달라질 수 있습니다.</p>'
        '<p><strong>학습자료를 세밀하게 나누어 오차를 줄였다고 해서 새로운 자료의 예측오차도 작아지는 것은 아닙니다.</strong> 이는 24장의 과적합과 연결됩니다. 확인자료를 반복해서 보며 모형을 고치면 그 자료는 더 이상 독립적인 최종 시험자료가 아닙니다.</p>'
        '<p><strong>학습 MAE가 더 작으면 과적합이라고 확정할 수 있을까요?</strong> 그 차이는 과적합 가능성을 살펴볼 근거가 됩니다. 차이만으로 확정할 수는 없습니다. 학습과 확인의 분포가 다르거나 확인자료에 특이한 관측이 있어도 오차가 달라질 수 있습니다. 복잡도, 표본, 분할 구조, 반복 검증을 함께 봅니다.</p>')
    sec('classify', '분류나무', '숫자의 평균 대신 범주가 얼마나 섞였는지 살펴봅니다',
        '<p>목표변수가 양성과 음성처럼 범주형이면 분류나무를 사용할 수 있습니다. 제곱오차 대신 범주가 섞인 정도를 분할 기준으로 쓸 수 있습니다. 대표적인 지표가 <strong>지니 불순도</strong> G=1−Σpₖ²입니다. pₖ는 그 노드에서 범주 k의 비율입니다.</p>'
        '<p>양성 4건, 음성 0건이면 지니 불순도는 0입니다. 양성 2건, 음성 2건이면 1−0.5²−0.5²=0.5입니다. 이진 분류에서는 반반일 때 가장 크고, 한 범주만 있으면 0입니다.</p>')
    sec('classify-example', '분류나무의 분할 예제', '부모보다 자식 노드의 혼합 정도를 낮춥니다',
        '<p>이번 예제는 별도의 가상 분류자료입니다. 공통 회귀 학습자료의 Y를 양성과 음성으로 바꾼 자료가 아닙니다. 부모는 양성 4건, 음성 4건이라 지니 불순도가 0.5입니다. 왼쪽은 양성 3건과 음성 1건, 오른쪽은 양성 1건과 음성 3건입니다.</p>'
        '<p>각 자식의 지니 불순도는 1−(3/4)²−(1/4)²=0.375입니다. 자식이 각각 4건이므로 가중 불순도는 (4/8)×0.375+(4/8)×0.375=0.375입니다. 감소량은 0.5−0.375=0.125입니다.</p>'
        + g4 +
        '<table class="tree-metrics"><caption>별도 분류 예제. 회귀 그림과 자료를 공유하지 않습니다.</caption><thead><tr><th>노드</th><th>관측수</th><th>양성</th><th>음성</th><th>지니 불순도</th></tr></thead><tbody>'
        '<tr><td>부모</td><td>8</td><td>4</td><td>4</td><td>0.5</td></tr><tr><td>왼쪽</td><td>4</td><td>3</td><td>1</td><td>0.375</td></tr><tr><td>오른쪽</td><td>4</td><td>1</td><td>3</td><td>0.375</td></tr>'
        '<tr><td>가중 자식</td><td>8</td><td></td><td></td><td>0.375</td></tr><tr><td>감소량</td><td></td><td></td><td></td><td>0.125</td></tr></tbody></table>'
        '<p>다른 후보도 같은 방식으로 비교할 수 있습니다. 감소량이 양수라고 반드시 분할해야 하는 것은 아닙니다. 최소 잎 크기, 최대 깊이, 가지치기 비용이 있을 수 있습니다. 불순도가 줄었다는 것은 범주 구성이 더 나뉘었다는 뜻이지, 그 변수가 결과의 원인이라는 뜻은 아닙니다. 범주 가중치를 쓰면 비율과 불순도 계산이 달라질 수 있습니다.</p>')
    sec('entropy', '엔트로피와 정보이득', '범주의 혼합 정도를 측정하는 또 다른 방법입니다',
        '<p>지니 불순도 외에 엔트로피 H=−Σpₖ log pₖ를 쓸 수 있습니다. 비율이 0인 항은 0으로 둡니다. 로그의 밑이 2이면 이진 분류에서 반반일 때 엔트로피는 1비트이고, 한 범주만 있으면 0입니다.</p>'
        f'<p>같은 분류 예제에서 밑을 2로 두면 부모 엔트로피는 1이고, 각 자식은 약 {child_h:.4f}입니다. 정보이득은 1−0.8113≈{parent_h - child_h:.4f}입니다. 정보이득이 클수록 분할 뒤 혼합이 더 많이 줄었습니다.</p>'
        '<p>지니 불순도와 엔트로피가 항상 같은 분할을 고르는 것은 아닙니다. 로그의 밑을 바꾸면 숫자의 단위는 달라지지만, 같은 밑을 모든 후보에 일관되게 쓰면 후보의 순서는 바뀌지 않습니다. 회귀의 SSE와 분류의 불순도는 서로 다른 손실입니다.</p>'
        '<p><strong>지니 불순도가 0이면 예측확률도 완벽할까요?</strong> 그렇지 않습니다. 학습 잎에 양성만 있으면 관측된 비율은 100%입니다. 새 관측의 실제 확률도 100%라는 뜻은 아니며, 관측이 한두 건이면 비율은 불안정합니다. 잎 비율을 보정된 확률로 쓰려면 별도의 평가가 필요합니다.</p>')
    sec('complexity', '나무의 복잡도', '질문을 계속 추가하면 언제 멈춰야 할까요?',
        '<p>나무가 깊어지면 자료를 더 잘게 나눌 수 있습니다. 각 잎에 한두 건만 남으면 새로운 자료에서 안정적인 예측을 보장하기 어렵습니다. 그래서 복잡도를 조절합니다.</p>'
        '<p><strong>최대 깊이</strong>는 루트에서 잎까지 허용할 분할 단계입니다. <strong>최소 분할 표본수</strong>는 노드를 더 나누려면 필요한 관측수입니다. <strong>최소 잎 표본수</strong>는 분할 뒤 각 자식에 남아야 하는 관측수입니다. <strong>최대 잎 수</strong>는 최종 잎의 개수 제한입니다. 이런 설정은 나무가 자라는 동안 거는 사전 제약입니다.</p>'
        '<p>제한을 지나치게 세게 하면 중요한 관계를 충분히 나타내지 못할 수 있습니다. 나무를 무조건 작게 만드는 것이 목적이 아니라, <strong>중요한 관계는 나타내면서 학습자료의 우연한 변동에는 과도하게 반응하지 않도록 조절하는 것</strong>이 목적입니다.</p>')
    sec('pruning', '가지치기', '먼저 만든 나무에서 불필요한 가지를 줄일 수도 있습니다',
        '<p><strong>가지치기</strong>는 비교적 큰 나무를 만든 다음 일부 분기를 제거하는 방법입니다. 비용복잡도 가지치기는 Rα(T)=R(T)+α|T|입니다. R(T)는 나무의 학습 손실, |T|는 잎 수, α는 잎을 더할 때 부과하는 비용입니다.</p>'
        '<p>이번 장에서 R(T)는 전체 학습 SSE를 학습 관측수 20으로 나눈 값, 즉 학습 MSE입니다. α의 단위도 Y의 제곱입니다.</p>'
        f'<table class="tree-metrics"><caption>제시된 세 후보. 손실은 반올림 전 SSE/20입니다.</caption><thead><tr><th>나무</th><th>잎 개수</th><th>학습 손실 R(T)</th></tr></thead><tbody>'
        f'<tr><td>1잎</td><td>1</td><td>{risks[0]["risk"]:.2f}</td></tr><tr><td>2잎</td><td>2</td><td>{risks[1]["risk"]:.2f}</td></tr><tr><td>3잎</td><td>3</td><td>{risks[2]["risk"]:.2f}</td></tr></tbody></table>'
        + alpha_controls +
        '<p>학습 손실만 보면 3잎이 가장 작습니다. α=1000이면 1잎 9083.89, 2잎 4528.10, 3잎 3825.52로 여전히 3잎이 작습니다. α=2000이면 1잎 10083.89, 2잎 6528.10, 3잎 6825.52로 2잎이 가장 작습니다. 규제의 세기에 따라 선택되는 복잡도가 달라질 수 있습니다.</p>'
        '<p>이 계산은 제시된 세 후보만 비교한 예제입니다. 가능한 모든 나무나 전체 가지치기 경로를 평가한 결과는 아닙니다. 프로그램마다 손실을 정규화하는 방식이 다르면 같은 α 숫자도 의미가 달라집니다.</p>')
    sec('validation', '교차검증으로 복잡도 선택하기', '학습 손실이 가장 작은 나무가 반드시 좋은 것은 아닙니다',
        '<p>최대 깊이, 최소 잎 크기, 가지치기 강도는 26장의 교차검증으로 비교할 수 있습니다. 같은 학습·검증 분할에서 후보를 평가합니다. 회귀나무는 검증 MAE나 RMSE를, 분류나무는 목적에 따라 분류오차나 로그손실 등을 볼 수 있습니다.</p>'
        '<p>각 폴드에서는 학습자료로 분할 기준을 다시 계산해야 합니다. 전체 자료로 나무를 한 번 만든 뒤 검증자료에만 적용하는 것은 교차검증이 아닙니다. 결측치 대체나 데이터 기반 인코딩도 학습 폴드 안에서 정합니다. 복잡도를 고른 뒤 개발자료 전체로 다시 학습할 수 있지만, 최종 시험자료는 그 선택에 쓰지 않습니다.</p>'
        '<p><strong>모형의 복잡도는 학습자료를 얼마나 잘게 나눌 수 있는지가 아니라, 새로운 자료에서 얼마나 안정적인지를 기준으로 정해야 합니다.</strong></p>')
    sec('scale', '변수의 스케일과 의사결정나무', 'KNN처럼 반드시 표준화해야 할까요?',
        '<p>29장에서 거리 기반 KNN은 변수의 단위와 표준화에 민감했습니다. 기본적인 수치형 CART는 값의 크기보다 <strong>순서와 경계</strong>로 나눕니다. 면적을 ㎡에서 평으로 바꾸어도 순서가 유지되면 같은 관측끼리 묶는 경계를 만들 수 있습니다. 그래서 일반적인 의사결정나무에서는 KNN이나 규제회귀처럼 표준화가 반드시 필요하지 않습니다.</p>'
        '<p>다만 반올림으로 값이 겹치거나, 아주 작은 차이가 수치 정밀도로 처리되거나, 근사 분할을 쓰거나, 결측치와 변수 변환이 달라지면 결과가 달라질 수 있습니다. 스케일에 상대적으로 덜 민감하다는 것과 모든 수치 변환에서 결과가 완전히 같다는 말은 구별해야 합니다.</p>')
    sec('categorical', '범주형 변수와 결측치', '용도지역을 숫자 코드로 저장했다고 순서가 생기는 것은 아닙니다',
        '<p>용도지역, 지목, 건물 구조 같은 범주를 1, 2, 3으로 저장하고 수치형 변수처럼 쓰면 나무가 “코드 ≤ 1.5인가?” 같은 질문을 만들 수 있습니다. 그 숫자는 저장용 구분값일 수 있고, 커질수록 하나의 특성이 늘어난다는 뜻이 아닙니다. 임의의 코드에 없는 순서를 부여하지 않도록 주의합니다.</p>'
        '<p>원핫 인코딩이나 범주 분할을 직접 지원하는 알고리즘을 고려할 수 있습니다. 어느 쪽이 맞는지는 범주 수와 빈도, 자료 규모에 따라 달라집니다. 일부 구현은 결측값의 분기 방향을 학습하지만 모두 그런 것은 아닙니다. 결측을 미리 대체한다면 그 기준은 학습자료로만 계산하고, 평가자료의 정보를 미리 반영하지 않습니다.</p>')
    sec('interaction', '변수 사이의 상호작용', '먼저 어떤 조건을 충족했는지에 따라 다음 질문이 달라집니다',
        '<p>먼저 용도지역으로 나누고, 주거지역에서는 면적을, 상업지역에서는 도로 조건을 물을 수 있습니다. 앞의 조건에 따라 다음 변수가 달라지는 방식입니다. 19장의 회귀 상호작용항과 연결되지만 표현은 다릅니다. 선형회귀는 식에 항을 넣고, 나무는 조건별 규칙을 만듭니다.</p>'
        '<p>나무가 분할을 골랐다는 사실만으로 시장에 그 상호작용이 있다고 확정할 수는 없습니다. 표본과 과적합, 우연한 분할을 살펴야 합니다. 수치형 변수를 여러 경계로 나누면 직선 하나로 나타내기 어려운 관계를 구간별 예측으로 보여줄 수 있습니다. 잎의 예측은 일정한 값이라 매끄러운 곡선을 직접 추정하지는 않으며, 관측 범위 밖의 증감 추세를 자연스럽게 연장하지도 않습니다.</p>')
    sec('importance', '변수 중요도의 해석', '먼저 분할에 사용된 변수가 가장 중요한 변수일까요?',
        '<p>나무가 어떤 변수를 분할에 썼는지, 그 변수가 불순도를 얼마나 줄였는지를 모을 수 있습니다. 이를 <strong>불순도 기반 변수 중요도</strong>라고 합니다. 첫 분할에 쓰였다는 이유만으로 시장에서 가장 중요한 변수라고 결론 내리지 않습니다.</p>'
        '<p>값이 많은 연속형 변수는 후보 경계도 많아 우연히 큰 감소를 찾을 가능성이 커질 수 있습니다. 비슷한 정보를 가진 변수들이 있으면 하나만 먼저 쓰이고 나머지는 중요도가 낮아 보일 수 있습니다. 거래 몇 건이 바뀌면 첫 분할 이후가 달라질 수도 있습니다.</p>'
        '<p>순열 중요도는 평가자료에서 한 변수의 값을 섞었을 때 성능이 얼마나 나빠지는지 봅니다. 상관된 변수를 따로 섞으면 원래 자료에 거의 없는 조합이 생길 수 있어, 이 역시 상관구조와 평가 설계의 영향을 받습니다. <strong>변수 중요도가 높다는 것은 그 변수를 바꾸면 거래가격이 그만큼 달라진다는 인과 설명이 아닙니다.</strong> 공시지가, 용도지역, 도로 조건처럼 서로 관련될 수 있는 변수를 읽을 때 이 점을 함께 봅니다.</p>')
    sec('instability', '단일 나무의 불안정성', '같은 자료를 조금만 바꾸어도 구조가 달라질 수 있습니다',
        '<p>질문은 읽기 쉽지만 분할 기준은 자료 구성에 민감할 수 있습니다. X=31이라는 첫 경계가 특이한 한 건의 영향을 크게 받았다면, 그 관측을 뺐을 때 첫 분할이 달라질 수 있습니다. 이 공통 학습자료의 첫 잎도 한 건입니다.</p>'
        '<p>나무를 여러 개 쓰는 방법으로 랜덤 포레스트와 부스팅이 있습니다. 랜덤 포레스트는 학습자료와 분할 변수의 일부를 무작위로 뽑아 여러 나무를 만들고 결과를 모읍니다. 회귀에서는 보통 예측을 평균하고, 분류에서는 투표나 확률형 점수를 집계할 수 있습니다. 부스팅은 비교적 단순한 모형을 순서대로 더하며 정한 손실을 줄입니다. 그래디언트 부스팅은 손실의 기울기를 이용합니다.</p>'
        '<p>이런 방법이 단일 나무의 한계를 보완할 수는 있지만 언제나 예측이 더 좋아지는 것은 아닙니다. 모형이 복잡해지면 개별 나무보다 읽기도 어려워집니다. 이번 계산은 단일 나무의 학습 예제이며, 랜덤 포레스트나 부스팅의 성능을 검증한 결과는 아닙니다.</p>')
    sec('practice', '확인 문제', '분할 조건과 예측값을 구별해 보세요',
        '<ol class="learn-exercises">'
        '<li>앞의 3잎 회귀나무에서 X=75의 예측값은 얼마일까요?<details><summary>답과 해설</summary><p><strong>약 193.43입니다.</strong> X=75는 31보다 크고 80 이하이므로 두 번째 잎에 속합니다. 그 잎의 학습 Y 평균을 예측값으로 사용합니다.</p></details></li>'
        '<li>분할 후 두 자식의 MSE를 단순히 더하면 왜 문제가 될 수 있을까요?<details><summary>답과 해설</summary><p><strong>두 자식의 관측수가 다를 수 있기 때문입니다.</strong> 전체 자료의 평균 제곱오차를 구하려면 각 자식의 MSE에 관측수 비중을 곱해야 합니다.</p></details></li>'
        '<li>양성과 음성이 3:1인 노드의 지니 불순도는 얼마일까요?<details><summary>답과 해설</summary><p>1−(3/4)²−(1/4)²=0.375입니다. 따라서 <strong>0.375</strong>입니다.</p></details></li>'
        '<li>학습 손실이 가장 작은 깊이의 나무를 무조건 선택하면 될까요?<details><summary>답과 해설</summary><p><strong>그렇지 않습니다.</strong> 나무가 깊어지면 학습자료의 우연한 변동까지 따라갈 수 있습니다. 목적에 맞는 교차검증과 복잡도 제약을 사용해야 합니다.</p></details></li>'
        '</ol>')
    sec('macro', 'CH2 Macro에서 읽기', '부동산 시장의 구분 기준과 나무의 분할 기준은 다릅니다',
        '<p>CH2 Macro에서는 거래자료로 지역과 부동산 유형에 따른 시장 구조를 분석합니다. 의사결정나무의 원리는 여러 조건으로 자료를 나누는 생각을 돕는 학습 내용입니다. 나무가 찾은 분할을 시장의 객관적인 구분 기준이라고 단정하지 않습니다.</p>'
        '<p><strong>① 용도지역과 지목.</strong> 가격 형성에 중요할 수 있습니다. 나무가 특정 용도지역을 첫 분할로 고르지 않았다고 그 변수가 시장에서 중요하지 않은 것은 아닙니다. 다른 변수와의 관계, 후보 수, 표본 구성이 영향을 줄 수 있습니다.</p>'
        '<p><strong>② 면적에 따른 가격 구조.</strong> 관계는 비선형일 수 있고 나무는 이를 구간으로 나타낼 수 있습니다. 계산으로 고른 100㎡나 200㎡ 경계를 시장의 보편적인 규모 구분으로 읽지는 않습니다.</p>'
        '<p><strong>③ 지역과 유형별 상호작용.</strong> 지역이나 용도지역에 따라 면적과 도로 조건의 역할이 달라질 수 있습니다. 나무는 조건부 관계를 탐색하는 데 도움을 줄 수 있습니다. 분할 결과를 경제적 효과로 읽으려면 별도의 검토가 필요합니다.</p>'
        '<p><strong>④ 작은 잎과 거래 부족.</strong> 거래가 적은 곳에서는 잎에 소수 거래만 들어갈 수 있습니다. 잎의 평균이 한두 건에 크게 좌우될 수 있으므로 관측수와 거래의 특성을 함께 봅니다.</p>'
        '<p><strong>⑤ 설명형과 예측형.</strong> 예측에서는 검증자료의 MAE·RMSE 등이 중요합니다. 설명에서는 분할이 시장에서 어떤 의미인지, 표본을 바꿔도 안정적인지를 함께 확인합니다.</p>'
        '<p><strong>⑥ 회귀분석과의 차이.</strong> 선형회귀나 로그회귀는 계수로 관계를 나타냅니다. 기본적인 회귀나무는 조건으로 나누고 잎의 평균으로 예측합니다. 나무가 고른 변수와 경계가 회귀계수의 통계적 유의성이나 인과효과를 직접 나타내지는 않습니다.</p>'
        '<p><strong>CH2 Macro에서 중요한 것은 계산으로 발견한 구분 기준이 시장에서 어떤 의미인지, 그리고 그 결과를 뒷받침하는 거래가 충분한지 확인하는 것입니다.</strong> 이번 나무는 학습용 예제이며, 실제 회귀분석과 모형추천이 같은 알고리즘을 쓴다는 뜻은 아닙니다. 잎의 평균을 개별 부동산의 감정평가상 적정가격으로 확정하지 않습니다.</p>'
        '<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>'
        '<details class="learn-more"><summary>확인한 서비스 범위</summary><div class="learn-more__body"><p>backend/app, frontend, frontend-built, frontend-collective, frontend-lab에서 DecisionTree, RandomForest, GradientBoost, xgboost, lightgbm에 해당하는 코드를 찾지 못했습니다. 이 검색을 저장소 전체의 부재 증명으로 확대하지 않습니다. 확인한 회귀와 모형추천은 이번 3잎 나무의 분할, 가지치기, 변수 중요도를 제공하지 않습니다.</p></div></details>')
    sec('recap', '결론 · 학습 요약', '나무의 질문이 이해하기 쉬워도 그 선택이 반드시 안정적인 것은 아닙니다',
        '<p>의사결정나무는 입력 조건으로 자료를 나누고 마지막 잎에서 예측값을 계산합니다. 회귀나무는 잎의 수치를 요약하고, 분류나무는 범주가 섞인 정도를 봅니다. 자료를 지나치게 잘게 나누면 소수 관측에 기대게 됩니다. 분할 기준과 복잡도, 검증을 함께 살펴야 합니다.</p>'
        '<ul class="learn-recap-list">'
        '<li><strong>의사결정나무:</strong> 입력 조건에 따라 자료를 여러 집단으로 나누는 지도학습 방법입니다.</li>'
        '<li><strong>루트·분기·잎:</strong> 시작점에서 질문을 따라 내려가 마지막 잎에서 결과를 얻습니다.</li>'
        '<li><strong>회귀나무:</strong> 제곱오차 기준에서는 잎의 학습 Y 평균을 예측합니다.</li>'
        '<li><strong>분할 기준:</strong> 양쪽 자식의 제곱오차 합이나 가중 불순도가 작아지는 경계를 찾습니다.</li>'
        '<li><strong>탐욕적 선택:</strong> 현재의 최선 분할이 전체 최적 나무를 보장하지는 않습니다.</li>'
        '<li><strong>분류나무:</strong> 지니 불순도나 엔트로피로 범주의 혼합 정도를 평가합니다.</li>'
        '<li><strong>복잡도:</strong> 최대 깊이, 최소 잎 크기 등으로 과적합을 제한합니다.</li>'
        '<li><strong>가지치기:</strong> 학습 손실과 잎 수의 비용을 함께 고려합니다.</li>'
        '<li><strong>스케일:</strong> 기본적인 수치형 나무는 순서에 의존하므로 일반적으로 표준화가 필수는 아닙니다.</li>'
        '<li><strong>변수 중요도:</strong> 분할에 기여했다는 사실을 인과적 중요도로 해석해서는 안 됩니다.</li>'
        '<li><strong>검증:</strong> 학습오차보다 목적에 맞는 새로운 자료에서의 안정성을 확인해야 합니다.</li>'
        '<li><strong>시장 해석:</strong> 분할 경계와 잎 평균을 시장의 확정 기준이나 개별 적정가격으로 해석해서는 안 됩니다.</li>'
        '</ul>'
        '<p>다음 <a href="/learn/stats/clustering/">31장 「군집분석」</a>에서는 목표변수 없이 관측값 사이의 유사성으로 자료를 나누는 방법을 알아보겠습니다.</p>'
        '<details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul>'
        '<li><a href="https://scikit-learn.org/stable/modules/tree.html">scikit-learn: Decision Trees</a></li>'
        '<li><a href="../decision-tree-example.json">분할 후보·잎·오차 재현 자료</a></li>'
        '</ul><p class="learn-source-note">본문과 그림은 공통 학습자료와 별도 가상 분류 예제로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')

    page = ROOT / 'decision-tree' / 'index.html'
    html = page.read_text(encoding='utf-8')
    html = re.sub(
        r'<article.*?</article>',
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="의사결정나무">' + '\n'.join(parts) + '</article>',
        html, count=1, flags=re.S,
    )
    html = re.sub(
        r'(name="description"\s+content=").*?("\s*/>)',
        r'\1의사결정나무의 분할·잎 평균, 지니 불순도, 가지치기와 검증을 학습 예제로 살펴봅니다.\2',
        html, count=1, flags=re.S,
    )
    html = html.replace(
        'aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span>',
        'aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>',
    )
    if 'decision-tree/chapter.css' not in html:
        html = html.replace('</head>', '<link rel="stylesheet" href="/learn/stats/decision-tree/chapter.css?v=20261025-1" /></head>')
    tree_data = dict(
        t1=t1, t2=t2, means=av, counts=[len(g) for g in groups],
        trainMin=min(xs), trainMax=max(xs), candidates=cand, risks=risks,
    )
    if 'id="tree-data"' not in html:
        html = html.replace('</body>', '<script type="application/json" id="tree-data">' + json.dumps(tree_data, ensure_ascii=False) + '</script>\n</body>')
    if 'decision-tree/experiment.js' not in html:
        html = html.replace('</body>', '<script type="module" src="/learn/stats/decision-tree/experiment.js?v=20261025-2"></script>\n</body>')
    if '[그림 ' in html:
        raise SystemExit('figure placeholder remains')
    if html.count('<summary>답과 해설</summary>') != 4:
        raise SystemExit('exercise count changed')
    page.write_text(html, encoding='utf-8')
    block = '"slug": "decision-tree",\n        "title": "의사결정나무",\n        "soon": false,\n        "macro_relevance": 1'
    replacement = block.replace('"macro_relevance": 1', '"macro_relevance": 2')
    for path in [ROOT / 'course.json', ROOT / 'learn-stats-toc.js']:
        text = path.read_text(encoding='utf-8')
        if block in text:
            path.write_text(text.replace(block, replacement, 1), encoding='utf-8')
    home = ROOT / 'index.html'
    home_text = home.read_text(encoding='utf-8')
    home_old = 'data-macro-relevance="1"><a href="/learn/stats/decision-tree/">30. 의사결정나무 <span class="learn-relevance" aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span></span>'
    home_new = home_old.replace('data-macro-relevance="1"', 'data-macro-relevance="2"').replace('1단계, 심화', '2단계, 권장').replace('★☆☆', '★★☆')
    if home_old in home_text:
        home.write_text(home_text.replace(home_old, home_new, 1), encoding='utf-8')
    print(f't={t1:g},{t2:g} leaves={[round(v, 2) for v in av]} train={metrics["train_mae"]:.2f} test={metrics["test_mae"]:.2f} linear={linear_test:.2f}')
    print('risks', [round(r['risk'], 2) for r in risks], 'entropy', round(child_h, 4))


if __name__ == '__main__':
    build()
