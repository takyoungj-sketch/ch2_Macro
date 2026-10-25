"""Chapter 31: clustering text, figures, and checked virtual examples."""
from pathlib import Path
from statistics import mean
from itertools import combinations
from html import escape
import json
import math
import re

ROOT = Path(__file__).resolve().parent
POINTS = [[1, 1], [1, 2], [2, 1], [7, 7], [7, 8], [8, 7]]
NAMES = 'ABCDEF'


def squared(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def fit(initial):
    centers = [POINTS[i][:] for i in initial]
    labels = None
    for _ in range(100):
        labels = [min(range(len(centers)), key=lambda j: squared(p, centers[j])) for p in POINTS]
        if len(set(labels)) != len(centers):
            return None
        new = [[mean(POINTS[i][axis] for i in range(6) if labels[i] == j) for axis in range(2)] for j in range(len(centers))]
        if new == centers:
            break
        centers = new
    return dict(centers=centers, labels=labels, inertia=sum(squared(p, centers[j]) for p, j in zip(POINTS, labels)))


def flat_clusters(height):
    values = [1, 2, 6, 9]
    merges = [[0, 1, 1, 2], [2, 3, 3, 2], [4, 5, 8, 4]]
    consumed = set()
    for row in merges:
        if row[2] <= height:
            consumed.add(row[0])
            consumed.add(row[1])

    def members(node):
        if node < 4:
            return [values[node]]
        left, right, merge_height, _count = merges[node - 4]
        if merge_height <= height:
            return members(left) + members(right)
        return None

    groups = []
    for node in range(4 + len(merges)):
        if node in consumed:
            continue
        if node >= 4 and merges[node - 4][2] > height:
            continue
        group = members(node)
        if group:
            groups.append(sorted(group))
    return sorted(groups, key=lambda group: group[0])


def build():
    models = []
    for k in range(1, 6):
        fitted = [fit(initial) for initial in combinations(range(6), k)]
        models.append(min((row for row in fitted if row is not None), key=lambda row: row['inertia']))
    model = models[1]
    silhouette = []
    for index, point in enumerate(POINTS):
        own = model['labels'][index]
        same = [math.sqrt(squared(point, other)) for other_index, other in enumerate(POINTS) if index != other_index and model['labels'][other_index] == own]
        other = [math.sqrt(squared(point, other)) for other_index, other in enumerate(POINTS) if model['labels'][other_index] != own]
        a = mean(same)
        b = mean(other)
        silhouette.append(dict(a=a, b=b, s=(b - a) / max(a, b)))
    payload = dict(
        description='군집 계산을 설명하는 단위 없는 가상 6점. 모든 관측점 조합을 초기 중심으로 반복한 결과 중 최소 목적값.',
        points=POINTS,
        models=models,
        silhouette=silhouette,
        hierarchy=dict(x=[1, 2, 6, 9], linkage='complete', merges=[[0, 1, 1, 2], [2, 3, 3, 2], [4, 5, 8, 4]]),
    )
    (ROOT / 'clustering-example.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    means = [[4 / 3, 4 / 3], [22 / 3, 22 / 3]]
    left = [squared(POINTS[i], means[0]) for i in range(3)]
    assert all(abs(value - expected) < 1e-12 for value, expected in zip(left, [2 / 9, 5 / 9, 5 / 9]))
    assert abs(sum(left) - 4 / 3) < 1e-12
    assert abs(model['inertia'] - 8 / 3) < 1e-12
    assert all(abs(a - b) < 1e-12 for a, b in zip(model['centers'][0], means[0]))
    assert all(abs(a - b) < 1e-12 for a, b in zip(model['centers'][1], means[1]))
    assert abs(silhouette[0]['s'] - 0.8885767812647701) < 1e-12
    assert abs(silhouette[0]['b'] - (math.sqrt(72) + 2 * math.sqrt(85)) / 3) < 1e-12
    assigned = fit((0, 3))
    assert assigned['labels'] == [0, 0, 0, 1, 1, 1]
    initial_w = sum(squared(point, POINTS[0] if label == 0 else POINTS[3]) for point, label in zip(POINTS, assigned['labels']))
    assert abs(initial_w - 4) < 1e-12 and initial_w >= model['inertia']
    inertias = [row['inertia'] for row in models] + [0]
    assert all(left_w >= right_w - 1e-12 for left_w, right_w in zip(inertias, inertias[1:]))
    assert flat_clusters(6) == [[1, 2], [6, 9]]
    assert flat_clusters(8) == [[1, 2, 6, 9]]
    assert flat_clusters(9) == [[1, 2, 6, 9]]
    assert flat_clusters(1) == [[1, 2], [6], [9]]
    assert flat_clusters(0) == [[1], [2], [6], [9]]
    k6 = dict(centers=[point[:] for point in POINTS], labels=list(range(6)), inertia=0)
    demo = [
        dict(centers=[[1, 1], [7, 7]], labels=None, w=None),
        dict(centers=[[1, 1], [7, 7]], labels=[0, 0, 0, 1, 1, 1], w=4),
        dict(centers=means, labels=[0, 0, 0, 1, 1, 1], w=8 / 3),
        dict(centers=means, labels=[0, 0, 0, 1, 1, 1], w=8 / 3),
    ]
    page_data = dict(points=POINTS, models=models + [k6], demo=demo, hierarchy=payload['hierarchy'])

    def tx(x, y, text, extra=''):
        return f'<text x="{x}" y="{y}"{extra}>{escape(str(text))}</text>'

    def line(x, y, a, b, color='#94a3b8', extra=''):
        return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{color}"{extra}/>'

    colors = ['#2563eb', '#d97706', '#059669', '#7c3aed', '#db2777', '#0891b2']
    body = tx(24, 28, '가상 6점 · K=2 · 글자는 관측, 십자는 중심') + line(36, 325, 340, 325) + line(36, 55, 36, 325)
    for index, (point, label) in enumerate(zip(POINTS, model['labels'])):
        x, y = 36 + point[0] * 36, 325 - point[1] * 30
        body += f'<circle data-point="{index}" cx="{x}" cy="{y}" r="7" fill="{colors[label]}" stroke="#111827"/>'
        body += tx(x - 18, y - 12, NAMES[index]) + tx(x + 10, y - 12, label + 1, f' data-member="{index}"')
    for index, point in enumerate(model['centers']):
        x, y = 36 + point[0] * 36, 325 - point[1] * 30
        body += f'<g data-center="{index}">{line(x - 8, y, x + 8, y, "#111827", " data-h") }{line(x, y - 8, x, y + 8, "#111827", " data-v")}</g>'
    for index in range(2, 6):
        body += f'<g data-center="{index}" visibility="hidden">{line(0, 0, 0, 0, "#111827", " data-h")}{line(0, 0, 0, 0, "#111827", " data-v")}</g>'
    for value in [0, 2, 4, 6, 8]:
        body += tx(28 + value * 36, 350, value) + tx(12, 330 - value * 30, value)
    body += tx(24, 390, 'X₁·X₂는 무단위 · 거리는 원자료 좌표')
    figure1 = (
        '<figure class="learn-chart learn-chart--wide cluster-chart"><svg viewBox="0 0 640 410" role="img" '
        'aria-labelledby="kmeans-title kmeans-desc"><title id="kmeans-title">K-means의 군집과 중심</title>'
        '<desc id="kmeans-desc">그림 1. A·B·C와 D·E·F의 중심은 (4/3, 4/3), (22/3, 22/3)입니다. 십자는 실제 관측이 아닙니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 1. A·B·C와 D·E·F의 중심은 (4/3, 4/3), (22/3, 22/3)입니다. 화면의 축 길이와 실제 거리는 다릅니다.</figcaption></figure>'
    )
    body = tx(24, 28, '같은 자료에서 군집 수를 늘리면 W가 줄어드는 경향') + line(44, 325, 340, 325) + line(44, 55, 44, 325)
    shown = models + [k6]
    coords = [(56 + index * 46, 325 - row['inertia'] * 2.2) for index, row in enumerate(shown)]
    body += '<polyline points="' + ' '.join(f'{x},{y}' for x, y in coords) + '" stroke="#2563eb" stroke-width="2" fill="none"/>'
    for index, ((x, y), row) in enumerate(zip(coords, shown)):
        mark = '#d97706' if index == 1 else '#2563eb'
        radius = 7 if index == 1 else 5
        body += f'<circle data-k="{index + 1}" cx="{x}" cy="{y}" r="{radius}" fill="{mark}"/>'
        body += tx(x - 14, y - 12, f'{row["inertia"]:.2f}') + tx(x - 4, 350, index + 1)
    for value in [0, 50, 100]:
        body += tx(8, 330 - value * 2.2, value)
    body += tx(24, 390, '가로: 군집 수 K / 세로: 군집 내 제곱거리 합 W')
    figure2 = (
        '<figure class="learn-chart learn-chart--wide cluster-chart"><svg id="elbow" viewBox="0 0 640 410" role="img" '
        'aria-labelledby="elbow-title elbow-desc"><title id="elbow-title">군집 수와 목적값</title>'
        '<desc id="elbow-desc">그림 2. K=2의 W는 8/3이고 K=6의 W는 0입니다. 가장 작은 W가 가장 유용한 군집 수는 아닙니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 2. 관측점 초기 조합 중 목적값이 가장 작은 결과입니다. K=2 부근에서 감소 폭이 꺾입니다.</figcaption></figure>'
    )
    body = tx(24, 28, 'K=2의 관측별 실루엣 · 범위 자체는 −1~1') + line(78, 335, 320, 335)
    for index, row in enumerate(silhouette):
        y = 75 + index * 38
        width = row['s'] * 230
        body += tx(48, y + 17, NAMES[index])
        body += f'<rect data-point="{index}" x="78" y="{y}" width="{width}" height="23" fill="{colors[model["labels"][index]]}"/>'
        body += tx(86 + width, y + 17, f'{row["s"]:.3f}', f' data-sil="{index}"')
    body += tx(74, 360, '0') + tx(300, 360, '1') + tx(24, 390, f'가로: 실루엣 s · K=2 평균 {mean(row["s"] for row in silhouette):.3f}')
    figure3 = (
        '<figure class="learn-chart learn-chart--wide cluster-chart"><svg viewBox="0 0 640 410" role="img" '
        'aria-labelledby="silhouette-title silhouette-desc"><title id="silhouette-title">관측별 실루엣</title>'
        '<desc id="silhouette-desc">그림 3. 제곱하지 않은 유클리드 거리입니다. A의 실루엣은 약 0.889입니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 3. 이 예제는 모두 양수라 0~1을 넓게 보이지만, 실루엣은 음수일 수도 있습니다.</figcaption></figure>'
    )
    body = tx(24, 28, '별도 1차원 자료 1·2·6·9 · 완전연결') + line(48, 325, 330, 325) + line(48, 55, 48, 325)
    slots = {0: 78, 1: 138, 2: 210, 3: 270}
    heights = {index: 0 for index in range(4)}
    merges = payload['hierarchy']['merges']
    for index, (left, right, height, _count) in enumerate(merges):
        y = 325 - height * 30
        body += line(slots[left], 325 - heights[left] * 30, slots[left], y, '#2563eb')
        body += line(slots[right], 325 - heights[right] * 30, slots[right], y, '#2563eb')
        body += line(slots[left], y, slots[right], y, '#2563eb')
        slots[4 + index] = (slots[left] + slots[right]) / 2
        heights[4 + index] = height
    body += '<line id="cluster-cut" x1="60" y1="145" x2="320" y2="145" stroke="#d97706" stroke-dasharray="5 4"/>'
    body += tx(168, 135, '높이 6 · 2군집', ' id="cluster-cut-label"')
    for index, value in enumerate([1, 2, 6, 9]):
        body += tx(slots[index] - 18, 350, f'x={value}')
    for value in [0, 2, 4, 6, 8]:
        body += tx(16, 330 - value * 30, value)
    body += tx(24, 390, '세로: 완전연결 병합 높이 / 가로: 배치 순서')
    figure4 = (
        '<figure class="learn-chart learn-chart--wide cluster-chart"><svg id="dendrogram" viewBox="0 0 640 410" role="img" '
        'aria-labelledby="dendrogram-title dendrogram-desc"><title id="dendrogram-title">완전연결 덴드로그램</title>'
        '<desc id="dendrogram-desc">그림 4. 높이 1, 3, 8에서 병합됩니다. 높이 6에서 자르면 두 군집입니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 4. 1과 2는 높이 1, 6과 9는 높이 3, 두 묶음은 가장 먼 거리 8에서 합쳐집니다.</figcaption></figure>'
    )

    def buttons(kind, values, pressed):
        chunks = []
        for value in values:
            state = ' aria-pressed="true"' if value == pressed else ''
            label = f'K={value}' if kind == 'k' else (NAMES[value] if kind == 'point' else f'높이 {value}')
            chunks.append(f'<button type="button" data-{kind}="{value}"{state}>{label}</button>')
        return ''.join(chunks)

    k_buttons = buttons('k', [1, 2, 3, 4, 5, 6], 2)
    controls1 = (
        '<div class="cluster-controls" hidden><p>그림 1과 그림 2는 같은 K를 사용합니다. K=2의 단계 버튼은 초기 중심을 A와 D에 고정한 시연입니다. '
        '그림 2의 점은 관측점으로 만들 수 있는 초기 조합을 모두 시도한 뒤 W가 가장 작은 결과입니다.</p>'
        f'<div class="cluster-shortcuts">{k_buttons}</div>'
        '<div class="cluster-shortcuts"><button type="button" data-step="0">초기 중심</button>'
        '<button type="button" data-step="1">배정</button><button type="button" data-step="2">중심 갱신</button>'
        '<button type="button" data-step="3" aria-pressed="true">수렴</button></div>'
        '<p role="status" id="cluster-kmeans-status"></p></div>'
    )
    controls2 = f'<div class="cluster-controls" hidden><div class="cluster-shortcuts">{k_buttons}</div><p role="status" id="cluster-elbow-status"></p></div>'
    controls3 = (
        f'<div class="cluster-controls" hidden><div class="cluster-shortcuts">{buttons("point", range(6), 0)}</div>'
        '<p role="status" id="cluster-sil-status"></p></div>'
    )
    controls4 = (
        f'<div class="cluster-controls" hidden><div class="cluster-shortcuts">{buttons("cut", [0, 1, 3, 6, 8, 9], 6)}</div>'
        '<p role="status" id="cluster-cut-status"></p></div>'
    )
    parts = []

    def sec(section_id, label, title, section_body):
        parts.append(
            f'<section class="learn-chapter__step" id="{section_id}" data-toc-label="{label}">'
            f'<p class="learn-chapter__label">{label}</p><h2>{title}</h2>{section_body}</section>'
        )

    sec('quick-start', '서두 · 학습목표', '정답을 미리 정하지 않고도 비슷한 거래를 묶을 수 있을까요?',
        '<p>어떤 지역의 부동산 거래자료 1,000건이 있다고 가정해 보겠습니다. 규모로 소형·중형·대형을 나누거나 용도지역과 지목으로 나눌 수 있습니다. 그런 기준은 분석자가 미리 정한 것입니다. 이번에는 면적, 건축연도, 층 같은 특성을 보고 자료에서 서로 비슷한 거래를 묶어 볼 수 있습니다. 이 분석을 군집분석이라고 합니다.</p>'
        '<p>군집분석은 정답 집단이 없어도 관측 사이의 유사성으로 여러 집단을 찾아보는 방법입니다. 무엇을 비슷하다고 볼지, 군집을 몇 개로 나눌지, 만들어진 군집에 어떤 의미가 있는지는 따로 물어야 합니다. 이번 장에서는 K-means와 계층적 군집, 군집의 품질과 해석의 한계를 살펴봅니다.</p>'
        '<ul class="learn-objectives"><li>분류와 군집분석의 차이를 이해합니다.</li><li>K-means의 배정·중심 갱신 과정을 알아봅니다.</li><li>군집 내 제곱거리 합 W를 계산합니다.</li><li>군집 수 K와 엘보 방법을 이해합니다.</li><li>실루엣 계수의 의미와 계산 방법을 알아봅니다.</li><li>계층적 군집과 덴드로그램을 해석합니다.</li><li>변수 표준화·초기값·이상치가 군집 결과에 미치는 영향을 이해합니다.</li><li>CH2 Macro의 시장 구분과 탐색적 군집분석의 역할을 구별합니다.</li></ul>')
    sec('compare-class', '분류와 군집분석', '이미 정해진 범주를 예측하는 것과 새로운 묶음을 찾는 것은 다릅니다',
        '<p>28장의 분류에서는 양성·음성처럼 결과가 학습자료에 있습니다. 모형은 입력과 이미 알려진 결과의 관계를 학습합니다. 군집분석에서는 정답 범주가 없어도 됩니다. 고른 변수에서 관측끼리 얼마나 비슷한지 계산하고 비슷한 관측을 묶습니다.</p>'
        '<table class="cluster-metrics"><caption>분류와 군집분석</caption><thead><tr><th>구분</th><th>분류</th><th>군집분석</th></tr></thead><tbody>'
        '<tr><td>학습 유형</td><td>지도학습</td><td>비지도학습</td></tr><tr><td>정답 라벨</td><td>주어짐</td><td>필요하지 않음</td></tr>'
        '<tr><td>주요 목적</td><td>새로운 관측의 범주 예측</td><td>유사한 집단 탐색</td></tr>'
        '<tr><td>대표 방법</td><td>로지스틱 회귀, 분류나무</td><td>K-means, 계층적 군집</td></tr></tbody></table>'
        '<p>이미 알고 있는 단지 유형을 예측하면 분류에 가깝고, 면적·건축연도·층으로 비슷한 거래를 묶으면 군집분석입니다. 이렇게 얻은 집단이 현실에 원래부터 있던 유일한 구분은 아닙니다. 포함한 변수와 거리 계산에 따라 묶음이 달라질 수 있습니다. 군집은 정해진 유사성 기준에서 발견한 묶음으로 보는 편이 맞습니다.</p>')
    sec('kmeans', 'K-means의 기본 원리', '가까운 중심에 관측값을 배정하고 중심을 다시 계산합니다',
        '<p>K-means에서는 군집 수 K를 먼저 정합니다. K=2이면 두 군집입니다. 처음 중심을 정하고, 각 관측을 가장 가까운 중심에 배정한 뒤, 그 관측들의 좌표 평균으로 중심을 다시 계산합니다. 배정과 갱신이 충분히 안정되면 멈춥니다. 이 중심을 센트로이드라고 합니다. 센트로이드는 변수별 평균이므로 실제 관측과 같은 자리에 있을 필요는 없습니다.</p>'
        '<p>아래 여섯 점은 계산 원리를 위한 별도 가상 자료입니다. 실제 거래자료가 아니고, 앞 장의 공통 학습자료 30건과도 다릅니다. X₁과 X₂에는 면적이나 가격 단위를 붙이지 않습니다.</p>'
        '<table class="cluster-metrics"><caption>여섯 관측</caption><thead><tr><th>관측</th><th>X₁</th><th>X₂</th></tr></thead><tbody>'
        + ''.join(f'<tr><td>{name}</td><td>{point[0]}</td><td>{point[1]}</td></tr>' for name, point in zip(NAMES, POINTS))
        + '</tbody></table>'
        '<p>군집 1을 A·B·C, 군집 2를 D·E·F로 두면 중심은 μ₁=((1+1+2)/3, (1+2+1)/3)=(4/3, 4/3), μ₂=((7+7+8)/3, (7+8+7)/3)=(22/3, 22/3)입니다. 약 (1.333, 1.333)과 (7.333, 7.333)입니다.</p>'
        + controls1 + figure1 +
        '<p>두 중심은 점들의 가운데에 있지만 A~F의 어느 점과도 같지 않습니다. 평균으로 얻은 위치이기 때문입니다. K-means의 중심을 실제 거래의 대표 사례로 읽지 않습니다. 실제 관측 가운데 대표점을 고르는 방법은 K-medoids에서 생각할 수 있습니다.</p>'
        '<details><summary>같은 거리와 빈 군집</summary><p>두 중심까지 거리가 같으면 이번 예제는 번호가 앞선 중심을 택합니다. 배정 뒤 한 중심이 비면 그 초기화는 목적값 비교에서 제외합니다. 빈 군집을 임의로 옮겨 놓고 같은 실행이라고 말하지 않습니다. 단계 시연의 초기 중심은 A와 D이며, 그 절차는 그림 2의 초기 조합 전체 탐색과 다릅니다. 기본 화면의 최종 중심은 본문의 (4/3, 4/3), (22/3, 22/3)입니다.</p></details>')
    sec('objective', 'K-means의 목적함수', '관측과 중심 사이의 제곱거리를 줄입니다',
        '<p>K-means는 관측과 소속 중심의 제곱거리 합 W를 줄입니다. W=ΣₖΣᵢ∈Cₖ‖xᵢ−μₖ‖²이며, 군집 내 제곱합 또는 inertia라고도 부릅니다. 거리는 화면의 픽셀이 아니라 X₁·X₂ 원자료의 유클리드 거리이고, W는 그 거리를 제곱해 더한 값입니다.</p>'
        '<p>군집 1의 중심이 (4/3, 4/3)일 때 A=(1, 1)의 제곱거리는 (1−4/3)²+(1−4/3)²=2/9입니다. B와 C는 각각 5/9입니다. 그래서 W₁=2/9+5/9+5/9=4/3입니다. 군집 2도 4/3이므로 W=8/3, 약 2.67입니다. 실루엣의 거리는 제곱하지 않은 유클리드 거리라 이 W와 다릅니다.</p>')
    sec('optimum', '중심을 옮기면 왜 W가 줄어들까요?', '평균이 제곱오차를 최소화하기 때문입니다',
        '<p>중심을 고정하고 더 가까운 중심에 배정하면 그 관측의 제곱거리는 커지지 않습니다. 배정을 고정하고 중심을 좌표별 평균으로 옮기면 그 군집의 제곱거리 합이 최소가 됩니다. 그래서 한 단계의 W는 증가하지 않습니다. 이번 시연에서는 중심을 A와 D에 둔 채 배정한 W가 4이고, 평균으로 옮기면 8/3으로 줄어든 뒤 배정이 유지됩니다.</p>'
        '<p>이것이 가능한 모든 배정 가운데 W가 가장 작은 전역 최적해를 보장하지는 않습니다. 초기 중심에 따라 다른 결과에 멈출 수 있습니다. 초기 중심을 바꿔 여러 번 실행하거나 K-means++ 같은 초기화를 쓸 수 있습니다. 이 작은 자료의 그림 2는 관측점으로 만들 수 있는 초기 조합을 모두 시도해 W가 가장 작은 결과를 골랐습니다. 관측이 많은 자료에서 그 조합을 모두 보는 일은 현실적이지 않을 수 있습니다.</p>')
    sec('scale', '변수의 스케일', '무엇을 비슷하게 볼 것인지가 군집을 결정합니다',
        '<p>가상 예제의 두 변수는 같은 단위로 두었습니다. 실제 거래에서는 면적 50~200㎡, 층 1~30, 건축연도 1980~2026년처럼 숫자 폭이 다릅니다. 원래 숫자로 유클리드 거리를 계산하면 변동 폭이 큰 변수가 거리를 더 크게 움직일 수 있습니다. 29장처럼 Zⱼ=(Xⱼ−X̄ⱼ)/sⱼ로 표준화하면 차이를 표준편차 단위로 비교할 수 있습니다.</p>'
        '<p>표준화는 통계적 스케일을 맞추는 방법이지, 변수의 경제적 중요도를 정해 주지는 않습니다. 층과 용도지역의 시장 의미가 같다고 볼 수는 없습니다. 용도지역이나 구조를 임의 숫자로 바꿔 평균과 거리를 계산하면 없는 순서가 생길 수 있습니다. 군집을 만들기 전에 어떤 변수를 넣고 어떤 조건은 미리 나눌지 정해야 합니다. 지도상의 거리와 특성 공간의 거리도 구별합니다. 표준화와 결측 대체는 학습에 쓰는 자료로만 기준을 잡습니다.</p>')
    sec('roles', '군집 생성 변수와 사후 해석 변수', '이미 사용한 차이를 새롭게 발견했다고 해석하지 마세요',
        '<p>거래단가를 넣어 군집을 만들면 단가가 비슷한 거래가 묶일 수 있습니다. 그 다음 군집별 평균 단가가 다르다고 해서 새로운 독립적 발견이라고 보기는 어렵습니다. 단가를 기준으로 묶었기 때문에 생긴 차이일 수 있습니다.</p>'
        '<p>면적, 건축연도, 층으로 군집을 만든 뒤 거래단가 분포를 보는 것은 다릅니다. 이때 단가는 군집을 만드는 데 직접 쓰지 않은 결과입니다. 그래도 여러 방식으로 군집을 만들고 단가 차이가 가장 큰 결과만 골랐다면 선택 과정이 남을 수 있습니다. 무엇으로 묶고 무엇으로 설명했는지 적어야 합니다.</p>')
    sec('number', '군집 수 K는 어떻게 결정할까요?', 'W가 가장 작은 K가 정답은 아닙니다',
        '<p>K를 늘리면 같은 자료와 거리에서 전역 최소 W는 커지지 않습니다. 여섯 점을 각각 한 군집으로 두면 K=6이고 W=0입니다. 그것이 가장 좋은 분석은 아닙니다. 공통된 구조를 보는 데는 거의 도움이 되지 않을 수 있습니다. 실제 반복이 전역 최소에 못 미치면 K가 늘었는데도 계산된 W가 커질 수 있습니다. 그때는 최소 W의 성질이 틀린 것이 아니라 그 실행이 전역 최적에 닿지 못했을 가능성을 봅니다.</p>'
        + controls2 + figure2 +
        '<p>엘보 방법은 W가 빨리 줄다가 감소 폭이 완만해지는 자리를 봅니다. 이 가상 자료에서는 K=2 부근의 꺾임이 비교적 뚜렷해 K=2를 후보로 볼 수 있습니다. 모든 자료에 꺾임이 있는 것은 아니고, 꺾임을 어디로 볼지는 주관적일 수 있습니다. W가 급히 주는 자리가 시장에서 의미 있는 구분과 같지도 않습니다. 실루엣, 군집 크기, 표본을 다시 뽑았을 때의 안정성, 해석 가능성을 함께 봅니다.</p>')
    sec('silhouette', '실루엣 계수', '자신의 군집에 가깝고 다른 군집에서는 먼지 살펴봅니다',
        '<p>a(i)는 같은 군집의 다른 관측까지 평균 거리이고, b(i)는 다른 군집들까지의 평균 거리 중 가장 작은 값입니다. s(i)=(b(i)−a(i))/max(a(i), b(i))이며 범위는 −1부터 1입니다. 1에 가까우면 자기 군집에 가깝고 다른 군집에서는 멉니다. 0 근처면 두 평균 거리가 비슷하고, 음수면 다른 군집까지의 평균 거리가 더 짧습니다. 여기서는 제곱하지 않은 유클리드 거리를 씁니다.</p>'
        + controls3 + figure3 +
        '<p>A=(1, 1)은 B, C와 거리가 각각 1이므로 a(A)=1입니다. D, E, F까지는 √72, √85, √85이고 그 평균 b(A)는 약 8.975입니다. s(A)=(8.975−1)/8.975≈0.889입니다. 나머지 점도 같은 K=2 배정으로 계산하며 모두 양수입니다. 이 자료가 양수라는 뜻이 실루엣의 범위가 0~1이라는 뜻은 아닙니다.</p>'
        '<details><summary>관측이 한 건인 군집</summary><p>같은 군집의 다른 관측이 없으면 a(i)를 보통의 방식으로 구할 수 없습니다. 많은 구현은 그 실루엣을 0으로 둡니다. 군집 수가 1이거나 모든 관측이 제각각인 경우에는 일반적인 전체 실루엣을 계산하지 않습니다. 보통 2 이상이고 관측 수보다 작은 군집 수에서 계산합니다.</p></details>'
        '<p>높은 실루엣이 곧 유용한 시장 유형은 아닙니다. 떨어진 두 집단이 같은 시장의 관측일 수도 있고, 길게 이어진 구조는 실루엣이 낮을 수 있습니다. 크기와 밀도가 크게 다르면 더 조심합니다. 평균과 함께 군집별 관측수, 실루엣 분포, 음수 값, 분산, 분석 목적을 봅니다. 거래가 두세 건뿐인 군집은 평균 실루엣이 높아도 안정된 유형으로 보기 어려울 수 있습니다.</p>')
    sec('hierarchy', '계층적 군집분석', '가까운 집단들을 차례로 합치는 방법입니다',
        '<p>응집형 계층적 군집은 각 관측을 하나의 군집으로 시작해 가장 가까운 두 군집을 반복해 합칩니다. 그 과정을 그린 그림이 덴드로그램입니다. 단일연결은 두 군집에서 가장 가까운 쌍, 완전연결은 가장 먼 쌍, 평균연결은 모든 쌍의 평균 거리입니다. Ward는 합칠 때 군집 내 제곱합이 적게 늘어나는 병합을 고릅니다. 같은 자료라도 연결 기준에 따라 순서와 결과가 달라질 수 있으며, 어느 하나가 모든 자료에 더 맞다고 말하지 않습니다.</p>'
        + controls4 + figure4 +
        '<p>그림 4는 별도 1차원 자료 1, 2, 6, 9의 완전연결입니다. 1과 2는 높이 1, 6과 9는 높이 3에서 합쳐집니다. {1, 2}와 {6, 9}의 가장 먼 쌍은 1과 9이므로 마지막 높이는 8입니다. 높이 6에서 자르면 {1, 2}와 {6, 9}입니다. 이번 예제는 병합 높이가 절단 높이 이하이면 그 병합을 반영합니다. 높이 8에서는 한 군집이 됩니다.</p>'
        '<p>세로축이 병합 높이입니다. 가로 간격과 좌우 순서는 원자료의 거리가 아니고, 가지를 뒤집어도 같은 병합일 수 있습니다. 한 번 합친 군집은 뒤에서 다시 나누지 않으므로 초기 병합의 영향이 남습니다.</p>'
        '<details><summary>Ward의 높이도 거리인가요?</summary><p>Ward는 합칠 때 늘어나는 군집 내 제곱합을 기준으로 합니다. 프로그램마다 덴드로그램 높이의 정의가 다를 수 있어, 그 높이를 두 관측의 유클리드 거리와 같다고 읽지 않습니다. 그림 4의 1·3·8은 완전연결의 거리입니다.</p></details>')
    sec('method-compare', 'K-means와 계층적 군집의 차이', '군집 수를 정하는 시점과 만드는 과정이 다릅니다',
        '<table class="cluster-metrics"><caption>두 방법의 차이</caption><thead><tr><th>구분</th><th>K-means</th><th>응집형 계층적 군집</th></tr></thead><tbody>'
        '<tr><td>기본 원리</td><td>가까운 중심에 배정하고 중심 갱신</td><td>가까운 군집부터 병합</td></tr>'
        '<tr><td>군집 수</td><td>K를 정하고 학습</td><td>자르는 높이 등으로 결정</td></tr>'
        '<tr><td>대표 결과</td><td>중심과 배정</td><td>병합 구조와 덴드로그램</td></tr>'
        '<tr><td>주요 설정</td><td>K, 초기 중심, 거리·표준화</td><td>연결 기준, 거리·표준화</td></tr>'
        '<tr><td>주의할 점</td><td>초기값·이상치에 민감</td><td>초기 병합의 영향이 남음</td></tr></tbody></table>'
        '<p>K-means는 중심을 반복해 조정할 수 있습니다. 일반적인 응집형에서는 한 번 합친 군집을 나중에 다시 분리하지 않습니다. 두 방법 모두 변수와 거리에 영향을 받으며, 어느 쪽이 항상 더 좋지는 않습니다.</p>')
    sec('alternatives', '다른 군집분석 방법', '모든 군집이 원형으로 모여 있는 것은 아닙니다',
        '<p>K-means는 중심 주변에 모인 형태에 맞는 경우가 많습니다. 길게 이어지거나 밀도가 다른 자료에는 다른 방법을 검토할 수 있습니다. K-medoids는 대표점을 실제 관측 가운데에서 고릅니다. 그 대표점은 산술평균 중심이 아닙니다.</p>'
        '<p>DBSCAN은 가까운 이웃이 충분히 많은 밀집 지역을 찾고, 일부 관측을 어느 군집에도 넣지 않은 잡음으로 남길 수 있습니다. 잡음이라는 표시가 입력 오류나 잘못된 거래라는 뜻은 아닙니다. 가우시안 혼합모형은 여러 분포의 혼합으로 보고 소속확률을 나타낼 수 있습니다. 그 확률을 가치 상승확률이나 투자 성공확률로 읽지 않습니다. 한 알고리즘의 군집이 다른 알고리즘에서도 같지는 않습니다.</p>')
    sec('stability', '군집의 안정성', '자료를 조금 바꾸어도 같은 군집이 만들어질까요?',
        '<p>초기 중심, 일부 관측의 제외, 변수 하나, 표준화, K를 바꾸면 구성이 달라질 수 있습니다. 군집 번호는 임의 이름표입니다. 같은 관측 집단도 실행마다 번호가 바뀔 수 있으므로, 번호가 같은 비율만으로 안정성을 판단하지 않습니다. 어떤 관측이 함께 묶였는지 보거나 라벨 순서에 영향받지 않는 비교를 쓸 수 있습니다.</p>')
    sec('size', '군집의 크기와 이상치', '소수 관측으로 만든 군집도 의미 있는 유형일까요?',
        '<p>500건 중 3건만 한 군집에 들어갈 수 있습니다. 특이한 거래일 수도 있고 입력 오류나 이상치의 영향일 수도 있습니다. 크기만으로 유효하거나 무의미하다고 정하지 않습니다. K-means는 제곱거리를 쓰므로 극단값이 중심을 크게 움직일 수 있고, 중복 저장과 결측 처리도 배정을 바꿉니다. 군집분석이 자료 품질을 보증하지는 않습니다.</p>')
    sec('naming', '군집의 이름을 어떻게 붙일까요?', '숫자 이름표보다 실제 특성의 차이를 설명하세요',
        '<p>번호가 크다고 더 좋은 거래나 더 높은 가격은 아닙니다. 다시 실행하면 번호가 바뀔 수도 있습니다. 면적이 작은 거래가 많은 군집, 건축연도가 오래된 거래가 많은 군집처럼 분포를 본 뒤 설명합니다. 우수한 투자 군집, 저평가된 군집, 가격 상승 가능성이 높은 군집 같은 이름은 군집분석만으로 확인되지 않습니다.</p>')
    sec('assign-new', '새로운 관측은 어떻게 처리할까요?', '기존 중심에 배정하는 것과 새로운 군집을 만드는 것은 다릅니다',
        '<p>학습이 끝난 K-means에는 중심이 있습니다. 새 관측은 고정된 중심 중 가까운 곳에 배정할 수 있습니다. 모든 중심에서 멀리 있어도 최근접 배정은 어느 한 군집에 넣습니다. 그것이 충분히 비슷한 군집이 있다는 뜻은 아닙니다. 새 관측이 많이 쌓여 구조가 변하면 중심을 다시 학습할 수 있습니다. 계층적 군집에는 새 관측을 기존 덴드로그램에 넣는 표준 예측 규칙이 없는 경우가 많아 별도 규칙이나 재학습이 필요합니다.</p>')
    questions = [
        ('A·B·C의 중심 (4/3, 4/3)은 실제 관측 중 하나일까요?', '<strong>아닙니다.</strong> 중심은 세 관측의 좌표 평균입니다. 실제 관측과 같은 위치에 있을 필요는 없습니다.'),
        ('군집 수를 6으로 늘려 W=0을 얻었다면 가장 좋은 군집분석일까요?', '<strong>반드시 그렇지는 않습니다.</strong> 여섯 관측을 각각 독립된 군집으로 만들면 W는 0이 됩니다. 공통된 구조를 이해하는 데는 별로 도움이 되지 않을 수 있습니다.'),
        ('실루엣 계수가 높으면 실제 시장에서도 독립적인 유형이 존재한다는 증거일까요?', '<strong>아닙니다.</strong> 높은 실루엣은 선택한 변수와 거리에서 군집이 잘 구분된다는 의미입니다. 서로 다른 시장인지는 따로 검토합니다.'),
        ('덴드로그램의 가로축에 표시된 관측 사이의 간격은 실제 거리일까요?', '<strong>아닙니다.</strong> 병합 수준은 세로축에서 읽습니다. 가로 간격이나 순서가 원자료의 거리는 아닙니다.'),
        ('군집 2는 군집 1보다 더 우수한 거래 집단일까요?', '<strong>그렇게 해석할 수 없습니다.</strong> 군집번호는 임의의 이름표입니다. 특성과 가치 판단은 별개입니다.'),
    ]
    sec('practice', '확인 문제', '군집의 계산 결과와 실제 의미를 구별해 보세요',
        '<ol class="learn-exercises">' + ''.join(
            f'<li>{question}<details><summary>답과 해설</summary><p>{answer}</p></details></li>' for question, answer in questions
        ) + '</ol>')
    sec('macro', 'CH2 Macro에서 읽기', '행정구역별 통계와 군집분석은 서로 다른 방식으로 시장을 구분합니다',
        '<p>CH2 Macro는 지역, 유형, 면적 등 여러 기준으로 거래자료를 나눠 시장을 볼 수 있습니다. 그 분석과 군집분석은 관련되지만 같은 방법은 아닙니다.</p>'
        '<p><strong>① 미리 정한 집단과 발견된 군집.</strong> 읍면동, 용도지역, 지목으로 나누는 일은 사전에 정한 기준입니다. 군집분석은 고른 변수의 유사성으로 묶음을 찾습니다. 행정구역별 통계표를 군집분석 결과라고 말하지 않습니다.</p>'
        '<p><strong>② 군집에 사용할 변수.</strong> 토지에서는 면적, 도로 조건, 지목, 용도지역을, 아파트에서는 면적, 건축연도, 층, 단지 규모를 생각할 수 있습니다. 성격이 다른 변수를 기준 없이 함께 넣으면 묶음의 의미가 달라집니다.</p>'
        '<p><strong>③ 가격을 군집에 포함할 것인가.</strong> 거래단가를 넣으면 비슷한 가격대가 묶일 수 있습니다. 단가를 빼고 특성으로 묶은 뒤 단가를 비교하면 다른 관점입니다. 목적에 따라 고릅니다.</p>'
        '<p><strong>④ 서로 다른 시장의 혼합.</strong> 도시와 농촌, 아파트와 토지를 한꺼번에 넣으면 유형이나 가격 규모만 갈라질 수 있습니다. 비교할 시장의 범위를 먼저 정합니다.</p>'
        '<p><strong>⑤ 군집별 표본수.</strong> 거래가 적은 지역은 안정성이 다를 수 있습니다. 중심과 함께 관측수, 분산, 이상치를 봅니다.</p>'
        '<p><strong>⑥ 군집과 회귀분석.</strong> 군집으로 집단을 탐색한 뒤 회귀를 비교할 수는 있습니다. 같은 자료에서 차이가 가장 큰 결과만 골라 유의하다고 말하면 선택 효과가 생깁니다. 탐색과 독립적인 검증을 구별합니다.</p>'
        '<p><strong>⑦ 쌍둥이 거래와의 관계.</strong> 29장의 KNN은 한 관측에 가까운 이웃을 찾습니다. K-means는 자료 전체를 K개로 나누고 중심을 계산합니다. 둘 다 유사성을 쓰지만 목적과 계산은 다릅니다. 쌍둥이 거래 탐색이 군집분석에 기초해야 하는 것은 아닙니다.</p>'
        '<p>군집분석을 쓴다면 새 시장 유형을 확정하는 기능보다, 어떤 유사성 구조가 있는지를 보는 보조 분석으로 접근하는 편이 맞습니다. 이번 장은 학습 예제입니다. 실제 CH2 Macro에 K-means나 계층적 군집이 구현되어 있다는 뜻은 아닙니다. 군집의 평균단가나 중심을 개별 부동산의 감정평가상 적정가격으로 읽지 않습니다.</p>'
        '<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>'
        '<details><summary>확인한 서비스 범위</summary><p>backend/app와 토지·복합·집합·랩 화면에서 K-means, 계층적 군집, DBSCAN, 실루엣 계산에 해당하는 코드는 확인하지 못했습니다. 이 검색을 저장소 전체의 부재 증명으로 확대하지 않습니다. 지역·유형별 집계와 29장에서 구분한 쌍둥이 거래는 이번 여섯 점의 K-means가 아닙니다.</p></details>')
    sec('recap', '결론 · 학습 요약', '군집은 발견되는 동시에 분석자의 선택에 의해 만들어집니다',
        '<p>군집분석은 정답 범주 없이 유사한 묶음을 찾아봅니다. K-means는 중심과의 제곱거리를 줄이도록 배정하고, 계층적 군집은 가까운 집단을 차례로 합칩니다. 의미는 변수, 거리, 군집 수, 알고리즘에 좌우됩니다. 만들었다는 사실보다 안정성과 해석 가능성을 봅니다.</p>'
        '<ul class="learn-recap-list"><li><strong>군집분석:</strong> 정답 라벨 없이 유사성으로 집단을 탐색합니다.</li>'
        '<li><strong>K-means:</strong> 가까운 중심에 배정하고 평균으로 중심을 갱신합니다.</li>'
        '<li><strong>센트로이드:</strong> 평균 좌표이며 실제 관측과 같을 필요는 없습니다.</li>'
        '<li><strong>W:</strong> 관측과 소속 중심의 제곱거리 합입니다.</li>'
        '<li><strong>초기값:</strong> 결과가 달라질 수 있어 여러 초기화를 검토합니다.</li>'
        '<li><strong>군집 수:</strong> K를 늘리면 W를 줄일 수 있지만 유용함이 보장되지는 않습니다.</li>'
        '<li><strong>엘보:</strong> W의 감소 폭이 완만해지는 지점을 참고합니다.</li>'
        '<li><strong>실루엣:</strong> 군집 안의 가까움과 다른 군집과의 분리를 함께 봅니다.</li>'
        '<li><strong>계층적 군집:</strong> 병합 과정을 덴드로그램으로 나타냅니다.</li>'
        '<li><strong>스케일:</strong> 무엇을 비슷하다고 볼 것인지에 영향을 줍니다.</li>'
        '<li><strong>안정성:</strong> 초기값·표본·변수를 바꿔도 묶음이 유지되는지 봅니다.</li>'
        '<li><strong>시장 해석:</strong> 번호나 중심을 우열이나 개별 적정가격으로 읽지 않습니다.</li></ul>'
        '<p>다음 <a href="/learn/stats/reading-results/">32장 「통계 결과를 읽고 판단하는 법」</a>에서는 배운 통계와 예측 결과를 어떤 순서로 판단할지 정리합니다.</p>'
        '<details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul>'
        '<li><a href="https://scikit-learn.org/stable/modules/clustering.html">scikit-learn: Clustering — 알고리즘과 평가 지표</a></li>'
        '<li><a href="../clustering-example.json">가상 관측·중심·목적값·실루엣·병합 자료</a></li></ul>'
        '<p class="learn-source-note">그림과 수치는 별도 가상 자료로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')

    page = ROOT / 'clustering' / 'index.html'
    html = page.read_text(encoding='utf-8')
    html = re.sub(
        r'<article.*?</article>',
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="군집분석">' + '\n'.join(parts) + '</article>',
        html, count=1, flags=re.S,
    )
    html = re.sub(
        r'(name="description"\s+content=").*?("\s*/>)',
        r'\1K-means의 중심과 W, 실루엣, 완전연결 덴드로그램을 가상 예제로 학습합니다.\2',
        html, count=1, flags=re.S,
    )
    html = html.replace(
        'aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span>',
        'aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>',
    )
    if 'clustering/chapter.css' not in html:
        html = html.replace('</head>', '<link rel="stylesheet" href="/learn/stats/clustering/chapter.css?v=20261025-1" /></head>')
    blob = '<script type="application/json" id="cluster-data">' + json.dumps(page_data, ensure_ascii=False) + '</script>'
    if 'id="cluster-data"' not in html:
        html = html.replace('</body>', blob + '\n</body>')
    else:
        html = re.sub(r'<script type="application/json" id="cluster-data">.*?</script>', blob, html, count=1, flags=re.S)
    if 'clustering/experiment.js' not in html:
        html = html.replace('</body>', '<script type="module" src="/learn/stats/clustering/experiment.js?v=20261025-3"></script>\n</body>')
    if '[그림 ' in html:
        raise SystemExit('figure placeholder remains')
    if html.count('<summary>답과 해설</summary>') != 5:
        raise SystemExit('exercise count changed')
    page.write_text(html, encoding='utf-8')
    block = '"slug": "clustering",\n        "title": "군집분석",\n        "soon": false,\n        "macro_relevance": 1'
    replacement = block.replace('"macro_relevance": 1', '"macro_relevance": 2')
    for path in [ROOT / 'course.json', ROOT / 'learn-stats-toc.js']:
        text = path.read_text(encoding='utf-8')
        if block in text:
            path.write_text(text.replace(block, replacement, 1), encoding='utf-8')
        elif replacement not in text:
            raise SystemExit(f'relevance block missing: {path.name}')
    home = ROOT / 'index.html'
    home_text = home.read_text(encoding='utf-8')
    home_old = 'data-macro-relevance="1"><a href="/learn/stats/clustering/">31. 군집분석 <span class="learn-relevance" aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span></span>'
    home_new = home_old.replace('data-macro-relevance="1"', 'data-macro-relevance="2"').replace('1단계, 심화', '2단계, 권장').replace('★☆☆', '★★☆')
    if home_old in home_text:
        home.write_text(home_text.replace(home_old, home_new, 1), encoding='utf-8')
    elif 'data-macro-relevance="2"><a href="/learn/stats/clustering/"' not in home_text:
        raise SystemExit('home listing was not updated')
    print('W', [round(value, 4) for value in inertias], 'sA', round(silhouette[0]['s'], 3), 'cuts', flat_clusters(6))


if __name__ == '__main__':
    build()
