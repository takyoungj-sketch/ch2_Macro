"""Chapter 4 body. Reuses example-data.json and the checked chart coordinates."""
from pathlib import Path
from html import escape
from statistics import median, mean
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def coord(value):
    return repr(float(value))


def tx(x, y, text, extra=''):
    return f'<text x="{x}" y="{y}"{extra}>{escape(str(text))}</text>'


def build():
    rows = json.loads((ROOT / 'example-data.json').read_text(encoding='utf-8'))['rows']
    prices = [row['price'] for row in rows]
    assert len(rows) == 30 and sum(prices) == 4390
    assert min(prices) == 62 and max(prices) == 480
    assert mean(prices) == 4390 / 30 and median(prices) == 122
    ordered = sorted(prices)
    assert ordered[14] == 120 and ordered[15] == 124
    assert sum(price > mean(prices) for price in prices) == 10
    assert sum(price < mean(prices) for price in prices) == 20
    other = [row['price'] for row in rows if row['id'] != 7]
    assert round(mean(other), 2) == 134.83 and median(other) == 120
    scenarios = {}
    for value in (268, 480, 900, 780):
        changed = other + [value]
        scenarios[value] = (sum(changed), mean(changed), median(changed))
    assert scenarios[268][0] == 4178 and round(scenarios[268][1], 2) == 139.27 and scenarios[268][2] == 122
    assert scenarios[480][0] == 4390 and round(scenarios[480][1], 2) == 146.33 and scenarios[480][2] == 122
    assert scenarios[900][0] == 4810 and round(scenarios[900][1], 2) == 160.33 and scenarios[900][2] == 122
    assert scenarios[780][0] == 4690 and round(scenarios[780][1], 2) == 156.33 and scenarios[780][2] == 122
    assert (200 + 100) / 2 == 150 and (10 * 200 + 90 * 100) / (10 + 90) == 110
    assert (10 * 100 + 90 * 200) / 100 == 190
    assert (90 * 100 + 10 * 200) / 100 == 110
    assert (62 + 480) / 2 == 271
    page_data = {
        'rows': [{'id': row['id'], 'price': row['price']} for row in rows],
        'rank15': 120,
        'rank16': 124,
        'median': 122,
    }

    def fig1():
        body = [tx(16, 24, '단가 점 30개 · 세로는 겹침 방지')]
        body.append('<line x1="60" y1="150" x2="560" y2="150" stroke="#cbd5e1"/>')
        lanes = ('115', '101', '87')
        for index, row in enumerate(sorted(rows, key=lambda item: item['price'])):
            fill = '#d97706' if row['id'] == 7 else '#475569'
            stroke = '#d97706' if row['id'] == 7 else '#1e3a8a'
            thick = '3' if row['id'] == 7 else '1'
            body.append(
                f'<circle data-observation="{row["id"]}" cx="{60 + row["price"]}" cy="{lanes[index % 3]}" r="4" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{thick}"/>'
            )
        mean_x = coord(60 + mean(prices))
        body.append(f'<line data-guide="mean" x1="{mean_x}" y1="48" x2="{mean_x}" y2="154" stroke="#047857" stroke-width="2"/>')
        body.append(tx(mean_x, 40, '평균 146.33', ' data-guide="mean" text-anchor="middle"'))
        body.append('<line data-guide="median" x1="182" y1="48" x2="182" y2="154" stroke="#1d4ed8" stroke-width="2"/>')
        body.append(tx(182, 176, '중앙값 122', ' data-guide="median" text-anchor="middle"'))
        for label, x in (('0', 60), ('100', 160), ('200', 260), ('300', 360), ('400', 460), ('500', 560)):
            body.append(tx(x, 198, label, ' text-anchor="middle"'))
        body.append(tx(16, 222, '단가(만원/㎡)'))
        body.append(tx(540, 72, '7번 480', ' text-anchor="middle"'))
        return (
            '<figure class="learn-chart learn-chart--wide mm-chart"><svg id="mm-dots" viewBox="0 0 640 240" role="img" '
            'aria-labelledby="two-centers-title two-centers-desc"><title id="two-centers-title">공통 자료의 평균과 중앙값</title>'
            '<desc id="two-centers-desc">30건의 평균 146.33, 중앙값 122. 7번 480은 주황색입니다.</desc>'
            f'{"".join(body)}</svg><figcaption class="learn-chart__caption">그림 1. 가로 위치는 단가입니다. 세로 위치는 점이 겹치지 않게 벌린 자리이며 다른 변수가 아닙니다.</figcaption></figure>'
        )

    def fig2():
        body = [tx(16, 24, '정렬 순서 · 15번째와 16번째')]
        ordered_rows = sorted(rows, key=lambda item: item['price'])
        for index, row in enumerate(ordered_rows, start=1):
            focus = index in (15, 16)
            fill = '#fff7ed' if focus else '#93c5fd'
            stroke = '#d97706' if focus else '#64748b'
            thick = '3' if focus else '1'
            body.append(
                f'<rect data-order="{index}" data-price="{row["price"]}" x="{12 + (index - 1) * 20}" y="48" width="16" height="36" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{thick}"/>'
            )
        body.append(tx(292, 104, '15번째 120', ' text-anchor="middle"'))
        body.append(tx(332, 124, '16번째 124'))
        body.append(tx(16, 156, '중앙값 (120+124)/2 = 122'))
        body.append(tx(16, 180, '가로 간격은 순서입니다'))
        return (
            '<figure class="learn-chart learn-chart--wide mm-chart"><svg id="mm-ranks" viewBox="0 0 640 200" role="img" '
            'aria-labelledby="median-ranks-title median-ranks-desc"><title id="median-ranks-title">정렬한 30건의 중앙값</title>'
            '<desc id="median-ranks-desc">오름차순 30건에서 15번째 120과 16번째 124의 평균이 122입니다.</desc>'
            f'{"".join(body)}</svg><figcaption class="learn-chart__caption">그림 2. 칸의 가로 위치는 크기순 번호입니다. 120과 124의 차이와 124와 200의 차이를 칸 간격으로 비교하지 않습니다.</figcaption></figure>'
        )

    def fig3():
        body = [tx(16, 24, '7번만 바꾼 평균과 중앙값')]
        body.append(tx(16, 48, '평균', ' fill="#047857"'))
        body.append(tx(70, 48, '중앙값', ' fill="#1d4ed8"'))
        points = {'mean': [], 'median': []}
        circles = []
        for value in (268, 480, 900):
            changed = other + [value]
            for key, actual in (('mean', mean(changed)), ('median', median(changed))):
                cx = 75 + (value - 268) * 0.75
                cy = 265 - (actual - 100) * 2.3
                points[key].append(f'{coord(cx)},{coord(cy)}')
                fill = '#047857' if key == 'mean' else '#1d4ed8'
                stroke = '#d97706' if value == 480 else '#334155'
                thick = '3' if value == 480 else '1'
                circles.append(
                    f'<circle cx="{coord(cx)}" cy="{coord(cy)}" r="4" fill="{fill}" stroke="{stroke}" stroke-width="{thick}" '
                    f'data-series="{key}" data-replacement="{value}" data-value="{coord(actual)}"/>'
                )
        body.append(f'<polyline fill="none" stroke="#047857" points="{" ".join(points["mean"])}"/>')
        body.append(f'<polyline fill="none" stroke="#1d4ed8" points="{" ".join(points["median"])}"/>')
        body.extend(circles)
        for value in (268, 480, 900):
            body.append(tx(coord(75 + (value - 268) * 0.75), 292, value, ' text-anchor="middle"'))
        body.append(tx(16, 316, '7번에 대입한 단가(만원/㎡)'))
        return (
            '<figure class="learn-chart learn-chart--wide mm-chart"><svg id="mm-sensitivity" viewBox="0 0 640 340" role="img" '
            'aria-labelledby="sensitivity-title sensitivity-desc"><title id="sensitivity-title">한 관측값 변화에 대한 민감도</title>'
            '<desc id="sensitivity-desc">7번을 268, 480, 900으로 바꿀 때 평균은 약 139.27, 146.33, 160.33이며 중앙값은 122입니다.</desc>'
            f'{"".join(body)}</svg><figcaption class="learn-chart__caption">그림 3. 초록은 평균, 파랑은 중앙값입니다. 268과 900은 학습용 대체값이며 7번 거래를 오류로 본 것이 아닙니다.</figcaption></figure>'
        )

    def bars(svg_id, title_id, caption_id, title, desc, labels, widths, shares, result):
        body = [tx(16, 24, title)]
        for index, (label, width, share) in enumerate(zip(labels, widths, shares)):
            y = 48 + index * 52
            body.append(tx(16, y + 18, label))
            body.append(f'<rect data-bar="{index}" x="36" y="{y}" width="{width}" height="24" fill="#93c5fd" stroke="#64748b"/>')
            body.append(tx(36 + width + 8, y + 18, share, f' data-share="{index}"'))
        body.append(tx(16, 168, result))
        return (
            f'<figure class="learn-chart learn-chart--wide mm-chart"><svg id="{svg_id}" viewBox="0 0 640 190" role="img" '
            f'aria-labelledby="{title_id} {caption_id}"><title id="{title_id}">{escape(title)}</title>'
            f'<desc id="{caption_id}">{escape(desc)}</desc>{"".join(body)}</svg>'
        )

    fig4 = bars(
        'mm-weights', 'weights-title', 'weights-desc', '거래 비중과 면적 비중',
        '거래별 평균은 150, 면적가중 평균은 110입니다.',
        ('A 200', 'B 100'), (150, 150), ('50%', '50%'), '거래별 평균 150만원/㎡',
    ) + '<figcaption class="learn-chart__caption">그림 4. A 10㎡·200만원/㎡, B 90㎡·100만원/㎡인 가상 두 거래입니다. 공통 30건이 아닙니다.</figcaption></figure>'
    fig5 = bars(
        'mm-pool', 'pooled-means-title', 'pooled-means-desc', '집단 비중과 거래 비중',
        '두 평균의 단순평균은 150, 건수를 반영한 전체 평균은 190입니다.',
        ('A 100', 'B 200'), (28, 252), ('10%', '90%'), '거래 건수 기준 190만원/㎡',
    ) + '<figcaption class="learn-chart__caption">그림 5. A 10건·평균 100, B 90건·평균 200인 가상 집단입니다. 집단 중앙값의 평균으로 전체 중앙값을 만들지 않습니다.</figcaption></figure>'

    def sec(sid, label, title, inner):
        return (
            f'<section class="learn-chapter__step" id="{sid}" data-toc-label="{escape(label)}">'
            f'<p class="learn-chapter__label">{escape(label)}</p><h2>{escape(title)}</h2>{inner}</section>'
        )

    controls_dots = (
        '<div class="mm-controls" hidden><div class="mm-shortcuts">'
        '<button type="button" data-show="mean" aria-pressed="true">평균 표시</button>'
        '<button type="button" data-show="median" aria-pressed="true">중앙값 표시</button></div>'
        '<p role="status" id="mm-dot-status"></p></div>'
    )
    controls_rank = (
        '<div class="mm-controls" hidden><div class="mm-shortcuts">'
        '<button type="button" data-rank-step="sort">정렬</button>'
        '<button type="button" data-rank-step="center">가운데 위치</button>'
        '<button type="button" data-rank-step="pair">15·16번째</button>'
        '<button type="button" data-rank-step="median" aria-pressed="true">중앙값 122</button></div>'
        '<p role="status" id="mm-rank-status"></p></div>'
    )
    controls_sens = (
        '<div class="mm-controls" hidden><div class="mm-shortcuts">'
        '<button type="button" data-case="268">268</button>'
        '<button type="button" data-case="480" aria-pressed="true">원래 값 480</button>'
        '<button type="button" data-case="900">900</button>'
        '<button type="button" data-case="drop">7번 제외</button></div>'
        '<p role="status" id="mm-sens-status"></p></div>'
    )
    controls_weight = (
        '<div class="mm-controls" hidden><div class="mm-shortcuts">'
        '<button type="button" data-weight="trade" aria-pressed="true">거래별 동일 비중</button>'
        '<button type="button" data-weight="area">면적 비중</button></div>'
        '<p role="status" id="mm-weight-status"></p></div>'
    )
    controls_pool = (
        '<div class="mm-controls" hidden><div class="mm-shortcuts">'
        '<button type="button" data-pool="equal">집단 균등 비중</button>'
        '<button type="button" data-pool="count" aria-pressed="true">거래 건수 비중</button></div>'
        '<p role="status" id="mm-pool-status"></p></div>'
    )
    parts = [
        sec('quick-start', '서두 · 학습목표', '어느 거래가격이 시장의 중심을 나타낼까요?',
            '<p>다섯 건의 단가가 100, 110, 120, 130, 300만원/㎡라고 해 보겠습니다. 모두 더해 5로 나누면 평균은 152만원/㎡입니다. 작은 순서로 놓으면 가운데 값은 120만원/㎡입니다. 같은 자료인데 두 값이 다른 이유는 300이 나머지 네 건보다 크기 때문입니다. 평균은 그 크기를 모두 반영하고, 중앙값은 정렬한 가운데 위치를 찾습니다.</p>'
            '<p>120이 언제나 더 정확한 가격은 아닙니다. 보려는 질문에 따라 평균이 맞을 수도 있고 중앙값이 맞을 수도 있습니다.</p>'
            '<ul class="learn-objectives"><li>산술평균과 중앙값의 차이를 이해합니다.</li><li>같은 자료에서 두 대표값을 계산합니다.</li><li>극단값이 평균과 중앙값에 미치는 영향을 비교합니다.</li><li>값을 바꾸는 것과 관측을 빼는 것을 구별합니다.</li><li>거래별 단가 평균과 면적가중 평균을 구별합니다.</li><li>집단 크기가 다를 때 전체 평균을 계산합니다.</li><li>절사평균과 최빈값의 뜻을 알아봅니다.</li><li>CH2 Macro의 평균·중위 단가를 읽는 방법을 이해합니다.</li></ul>'),
        sec('center', '대표값', '여러 관측을 하나의 숫자로 요약합니다',
            '<p>대표값은 자료의 중심 위치를 나타내는 통계량입니다. 산술평균은 값을 더하고, 중앙값은 정렬한 가운데를 찾고, 최빈값은 가장 자주 나오는 값을 찾습니다.</p>'
            '<p><strong>대표값은 요약한 숫자입니다.</strong> 평균이 150만원/㎡여도 150에 거래된 사례가 없을 수 있고, 그 평균이 특정 토지의 적정가격이 되지는 않습니다.</p>'),
        sec('example', '공통 학습자료', '30건의 단가로 평균과 중앙값을 계산합니다',
            '<p>1~3장의 공통 학습자료 30건에서 이번 장은 거래단가만 사용합니다. 단가 합계는 4,390, 최솟값은 62, 최댓값은 480, 산술평균은 약 146.33, 중앙값은 122입니다. 4,390은 단가를 더한 값이며 거래금액의 합이 아닙니다. 번호는 거래 시점이 아닙니다.</p>'
            '<p>이 자료는 출처와 표집 설계가 확인되지 않은 학습 예제입니다. <a href="/learn/stats/graphs/#data">원자료 표</a>와 <a href="../example-data.json">JSON</a>에서 값을 확인할 수 있습니다.</p>'
            + controls_dots + fig1() +
            '<p>그림에서 평균은 중앙값보다 오른쪽에 있습니다. 480은 다른 점보다 멀리 떨어져 있습니다. 평균 146.33보다 큰 관측은 10건, 작은 관측은 20건입니다. 평균보다 낮다는 말과 하위 50%는 다릅니다.</p>'),
        sec('mean', '산술평균', '모든 관측을 같은 비중으로 더합니다',
            '<p>산술평균은 합을 관측수로 나눈 값입니다. 보통 평균이라고 하면 이 값을 말합니다.</p>'
            '<p>평균 = (x₁+…+xₙ) / n = 4,390 / 30 ≈ 146.33만원/㎡.</p>'
            '<p>이 계산에서 거래 한 건의 비중은 모두 1/30입니다. 면적이 큰 거래와 작은 거래도 한 건으로는 같습니다. 그래서 이번 평균은 거래 건수 기준 단가의 산술평균입니다.</p>'
            '<p>한 건의 단가가 30 늘면 합이 30 늘고 평균은 30/30=1 늘어납니다. 한 건이 300 늘면 평균은 10 늘어납니다. 평균이 큰 값에 움직이는 것은 계산 오류가 아니라 산술평균의 성질입니다.</p>'),
        sec('median', '중앙값', '정렬한 뒤 가운데 위치를 찾습니다',
            '<p>중앙값은 값을 작은 순서로 놓았을 때의 가운데입니다. 표의 중위도 같은 뜻입니다. 홀수 개이면 가운데 한 값을 고릅니다. 10, 20, 30, 40, 100의 중앙값은 30입니다. 짝수 개이면 가운데 두 값의 평균을 씁니다. 10, 20, 30, 40, 50, 100이면 (30+40)/2=35이고, 35는 원자료에 없어도 됩니다.</p>'
            '<p>30건의 가운데는 15번째와 16번째입니다. 정렬하면 120과 124이므로 중앙값은 (120+124)/2=122만원/㎡입니다.</p>'
            + controls_rank + fig2() +
            '<p>같은 값이 반복되면 중앙값보다 엄격히 작은 건수와 엄격히 큰 건수가 정확히 반반이 아닐 수 있습니다. 중앙값은 최솟값과 최댓값의 평균도 아닙니다. (62+480)/2=271이지만 중앙값은 122입니다.</p>'),
        sec('outliers', '극단값', '값을 바꾸는 것과 관측을 빼는 것은 다릅니다',
            '<p>10, 20, 30, 40, 100의 평균은 40, 중앙값은 30입니다. 100을 200으로 바꾸면 평균은 60이 되고 중앙값은 30입니다. 가운데 위치가 그대로이기 때문입니다. 관측을 넣거나 빼서 정렬이 바뀌면 중앙값도 달라질 수 있습니다.</p>'
            '<p>공통 자료에서 나머지 29건은 두고 7번의 480만 바꿉니다. 268과 900은 가상 대체값입니다.</p>'
            '<div class="learn-data learn-data--full mm-table"><table><caption>7번 단가를 바꾸거나 빼면</caption><thead><tr><th scope="col">상태</th><th scope="col">건수</th><th scope="col">합계</th><th scope="col">평균</th><th scope="col">중앙값</th></tr></thead><tbody>'
            '<tr><th scope="row">268로 변경</th><td>30</td><td>4,178</td><td>139.27</td><td>122</td></tr>'
            '<tr><th scope="row">원래 480</th><td>30</td><td>4,390</td><td>146.33</td><td>122</td></tr>'
            '<tr><th scope="row">900으로 변경</th><td>30</td><td>4,810</td><td>160.33</td><td>122</td></tr>'
            '<tr><th scope="row">7번 제외</th><td>29</td><td>3,910</td><td>134.83</td><td>120</td></tr>'
            '</tbody></table></div>'
            + controls_sens + fig3() +
            '<p>480을 900으로 바꾸면 합이 420 늘고 평균은 420/30=14 늘어 약 160.33이 됩니다. 이번 세 값에서는 가운데 120과 124가 그대로라 중앙값은 122입니다. 7번을 빼면 건수가 29가 되어 가운데는 15번째 한 값인 120입니다. 평균은 3,910/29≈134.83입니다.</p>'
            '<p>평균에 영향이 크다고 그 거래를 빼지는 않습니다. 유효한 거래인지, 면적과 금액이 맞는지, 조건이 다른지, 분석 목적에 넣을 거래인지를 먼저 봅니다. 원자료의 오류와 평균에 미치는 영향은 다른 문제입니다.</p>'),
        sec('choice', '어느 대표값인가', '평균과 중앙값은 다른 질문에 답합니다',
            '<p>산술평균은 전체 합의 중심입니다. 중앙값은 정렬한 가운데 위치입니다. 고가 몇 건에 덜 기대고 중간 수준을 보려면 중앙값이 유용할 수 있습니다. 서로 다른 유형이 섞여 있으면 중앙값도 한 시장의 전형적인 가격이라고 보기 어렵습니다. 평균, 중앙값, 거래 건수, 분포를 함께 봅니다.</p>'),
        sec('weighted', '가중평균', '거래 한 건과 면적 1㎡는 비중이 다릅니다',
            '<p>가중평균은 (가중치×값)의 합을 가중치의 합으로 나눕니다. 가중치는 음수가 아니고 합은 0보다 커야 합니다. 가중치가 모두 같으면 산술평균과 같습니다.</p>'
            '<div class="learn-data learn-data--full mm-table"><table><caption>가상 거래 두 건</caption><thead><tr><th scope="col">거래</th><th scope="col">면적</th><th scope="col">단가</th><th scope="col">금액</th></tr></thead><tbody>'
            '<tr><th scope="row">A</th><td>10㎡</td><td>200</td><td>2,000만원</td></tr>'
            '<tr><th scope="row">B</th><td>90㎡</td><td>100</td><td>9,000만원</td></tr>'
            '<tr><th scope="row">합계</th><td>100㎡</td><td></td><td>11,000만원</td></tr>'
            '</tbody></table></div>'
            '<p>거래별 평균은 (200+100)/2=150입니다. 면적가중 평균은 (10×200+90×100)/(10+90)=110이고, 11,000/100과도 같습니다.</p>'
            + controls_weight + fig4 +
            '<p>거래별 평균은 A와 B를 50%씩 반영합니다. 면적가중 평균은 A 10%, B 90%입니다. 어느 계산이 틀린 것은 아니고, 같은 비중을 주는 대상이 다릅니다. 평균단가라는 이름만으로는 가중치를 알 수 없습니다.</p>'
            '<p>면적가중 단가는 각 거래의 금액과 면적이 서로 대응할 때 성립합니다. 집합건물의 거래금액과 전용면적, 토지 거래금액과 토지면적은 단위가 만원/㎡로 같아도 측정 대상이 다를 수 있습니다.</p>'),
        sec('group-means', '평균의 평균', '건수가 많은 집단이 전체 평균에 더 들어갑니다',
            '<p>A는 10건·평균 100, B는 90건·평균 200이고 서로 겹치지 않으며 단가의 정의가 같다고 하겠습니다. 두 평균을 더해 2로 나누면 150입니다. 이것은 집단에 같은 비중을 준 값입니다. 거래 한 건에 같은 비중을 주면 (10×100+90×200)/100=190입니다.</p>'
            + controls_pool + fig5 +
            '<p>집단 평균과 관측수를 알면 전체 평균은 (n₁x̄₁+n₂x̄₂)/(n₁+n₂)로 합칠 수 있습니다. 중앙값은 다릅니다. 집단별 중앙값과 건수만으로는 전체를 정렬한 가운데가 정해지지 않습니다. 읍면동 중앙값을 평균해 시군구 중앙값으로 쓰지 않습니다. 원자료를 합친 뒤 다시 중앙값을 구합니다.</p>'),
        sec('composition', '거래 구성', '집단 가격이 그대로여도 전체 평균은 달라질 수 있습니다',
            '<p>A 평균 100, B 평균 200이 두 기간 모두 같다고 하겠습니다. 첫 기간이 A 90건·B 10건이면 전체 평균은 110입니다. 다음 기간이 A 10건·B 90건이면 전체 평균은 190입니다. 달라진 것은 거래 구성입니다.</p>'
            '<p>전체 평균이 올랐다고 같은 부동산의 가격이 올랐다고 보지는 않습니다. 구성이 바뀌었다고 가격 변화가 없었다고 단정하지도 않습니다. 기간을 비교할 때는 구성과 가격 수준을 함께 봅니다.</p>'),
        sec('more-centers', '다른 대표값', '절사평균, 최빈값, 최소화하는 오차',
            '<p>10% 절사평균은 정렬한 뒤 작은 쪽과 큰 쪽에서 각각 10%를 빼고 남은 값의 평균을 구합니다. 빼는 비율은 미리 정합니다. 결과를 맞추려고 특정 거래만 지우는 것과는 다릅니다.</p>'
            '<p>최빈값은 가장 자주 나오는 값입니다. 100, 100, 120, 150, 200의 최빈값은 100입니다. 여러 개일 수도 있고, 단가가 모두 다르면 하나의 최빈값이 없을 수 있습니다. 히스토그램에서 가장 높은 구간은 개별 값의 최빈값과 다르며, 구간 폭에 따라 달라질 수 있습니다.</p>'
            '<details class="learn-more"><summary>평균과 중앙값이 최소화하는 오차</summary><div class="learn-more__body"><p>어떤 수 c와 각 관측의 차이를 제곱해 모두 더하면, 그 합이 가장 작아지는 c는 산술평균입니다. 차이의 절댓값을 모두 더하면, 그 합이 가장 작아지는 c는 중앙값입니다. 짝수 개이고 가운데 두 값이 다르면 그 두 값 사이의 모든 c가 절대오차 합을 최소화합니다. 통계에서는 보통 그 두 값의 평균을 중앙값으로 적습니다.</p><p>제곱오차의 중심은 평균이고, 절대오차의 중심은 중앙값입니다. 이후 예측오차에서 MAE와 RMSE가 다른 모형을 고를 수 있는 이유와 이어집니다.</p></div></details>'
            '<p>자료 100, 100, 100과 0, 100, 200은 평균과 중앙값이 모두 100입니다. 퍼짐은 다릅니다. 최솟값, 최댓값, 분위수, 분산, 히스토그램, 상자그림이 더 필요합니다. 5장과 6장에서 위치와 퍼짐을 이어서 봅니다.</p>'),
        sec('practice', '확인 문제', '계산 기준을 구별해 보세요',
            '<ol class="learn-exercises">'
            '<li>7번의 단가를 480에서 780으로 바꾸면 평균과 중앙값은 어떻게 될까요?<details><summary>답과 해설</summary><p>단가가 300 늘어 합계는 4,690, 평균은 4,690/30≈156.33입니다. 기존 평균보다 10 큽니다. 가운데 120과 124는 그대로이므로 중앙값은 122입니다.</p></details></li>'
            '<li>A 10건의 평균이 100이고 B 90건의 평균이 200입니다. 전체 평균을 150으로 계산해도 될까요?<details><summary>답과 해설</summary><p>거래 100건의 평균이라면 그렇지 않습니다. (10×100+90×200)/100=190입니다. 150은 두 집단 평균에 50%씩 준 값입니다.</p></details></li>'
            '<li>거래별 평균이 150이고 면적가중 평균이 110이면 하나가 틀린 계산일까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 거래별 평균은 거래 한 건을, 면적가중 평균은 면적 1㎡를 같은 비중으로 봅니다.</p></details></li>'
            '<li>중앙값이 100인 두 지역은 가격 분포도 비슷할까요?<details><summary>답과 해설</summary><p>반드시 그렇지는 않습니다. 퍼짐, 분위수, 극단값, 거래 건수가 다를 수 있습니다.</p></details></li>'
            '<li>단가 480이 평균에 크게 영향을 주면 그 거래를 빼는 것이 좋을까요?<details><summary>답과 해설</summary><p>영향이 크다는 이유만으로 빼지는 않습니다. 거래의 유효성, 면적과 금액, 특수 조건, 분석 목적에 포함되는지를 먼저 확인합니다.</p></details></li>'
            '</ol>'),
        sec('macro', 'CH2 Macro에서 읽기', '평균 33.2와 중위 26.0은 어떻게 읽을까요?',
            '<p>토지 기본통계에서는 지역, 기간, 용도지역, 지목별로 단가를 요약합니다. 아래는 자녹과 답이 만나는 칸의 과거 화면입니다.</p>'
            '<figure class="learn-capture learn-capture--detail"><a href="../assets/captures/land-mean-median-cell.png" target="_blank" rel="noopener"><img src="../assets/captures/land-mean-median-cell.png" width="251" height="180" loading="lazy" alt="CH2 Macro 토지 기본통계 일부. 용도지역 자녹과 지목 답이 만나는 칸에 평균 33.2와 중앙값 26.0이 표시되어 있습니다."/></a>'
            '<figcaption class="learn-capture__caption">자녹·답 칸의 평균 33.2만원/㎡, 중위 26.0만원/㎡입니다. 차이는 7.2입니다. 캡처 당시의 값이며 공통 30건이나 현재 운영 통계가 아닙니다.</figcaption></figure>'
            '<p>평균 33.2와 중위 26.0은 같은 조건의 거래를 다른 방법으로 요약한 값입니다. 차이가 7.2라고 고가 거래의 건수나 이상치 여부가 정해지지는 않습니다. 그 조건의 모든 토지가 26만원/㎡에 거래된다는 뜻도 아닙니다.</p>'
            '<p>확인한 토지 기본통계에서 매트릭스 칸의 평균은 그 조건에 들어온 거래단가의 산술평균입니다. 거래 한 건이 같은 비중입니다. 연도별 표의 단가는 거래금액 합을 면적 합으로 나눈 값입니다. 중위는 그 단가 목록의 중앙값입니다. 칸마다 같은 산식이라고 단정하지 않으려면 표의 이름을 함께 봅니다. 읍면동 중위를 평균해 시군구 중위로 쓰지 않습니다.</p>'
            '<ol class="learn-screen-reading"><li><strong>건수:</strong> 5건과 500건의 대표값은 안정성이 다릅니다.</li>'
            '<li><strong>산식:</strong> 거래별 평균인지 면적가중 평균인지 확인합니다.</li>'
            '<li><strong>조건:</strong> 같은 자녹·답이어도 면적, 도로, 이용상황, 시점이 다를 수 있습니다.</li>'
            '<li><strong>기간:</strong> 3년·5년·7년 평균이 달라도 구성이 바뀐 결과일 수 있습니다. 기간은 서로 겹칩니다.</li>'
            '<li><strong>차이:</strong> 평균이 중위보다 높으면 큰 단가의 영향을 분포와 거래 목록에서 살펴봅니다.</li></ol>'
            '<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p>'),
        sec('recap', '결론 · 학습 요약', '평균은 값의 크기를, 중앙값은 가운데 위치를 반영합니다',
            '<ul class="learn-recap-list">'
            '<li><strong>산술평균:</strong> 합을 건수로 나눕니다.</li>'
            '<li><strong>중앙값:</strong> 정렬한 가운데입니다. 짝수 개이면 가운데 두 값의 평균입니다.</li>'
            '<li><strong>극단값:</strong> 평균은 크기에 민감하고, 중앙값은 그보다 덜 민감합니다. 관측을 빼면 둘 다 다시 계산합니다.</li>'
            '<li><strong>가중평균:</strong> 거래 한 건과 면적 1㎡는 다른 질문입니다.</li>'
            '<li><strong>집단 평균:</strong> 전체 평균에는 건수가 들어갑니다. 중앙값은 집단 중앙값만으로 합치지 않습니다.</li>'
            '<li><strong>구성:</strong> 유형의 비중이 바뀌어도 전체 평균은 달라질 수 있습니다.</li>'
            '</ul>'
            '<p>다음 <a href="/learn/stats/quantiles/">5장 「분위수와 상자그림」</a>에서는 Q1·Q3·IQR로 분포의 위치를 더 나눕니다.</p>'
            '<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul>'
            '<li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda351.htm">NIST/SEMATECH e-Handbook: Measures of Location</a></li>'
            '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/2-5-measures-of-the-center-of-the-data">OpenStax, Introductory Statistics 2e §2.5</a></li>'
            '</ul><p class="learn-source-note">참고자료 확인일: 2026-10-07. 그림 1·2·3은 공통 학습자료이고 그림 4·5는 별도 가상 예제입니다. 화면의 33.2와 26.0은 캡처 당시의 값입니다.</p></div></details>'),
    ]
    html = f'''<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>04. 평균과 중앙값 | 통계학 &amp; 데이터 분석</title>
    <meta name="description" content="산술평균과 중앙값, 극단값의 영향, 면적가중 평균과 집단 평균을 같은 자료와 가상 예제로 비교합니다." />
    <link rel="canonical" href="https://ch2data.com/learn/stats/mean-and-median/" />
    <script src="/learn/stats/learn-stats-theme.js?v=20261023-1"></script>
    <link rel="stylesheet" href="/style.css" />
    <link rel="stylesheet" href="/learn/stats/learn-stats.css?v=20261023-1" />
    <link rel="stylesheet" href="/learn/stats/learn-reader.css?v=20261026-toc" />
    <link rel="stylesheet" href="/learn/stats/mean-and-median/chapter.css?v=20261026-9" />
  </head>
  <body>
    <div class="page">
      <header class="hero hero--document">
        <p class="learn-breadcrumb"><a href="https://ch2data.com/">CH2 DATA</a> · <a href="/learn/stats/">통계학 &amp; 데이터 분석</a></p>
        <p class="hero__eyebrow">I. 데이터와 기술통계</p>
        <h1 class="hero__title">04. 평균과 중앙값</h1>
        <p class="learn-chapter-relevance">Macro 활용도 <span class="learn-relevance" aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span></span></p>
        <p class="learn-relevance-guide">Macro 활용도: ★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화<br>별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.</p>
      </header>
      <article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="평균과 중앙값">{''.join(parts)}</article>
      <nav class="learn-chapter-nav" aria-label="장 이동">
        <a href="/learn/stats/graphs/">← 03. 그래프로 보는 데이터와 분포</a>
        <a href="/learn/stats/quantiles/">05. 분위수와 상자그림 →</a>
      </nav>
      <footer class="footer"><nav class="footer__links"><a href="https://ch2data.com/">홈</a><a href="/learn/stats/">통계학 &amp; 데이터 분석</a></nav><p>© CH2 DATA</p></footer>
    </div>
    <script src="/learn/stats/learn-stats-toc.js?v=20261026-9" defer></script>
    <script type="application/json" id="mm-data">{json.dumps(page_data, ensure_ascii=False)}</script>
    <script type="module" src="/learn/stats/mean-and-median/experiment.js?v=20261026-9"></script>
  </body>
</html>
'''
    ids = re.findall(r'\sid="([^"]+)"', html)
    if len(ids) != len(set(ids)):
        raise SystemExit(f'duplicate ids: {sorted({item for item in ids if ids.count(item) > 1})}')
    charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', html, re.S)]
    assert len(charts) == 5
    dot = next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('two-centers'))
    points = [node for node in dot.findall('circle') if 'data-observation' in node.attrib]
    assert len(points) == 30
    for point in points:
        row = next(item for item in rows if item['id'] == int(point.attrib['data-observation']))
        assert float(point.attrib['cx']) == 60 + row['price']
    sensitivity = next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('sensitivity'))
    for point in sensitivity.findall('circle'):
        replacement = int(point.attrib['data-replacement'])
        key = point.attrib['data-series']
        actual = mean(other + [replacement]) if key == 'mean' else median(other + [replacement])
        assert abs(float(point.attrib['data-value']) - actual) < 1e-8
        assert abs(float(point.attrib['cx']) - (75 + (replacement - 268) * 0.75)) < 1e-8
        assert abs(float(point.attrib['cy']) - (265 - (actual - 100) * 2.3)) < 1e-8
    exercises = html.split('<ol class="learn-exercises">')[1].split('</ol>')[0]
    assert exercises.count('<summary>답과 해설</summary>') == 5 and ' open' not in exercises
    assert 'id="mean"' in html and 'id="median"' in html
    assert '[그림 ' not in html and '★☆☆ 심화' in html and '3단계, 핵심' in html
    assert 'land-mean-median-cell.png' in html
    (ROOT / 'mean-and-median' / 'index.html').write_text(html, encoding='utf-8')
    print('chapter 4 rebuilt', round(mean(prices), 2), median(prices))


if __name__ == '__main__':
    build()
