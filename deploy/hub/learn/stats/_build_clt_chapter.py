"""Chapter 10: exact sampling distributions of a fictional Bernoulli mean."""
from pathlib import Path
from html import escape
import json
import math
import re
import xml.etree.ElementTree as ET

from _build_distributions_chapter import binomial

ROOT = Path(__file__).resolve().parent
ROW_SIZES = [1, 5, 30, 100]
ERROR_SIZES = [1, 4, 16, 64]
TABLE_SIZES = [5, 25, 100, 400]


def build():
    distributions = [{'n': n, 'probabilities': binomial(n, .2)} for n in ROW_SIZES]
    five = distributions[1]['probabilities']
    expected = [.32768, .4096, .2048, .0512, .0064, .00032]
    assert all(abs(a - b) < 1e-12 for a, b in zip(five, expected))
    assert abs(sum(five) - 1) < 1e-12
    assert abs(sum(k / 5 * p for k, p in enumerate(five)) - .2) < 1e-12
    assert abs(sum((k / 5 - .2) ** 2 * p for k, p in enumerate(five)) - .032) < 1e-12
    assert abs(.4 / math.sqrt(5) - 0.17888543819998318) < 1e-12
    for n in TABLE_SIZES + ERROR_SIZES:
        assert abs((.4 / math.sqrt(n)) ** 2 - .16 / n) < 1e-12
    exact = sum(binomial(100, .2)[15:26])
    corrected = math.erf(1.375 / math.sqrt(2))
    plain = math.erf(1.25 / math.sqrt(2))
    assert f'{exact:.4f}' == '0.8321' and f'{corrected:.4f}' == '0.8309'
    assert abs(exact - corrected) < .01
    assert math.sqrt((100 - 100) / 99) == 0 and math.sqrt((100 - 1) / 99) == 1

    data = {
        'description': '가상 독립 베르누이 모형 p=0.2의 정확한 표본평균 분포. 모의실험 빈도가 아니고 CH2 Macro 거래자료도 아닙니다.',
        'p': .2,
        'distributions': distributions,
    }
    (ROOT / 'sampling-distributions-example.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )

    def t(x, y, text, extra=''):
        return f'<text x="{x}" y="{y}" {extra}>{escape(str(text))}</text>'

    def axis(x, y, xx, yy, extra=''):
        return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#64748b" {extra}/>'

    def fig(fig_id, title, body, caption, height, html_id):
        return (
            f'<figure class="learn-chart learn-chart--wide cl-chart" id="{html_id}">'
            f'<svg viewBox="0 0 640 {height}" role="img" aria-labelledby="{fig_id}-title {fig_id}-desc">'
            f'<title id="{fig_id}-title">{title}</title><desc id="{fig_id}-desc">{caption}</desc>{body}</svg>'
            f'<figcaption class="learn-chart__caption">{caption}</figcaption></figure>'
        )

    body = t(24, 28, '같은 n=5로 반복 추출하고, 매번 평균 하나를 남깁니다')
    for i, values in enumerate([[0, 0, 0, 0, 0], [0, 1, 0, 0, 0], [1, 0, 1, 0, 0]]):
        y = 85 + i * 65
        body += (
            t(24, y, f'표본 {i + 1}')
            + t(130, y, ' · '.join(map(str, values)))
            + t(350, y, '→')
            + t(400, y, f'평균 {sum(values) / 5:.1f}')
        )
    body += t(24, 293, '각 표본 안의 값 5개 ≠ 반복해서 모은 평균 3개')
    figure1 = fig(
        'repeated', '표본과 표본평균', body,
        '그림 1. 반복 추출의 구조를 설명하는 가상 세 표본입니다. 실제 시뮬레이션 결과나 같은 확률로 나타나는 대표 표본이 아닙니다. 반복마다 n=5를 유지합니다.',
        320, 'cl-fig1',
    )

    body = t(24, 26, '원자료는 계속 0 또는 1, 평균의 분포만 달라집니다')
    for i, item in enumerate(distributions):
        n = item['n']
        base = 140 + i * 140
        body += t(200, base - 90, f'n={n} · 평균 0.20 · SE={.4 / math.sqrt(n):.3f}') + axis(70, base, 570, base)
        for k, p in enumerate(item['probabilities']):
            x = 70 + 500 * k / n
            body += axis(x, base, x, base - 100 * p / .8, f'stroke-width="3" data-n="{n}" data-k="{k}" data-probability="{p}"')
        for value in [0, .2, .4, .6, .8, 1]:
            body += t(70 + 500 * value, base + 23, f'{value:.1f}', 'text-anchor="middle"')
    body += t(24, 605, '공통 세로축: 확률 0~0.8 / 공통 가로축: 표본평균')
    figure2 = fig(
        'exact', '표본수별 정확한 표본평균 분포', body,
        '그림 2. p=0.2인 독립 베르누이 시행. 막대 위치 k/n과 높이 P(K=k)를 이항공식으로 계산했습니다. 각 줄의 확률 합은 1이며 n이 커져도 유한 n에서는 이산분포입니다.',
        636, 'cl-fig2',
    )

    body = t(24, 28, '표준오차를 절반으로 줄이려면 n을 네 배로 늘립니다')
    for i, n in enumerate(ERROR_SIZES):
        y = 75 + i * 65
        se = .4 / math.sqrt(n)
        body += (
            t(24, y + 19, f'n={n}')
            + f'<rect x="145" y="{y}" width="{se * 900}" height="25" fill="#2563eb" data-n="{n}" data-se="{se}"/>'
            + t(155 + se * 900, y + 19, f'{se:.2f}')
        )
    body += t(24, 367, '개별 X의 표준편차 σ=0.40은 그대로입니다')
    figure3 = fig(
        'se', '표본수와 표준오차', body,
        '그림 3. 같은 가상 모집단에서 SE=0.4/√n입니다. 표준오차는 표본평균의 퍼짐이며 개별 관측값의 표준편차와 다릅니다. 막대의 표본수는 1, 4, 16, 64입니다.',
        392, 'cl-fig3',
    )

    body = t(24, 28, '표본평균을 표준화해 모양을 비교합니다')
    for i, n in enumerate([5, 100]):
        base = 215 + i * 220
        body += t(24, base - 150, f'n={n} · Z=(평균−0.2)/(0.4/√n)') + axis(60, base, 580, base)
        step = 1 / (n * (.4 / math.sqrt(n)))
        for k, p in enumerate(binomial(n, .2)):
            z = (k / n - .2) / (.4 / math.sqrt(n))
            if -4 <= z <= 4:
                x = 320 + z * 60
                body += axis(
                    x, base, x, base - p / step * 270,
                    f'stroke-width="3" data-n="{n}" data-k="{k}"',
                )
        points = [
            (320 + z * 60, base - math.exp(-z * z / 2) / math.sqrt(2 * math.pi) * 270)
            for z in [-4 + j * .04 for j in range(201)]
        ]
        body += '<polyline points="' + ' '.join(f'{x:.4f},{y:.4f}' for x, y in points) + '" fill="none" stroke="#d97706" stroke-width="2"/>'
        for z in [-4, -2, 0, 2, 4]:
            body += t(320 + z * 60, base + 24, z, 'text-anchor="middle"')
    body += t(24, 503, '선: 표준정규 밀도 / 막대 높이: 확률÷격자 간격')
    figure4 = fig(
        'standardized', '표준화한 표본평균과 정규 근사', body,
        '그림 4. 막대 높이는 확률질량을 z값의 간격으로 나눈 밀도 환산값입니다. 주황선은 표준정규 밀도입니다. 높이 자체가 한 점의 확률은 아니며 −4~4 구간만 표시했습니다.',
        533, 'cl-fig4',
    )

    def row(cells, tag='td'):
        return '<tr>' + ''.join(f'<{tag}>{cell}</{tag}>' for cell in cells) + '</tr>'

    probability_rows = ''.join(
        row([str(k), f'{k / 5:.1f}', f'{p:.5f}']) for k, p in enumerate(five)
    ) + row(['합계', '', '1.00000'])
    se_rows = ''.join(
        row([
            str(n), '0.4', trim(.16 / n),
            '약 0.1789' if n == 5 else trim(.4 / math.sqrt(n)),
        ]) for n in TABLE_SIZES
    )
    parts = []

    def sec(sec_id, label, title, content):
        parts.append(
            f'<section class="learn-chapter__step" id="{sec_id}" data-toc-label="{label}">'
            f'<p class="learn-chapter__label">{label}</p><h2>{title}</h2>{content}</section>'
        )

    sec('quick-start', '서두 · 학습목표', '같은 지역에서 평균을 여러 번 구하면 모두 같을까요?',
        '<p>어느 지역의 토지 거래 30건을 골라 평균단가가 150만원/㎡로 나왔다고 가정하겠습니다. 다른 30건을 고르면 140만원/㎡나 160만원/㎡가 될 수도 있습니다. 선택된 거래가 달라지면 평균도 달라질 수 있습니다.</p>'
        '<p>표본을 같은 방법으로 반복해서 고를 때 평균이 어떤 값들을 가질 수 있는지를 <strong>표본분포</strong>라고 합니다. 9장에서는 개별 확률변수의 분포를 보았습니다. 이번 장에서는 여러 관측으로 계산한 <strong>표본평균 자체</strong>를 하나의 확률변수로 다룹니다.</p>'
        '<ul class="learn-objectives">'
        '<li>모집단 분포, 한 표본의 경험분포, 표본평균의 표본분포를 구별합니다.</li>'
        '<li>표본수 n과 모의실험 반복 횟수 B의 차이를 이해합니다.</li>'
        '<li>표본평균의 기대값, 분산, 표준오차를 계산합니다.</li>'
        '<li>중심극한정리의 조건과 정규근사, 연속성 보정을 이해합니다.</li>'
        '<li>큰 표본도 편향과 관측 간 의존성을 없애지 못하는 이유를 이해합니다.</li>'
        '</ul>')
    sec('three-distributions', '세 가지 분포', '같은 분포라는 말이라도 대상이 다릅니다',
        '<div class="cl-table"><table><thead><tr><th>구분</th><th>분석 대상</th><th>질문</th></tr></thead><tbody>'
        + row(['모집단 분포', '전체 대상의 개별 값', '거래단가 자체가 얼마나 다양할까요?'], 'th')
        + row(['한 표본의 경험분포', '선택한 n개 값', '이번에 본 거래는 어떻게 퍼져 있을까요?'], 'th')
        + row(['표본평균의 표본분포', '반복해서 구한 평균들', '다시 뽑으면 평균이 얼마나 달라질까요?'], 'th')
        + '</tbody></table></div>'
        '<p>이번 장에서 집중할 대상은 세 번째입니다. 첫 번째는 목표 모집단의 개별 값이고, 두 번째는 지금 손에 있는 n개 값의 히스토그램입니다.</p>')
    sec('statistic', '표본분포', '통계량도 표본에 따라 달라지는 확률변수입니다',
        '<p>표본에서 계산한 평균, 비율, 중앙값을 <strong>통계량</strong>이라고 합니다. 표본평균은 X̄=(X₁+…+Xₙ)/n입니다. 표본을 고르기 전에는 각 Xᵢ와 평균이 확률변수이고, 한 번 고르면 평균은 하나의 숫자가 됩니다. 다시 고르면 그 숫자가 달라질 수 있습니다.</p>'
        '<p>가능한 표본평균과 그 확률이 표본평균의 표본분포입니다. 이 분포는 조사를 수천 번 해야만 정의되는 것이 아닙니다. 반복 표집은 이해하기 위한 사고실험이고, 확률모형을 알면 분포를 식으로 계산할 수도 있습니다.</p>')
    sec('repeated', '표본수와 반복 횟수', '한 번에 다섯 개씩 고르고 평균 하나를 남깁니다',
        '<div class="cl-controls" id="cl-fig1-controls" hidden><p>표본수 n은 한 표본 안의 관측수이고, 반복 횟수 B는 그 표본을 몇 번 모의로 골랐는지입니다.</p>'
        '<div class="cl-shortcuts" role="group" aria-label="반복 횟수"><button type="button" data-b="1000" aria-pressed="true">n=5, B=1,000</button><button type="button" data-b="10000" aria-pressed="false">n=5, B=10,000</button></div>'
        '<p id="cl-repeat-status" role="status"></p></div>'
        + figure1 +
        '<p>그림의 세 표본은 구조를 보여주는 개념도입니다. 특정 모집단에서 실제로 뽑아 얻은 결과로 읽지 않습니다. B를 1,000에서 10,000으로 늘리면 시뮬레이션으로 그린 분포가 이론 분포에 더 가깝게 보일 수 있습니다. 한 표본의 관측수는 둘 다 5개이므로, 표본평균의 이론적 표준오차는 B 때문에 작아지지 않습니다.</p>'
        '<p>한 번에 100개씩 고르면 조건이 맞을 때 평균의 변동이 작아질 수 있습니다. <strong>n을 키우는 것</strong>은 한 표본의 정보량을 바꾸고, <strong>B를 키우는 것</strong>은 같은 크기의 표본을 모의로 더 많이 관찰하는 일입니다.</p>')
    sec('bernoulli', '계산 예제', '0과 1의 평균은 이번 예제에서 참여 비율입니다',
        '<p>독서 동아리 참여 비율이 20%인 학교를 가정합니다. 학생 한 명을 뽑아 참여하면 1, 아니면 0으로 적고 명단에 다시 넣습니다. 매번 같은 명단에서 독립적으로 고르므로 참여 확률은 0.2입니다. 이 모형은 9장과 이어지는 학습용 모형이며, 토지 거래단가의 분포가 아닙니다.</p>'
        '<div class="cl-table"><table><thead><tr><th>X</th><th>확률</th></tr></thead><tbody>'
        + row(['0', '0.8']) + row(['1', '0.2']) + '</tbody></table></div>'
        '<p>개별 X의 기대값은 μ=0.2, 분산은 0.2×0.8=0.16, 표준편차는 σ=√0.16=0.4입니다. 0.4는 0·1 관측값 하나의 표준편차입니다.</p>'
        '<p>다섯 번 독립적으로 고를 때 참여 횟수 K는 Bin(5, 0.2)를 따릅니다. 표본평균은 X̄=K/5이므로 가능한 값은 0, 0.2, 0.4, 0.6, 0.8, 1.0입니다. 참여자가 한 번이면 평균은 1/5=0.2이고, 세 번이면 3/5=0.6입니다.</p>'
        '<div class="cl-table"><table><thead><tr><th>참여 횟수 K</th><th>표본평균</th><th>확률</th></tr></thead><tbody>'
        + probability_rows + '</tbody></table></div>'
        '<p>P(K=1)=C(5, 1)×0.2×0.8⁴=5×0.2×0.4096=0.4096입니다. 따라서 표본평균이 0.2일 확률은 40.96%입니다. P(K=2)=10×0.2²×0.8³=0.2048입니다. 이 표는 시뮬레이션 빈도가 아니라 이항공식의 정확한 확률입니다.</p>'
        '<p>이번 평균은 0과 1의 산술평균이면서 표본의 참여 비율입니다. 거래단가의 평균이 어떤 사건의 발생 비율이라는 뜻은 아닙니다.</p>')
    sec('pmf', '정확한 표본분포', '표본수를 늘리면 평균의 분포가 0.2 근처에 모입니다',
        '<div class="cl-controls" id="cl-fig2-controls" hidden><p>네 표본수는 같은 p=0.2 모형입니다. 고른 줄의 막대를 강조합니다. 나머지 줄은 비교용으로 남습니다.</p>'
        '<div class="cl-shortcuts" role="group" aria-label="정확한 분포의 표본수">'
        + ''.join(
            f'<button type="button" data-n-choice="{n}" aria-pressed="{"true" if n == 5 else "false"}">n={n}</button>'
            for n in ROW_SIZES
        ) + '</div><p id="cl-pmf-status" role="status"></p></div>'
        + figure2 +
        '<p>n이 커져도 개별 X는 0 또는 1입니다. 0.3이나 0.7은 여러 값을 평균했을 때 나타날 수 있는 표본평균입니다. 유한한 n에서 평균은 k/n만 가지므로 정확한 분포는 이산분포입니다. 간격이 좁아져 곡선처럼 보여도 연속분포로 바뀐 것은 아닙니다.</p>'
        '<p>n=5에서는 가능한 평균이 6개이고, n=100에서는 101개입니다. 확률의 합 1이 더 많은 값에 나뉘므로, 가장 높은 막대가 낮아져도 분포가 더 넓어진 것은 아닙니다. 퍼짐은 표준오차와 값이 모인 범위로 봅니다. 그림 2의 세로축은 확률이고, 그림 4의 세로축은 밀도로 환산한 높이입니다.</p>'
        '<details class="learn-more"><summary>0.15~0.25 구간의 정확한 확률</summary><div class="learn-more__body"><p id="cl-band-note">표본수를 고르면 이 구간에 들어가는 k/n의 확률을 더합니다.</p>'
        '<p>하한과 상한을 포함합니다. n=100이면 15≤K≤25이고, 정확한 확률은 <strong>0.8321</strong>입니다.</p></div></details>'
        '<p>확률은 <a href="../sampling-distributions-example.json">이항공식으로 계산한 표</a>와 같습니다. 막대 높이를 모의실험 빈도로 바꾸지 않았습니다.</p>')
    sec('moments', '기대값·분산·표준오차', '평균의 중심은 0.2이고 퍼짐은 n이 커질수록 줄어듭니다',
        '<p>각 관측의 기대값이 μ이면 E[X̄]=(nμ)/n=μ입니다. 이 관계에는 독립이 필요하지 않습니다. 이번 모형에서는 n이 5이든 25이든 100이든 표본평균의 기대값은 0.2입니다. 매번 평균이 정확히 0.2가 된다는 뜻은 아닙니다. 반복해서 고른 평균들의 중심이 0.2라는 뜻입니다. 표집 방법이 편향되면 목표 모집단의 평균을 이렇게 추정한다고 보장할 수 없습니다.</p>'
        '<p>관측이 서로 독립이고 분산이 모두 σ²이면 Var(X̄)=σ²/n입니다. 합의 분산이 nσ²이고, 그 합을 n으로 나누면 분산은 n²으로 나뉩니다. 표준오차는 그 분산의 제곱근입니다.</p>'
        '<p><strong>SE(X̄)=σ/√n</strong></p>'
        '<div class="cl-table"><table><thead><tr><th>구분</th><th>표준편차 SD</th><th>표준오차 SE</th></tr></thead><tbody>'
        + row(['대상', '개별 관측값', '표본평균'])
        + row(['이번 예제', '0.4', '0.4/√n'])
        + row(['n이 커지면', '모집단 SD는 그대로', '조건이 맞으면 감소'])
        + '</tbody></table></div>'
        '<div class="cl-controls" id="cl-fig3-controls" hidden><p>그림 3의 막대는 n=1, 4, 16, 64입니다. 그림 2의 표본수와 다릅니다.</p>'
        '<div class="cl-shortcuts" role="group" aria-label="표준오차 그림의 표본수">'
        + ''.join(
            f'<button type="button" data-se-choice="{n}" aria-pressed="{"true" if n == 4 else "false"}">n={n}</button>'
            for n in ERROR_SIZES
        ) + '</div><p id="cl-se-status" role="status"></p></div>'
        + figure3 +
        '<div class="cl-table"><table><thead><tr><th>표본수 n</th><th>개별 SD</th><th>평균의 분산</th><th>표준오차</th></tr></thead><tbody>'
        + se_rows + '</tbody></table></div>'
        '<p>n=25이면 SE=0.4/5=0.08이고, n=100이면 SE=0.4/10=0.04입니다. 표본수가 네 배가 되면 같은 독립표집 조건에서 이론적 표준오차는 절반이 됩니다. 표준오차를 10분의 1로 줄이려면 표본수는 100배가 필요합니다. 개별 거래의 가격 차이와 평균 추정의 불확실성은 다른 대상입니다.</p>'
        '<details class="learn-more"><summary>분산 공식이 성립하는 조건</summary><div class="learn-more__body"><p>기대값 μ에는 각 관측의 기대값이 μ라는 조건이 쓰입니다. σ²/n에는 독립과 같은 분산이 추가로 쓰입니다. 두 공식 모두 원자료가 정규분포라는 가정을 요구하지 않습니다. 관련된 거래를 독립이라고 두면 불확실성을 작게 볼 수 있습니다.</p></div></details>')
    sec('clt', '중심극한정리', '정규분포에 가까워지는 것은 표준화한 표본평균입니다',
        '<p>개별 X는 0과 1뿐이라 정규분포가 아닙니다. 그래도 독립·동일분포이고 평균과 분산이 유한하며 분산이 양수이면, n이 커질 때 Zₙ=(X̄−μ)/(σ/√n)의 분포는 표준정규분포에 가까워집니다. 이번 모형에서는 μ=0.2이고 SE=0.4/√n입니다. n=100에서 평균이 0.28이면 z=(0.28−0.20)/0.04=2입니다.</p>'
        '<div class="cl-controls" id="cl-fig4-controls" hidden><p>그림 4는 n=5와 n=100만 그립니다. 그림 2에서 이 둘을 고르면 같은 표본수가 강조됩니다.</p>'
        '<div class="cl-shortcuts" role="group" aria-label="표준화 그림의 표본수"><button type="button" data-n-choice="5" aria-pressed="true">n=5</button><button type="button" data-n-choice="100" aria-pressed="false">n=100</button></div>'
        '<p id="cl-z-status" role="status"></p></div>'
        + figure4 +
        '<p>표준화는 서로 다른 n의 모양을 같은 척도에서 비교하기 위한 변환입니다. 유한한 n의 정확한 분포는 여전히 이산분포입니다. 표준정규밀도는 φ(z)=exp(−z²/2)/√(2π)입니다. 막대 높이 P(K=k)/Δz에서 Δz=1/√(0.16n)입니다. 그림 2의 막대 높이와 단위가 다릅니다.</p>'
        '<p>n=30은 모든 자료에서 정규근사를 보장하는 경계가 아닙니다. 원자료가 정규분포이고 독립이면 표본평균은 작은 n에서도 정확히 정규분포입니다. 치우침이 크거나 드문 사건을 보면 더 많은 표본이 필요할 수 있고, 꼬리 확률은 중심부보다 오차가 중요할 수 있습니다. 이항모형에서는 기대 성공 횟수 np와 기대 실패 횟수 n(1−p)를 함께 봅니다. 둘 다 크다고 모든 꼬리 확률이 정확해지는 것은 아닙니다.</p>')
    sec('approximation', '정확한 확률과 정규근사', 'n=100에서 15%부터 25%까지의 확률을 두 방법으로 계산합니다',
        '<p>K~Bin(100, 0.2)의 평균은 20, 분산은 16, 표준편차는 4입니다. 참여 비율 15% 이상 25% 이하는 15≤K≤25입니다. 정확한 이항확률은 <strong>'
        + f'{exact:.4f}' + '</strong>, 곧 ' + f'{exact * 100:.2f}%' + '입니다. 정규분포를 가정한 값이 아닙니다.</p>'
        '<p>연속성 보정은 정수 15부터 25까지를 14.5 이상 25.5 이하로 근사합니다. 평균 20, 표준편차 4로 표준화하면 경계는 ±1.375입니다. N(20, 16)에서 16은 분산입니다. 보정한 근사확률은 <strong>'
        + f'{corrected:.4f}' + '</strong>, 곧 ' + f'{corrected * 100:.2f}%' + '입니다. 두 값은 가깝지만 모든 n과 모든 꼬리에서 이렇게 가깝다는 보장은 아닙니다.</p>'
        '<details class="learn-more"><summary>연속성 보정을 빼면</summary><div class="learn-more__body"><p>15 이상 25 이하를 그대로 연속 구간으로 두면 z 경계는 ±1.25이고 근사확률은 '
        + f'{plain:.4f}' + '입니다. 보정을 넣은 0.8309, 정확한 이항확률 0.8321과 구별합니다.</p></div></details>')
    sec('limits', '적용 조건', '평균이 어디로 가는지와 오차가 어떤 모양인지를 구별합니다',
        '<p><strong>대수의 법칙</strong>은 조건이 맞으면 표본평균이 모집단 평균에 가까워진다는 결과입니다. <strong>중심극한정리</strong>는 그 차이를 표준오차로 나눈 값이 어떤 분포에 가까워지는지를 설명합니다. 개별 관측이 모두 평균 근처로 모인다는 뜻은 아닙니다.</p>'
        '<p>특정 유형의 거래만 모으면 그 유형의 평균은 건수가 늘수록 안정될 수 있습니다. 그 평균이 지역 전체의 평균이 되는 것은 아닙니다. 많은 자료가 계산을 정밀하게 만들 수는 있지만, 잘못 정의된 모집단을 자동으로 바로잡지는 못합니다.</p>'
        '<p>같은 단지나 같은 시점의 거래는 공통 요인을 공유할 수 있습니다. 양의 공분산이 있으면 독립을 가정한 SE=s/√n보다 표본평균의 분산이 클 수 있습니다. 관련성이 항상 양수인 것은 아니므로 구조와 크기를 확인합니다. 일반적인 식은 Var(X̄)=[ΣVar(Xᵢ)+2Σᵢ&lt;ⱼCov(Xᵢ,Xⱼ)]/n²입니다.</p>'
        '<details class="learn-more"><summary>유한모집단 보정</summary><div class="learn-more__body"><p>크기가 N인 모집단에서 n개를 중복 없이 단순무작위 추출하고, 모집단 분산을 N으로 나눈 σ²를 쓰면 SE=(σ/√n)×√((N−n)/(N−1))입니다. n=1이면 보정계수는 1이고, n=N이면 그 고정된 모집단 평균의 표집오차는 0입니다. 측정 오류와 미래 거래의 불확실성은 남습니다. 과거 평균을 계산하는 일과 미래 평균을 예측하는 일은 다릅니다.</p></div></details>'
        '<p>분산이 유한하지 않거나, 시간적 의존이 강하거나, 군집이 있거나, 시점에 따라 분포가 달라지거나, 거래된 물건만으로 거래되지 않은 전체를 추론하면 이번 장의 기본 공식을 그대로 적용하기 어렵습니다. 중앙값, 분위수, 회귀계수도 표본분포를 가질 수 있지만, σ/√n을 그 통계량에 그대로 쓰지는 않습니다. 회귀계수의 표준오차는 설명변수의 구성, 잔차의 분산, 관측 간 의존에 따라 달라집니다.</p>')
    sec('practice', '확인 문제', '표본수, 반복 횟수, 분포의 대상을 구별해 보세요',
        '<ol class="learn-exercises">'
        '<li>n=25인 표본의 모의 추출을 1,000회에서 10,000회로 늘리면 이론적인 표준오차가 감소할까요?<details><summary>답과 해설</summary><p>아닙니다. 한 표본의 n과 표집 모형이 같으면 이론적 표준오차는 그대로입니다. 반복 횟수를 늘리면 시뮬레이션으로 그린 분포가 이론 분포에 더 가깝게 보일 수 있습니다.</p></details></li>'
        '<li>모집단 표준편차가 0.4일 때 n=25와 n=100의 표준오차는 각각 얼마일까요?<details><summary>답과 해설</summary><p>독립·동일분포에서 SE=0.4/√n입니다. n=25이면 0.08, n=100이면 0.04입니다. 표본수가 네 배가 되면 표준오차는 절반입니다.</p></details></li>'
        '<li>표본평균의 분포가 정규모양에 가까워지면 개별 관측도 정규분포가 될까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 이번 예제의 개별 X는 0 또는 1입니다. 정규분포에 가까워지는 대상은 조건이 맞을 때의 표준화한 표본평균입니다.</p></details></li>'
        '<li>거래자료가 10만 건이면 선택 편향이나 관측 간 의존성은 없어질까요?<details><summary>답과 해설</summary><p>아닙니다. 특정 유형에 거래가 몰려 있거나 거래끼리 관련되어 있을 수 있습니다. 표본수가 편향과 의존성을 자동으로 없애지는 못합니다.</p></details></li>'
        '<li>n=100, p=0.2일 때 참여 비율이 15~25%일 정확한 확률은 얼마일까요?<details><summary>답과 해설</summary><p>15≤K≤25의 정확한 이항확률은 약 83.21%입니다. 연속성 보정을 넣은 정규근사는 약 83.09%입니다. 두 값은 가깝지만 같지는 않습니다.</p></details></li>'
        '</ol>')
    sec('macro', 'CH2 Macro에서 읽기', '거래 건수만으로 평균의 불확실성을 정하지 않습니다',
        '<p>토지 매트릭스 칸은 거래 건수, 평균, 표본표준편차와 함께 평균의 95% t 신뢰구간을 보여 줍니다. 구간은 표본표준편차를 √n으로 나눈 값에 t 임계값을 곱해 만듭니다. 화면의 별도 칸 이름은 표준오차가 아니라 신뢰구간입니다. 이 계산은 관측을 독립으로 둔 공식입니다. 같은 지역이나 시점의 거래가 관련되어 있어도 군집표준오차로 바꾸어 계산하지는 않습니다.</p>'
        '<p>15건 이상인 칸은 신뢰구간을 강조하고, 5건 미만은 흐리게 표시합니다. 건수가 많다는 사실과 거래 구성이 비교 가능한지는 함께 봅니다. 실거래의 평균은 그 집계에 들어온 거래의 평균입니다. 거래되지 않은 토지까지 포함한 전체의 평균과 같다고 두지 않습니다.</p>'
        '<p>롤링 기간은 3년·5년·7년입니다. 기간을 늘리면 건수가 늘 수 있지만, 서로 다른 시점의 가격 수준이 한 평균에 섞일 수 있습니다. 개별 단가의 표준편차, 평균의 표준오차, 회귀모형의 예측오차는 서로 다른 질문입니다.</p>'
        '<p>토지 회귀계수의 표준오차는 OLS의 기본 공분산으로 계산합니다. 단지·지역·시점으로 묶은 군집표준오차는 이 제품 회귀에 들어 있지 않습니다. 표본이 최소 기준보다 적으면 회귀 결과를 내지 않으며, 그 절대 하한은 10건입니다. 표본수가 매우 많으면 실무적으로 작은 차이도 통계적으로 뚜렷하게 보일 수 있으므로, 계수의 크기와 표본 구성을 함께 봅니다.</p>'
        '<p>이번 장의 0·1 모형과 네 그림은 교육용입니다. 실제 거래자료를 반복 표집한 결과가 아닙니다.</p>'
        '<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>')
    sec('recap', '결론 · 학습 요약', '중심극한정리는 개별 자료가 아니라 평균의 분포에 관한 정리입니다',
        '<p>표본을 다시 고르면 평균도 달라질 수 있습니다. 조건이 맞으면 표본수가 커질수록 평균의 퍼짐은 줄어들고, 표준화한 표본평균의 분포는 정규분포에 가까워집니다. 개별 거래단가가 정규분포가 되거나 선택 편향이 사라지는 것은 아닙니다.</p>'
        '<ul class="learn-recap-list">'
        '<li><strong>세 분포:</strong> 모집단의 개별 값, 한 표본의 n개 값, 반복해서 구한 평균은 서로 다른 대상입니다.</li>'
        '<li><strong>n과 B:</strong> n은 한 표본의 관측수이고, B는 모의 추출 횟수입니다.</li>'
        '<li><strong>SD와 SE:</strong> 이번 모형에서 개별 표준편차는 0.4이고, 독립·동일분포에서 평균의 표준오차는 0.4/√n입니다.</li>'
        '<li><strong>중심극한정리:</strong> 가까워지는 것은 표준화한 표본평균의 분포입니다.</li>'
        '<li><strong>정규근사:</strong> n=100의 15~25회는 정확한 확률 0.8321, 연속성 보정 근사 0.8309입니다.</li>'
        '<li><strong>해석:</strong> 큰 표본도 편향과 의존성을 자동으로 없애지 않습니다.</li>'
        '</ul>'
        '<p>다음 <a href="/learn/stats/sample-size/">11장 「표준오차와 표본수」</a>에서는 관측한 자료로 표준오차를 추정하고, 표본수에 따른 정밀도를 더 살펴봅니다.</p>'
        '<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/7-1-the-central-limit-theorem-for-sample-means-averages">OpenStax, Introductory Statistics 2e §7.1</a> — 표본평균의 중심극한정리.</li>'
        '</ul><p class="learn-source-note">참고자료 확인일: 2026-10-07. 네 그림은 교육용 가상모형과 개념도입니다. CH2 Macro의 거래자료를 표집한 결과가 아닙니다.</p></div></details>')

    page = ROOT / 'sampling-distributions' / 'index.html'
    html = page.read_text(encoding='utf-8')
    article = (
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" '
        'aria-label="표본분포와 중심극한정리">\n' + '\n'.join(parts) + '\n</article>'
    )
    html = re.sub(r'<article.*?</article>', article, html, count=1, flags=re.S)
    html = re.sub(
        r'(name="description"\s+content=").*?("\s*/>)',
        r'\1표본평균의 분포, 표준오차와 중심극한정리를 가상 베르누이 모형으로 계산합니다.\2',
        html, count=1, flags=re.S,
    )
    if 'sampling-distributions/chapter.css' not in html:
        html = html.replace(
            'learn-reader.css?v=20261026-toc" />',
            'learn-reader.css?v=20261026-toc" />\n    <link rel="stylesheet" href="/learn/stats/sampling-distributions/chapter.css?v=20261026-20" />',
        )
    html = re.sub(
        r'\n\s*<script type="module" src="/learn/stats/sampling-distributions/experiment\.js[^"]*"></script>',
        '', html,
    )
    html = html.replace(
        '</body>',
        '    <script type="module" src="/learn/stats/sampling-distributions/experiment.js?v=20261026-21"></script>\n  </body>',
    )
    assert '2단계, 권장' in html and '★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화' in html
    page.write_text(html, encoding='utf-8')

    written = page.read_text(encoding='utf-8')
    charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', written, re.S)]
    assert len(charts) == 4
    bars = [item for item in charts[1].findall('line') if 'data-n' in item.attrib]
    assert len(bars) == 140
    for bar in bars:
        n = int(bar.attrib['data-n'])
        k = int(bar.attrib['data-k'])
        p = binomial(n, .2)[k]
        assert abs(float(bar.attrib['x1']) - (70 + 500 * k / n)) < 1e-9
        assert abs(float(bar.attrib['y1']) - float(bar.attrib['y2']) - 125 * p) < 1e-9
    for bar in charts[2].findall('rect'):
        se = .4 / math.sqrt(int(bar.attrib['data-n']))
        assert float(bar.attrib['data-se']) == se and float(bar.attrib['width']) == se * 900
    assert f'{exact:.4f}' in written and f'{corrected:.4f}' in written
    ids = re.findall(r'\bid="([^"]+)"', written)
    assert len(ids) == len(set(ids))
    assert written.count('<summary>답과 해설</summary>') == 5
    practice = re.search(r'<section[^>]*id="practice".*?</section>', written, re.S).group(0)
    assert 'open' not in practice
    course = json.loads((ROOT / 'course.json').read_text(encoding='utf-8'))
    items = [item for group in course for item in group['items']]
    assert next(item['macro_relevance'] for item in items if item['slug'] == 'sampling-distributions') == 2
    print('chapter 10 exact', f'{exact:.4f}', 'corrected', f'{corrected:.4f}', 'plain', f'{plain:.4f}')


def trim(value):
    return f'{value:.6f}'.rstrip('0').rstrip('.')


if __name__ == '__main__':
    build()
