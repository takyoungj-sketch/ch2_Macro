"""Generate chapter 09 from the binomial, uniform and normal teaching models."""
from pathlib import Path
from html import escape
import math
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def binomial(n, p):
    return [math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n + 1)]


def normal(z):
    return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)


def inclusion(z):
    return round(math.erf(z / math.sqrt(2)) * 100, 2)


def build():
    probs = binomial(3, .4)
    assert all(abs(a - b) < 1e-12 for a, b in zip(probs, [.216, .432, .288, .064]))
    assert abs(sum(probs) - 1) < 1e-12
    mu = sum(k * p for k, p in enumerate(probs))
    ex2 = sum(k * k * p for k, p in enumerate(probs))
    var = ex2 - mu ** 2
    assert abs(mu - 1.2) < 1e-12 and abs(ex2 - 2.16) < 1e-12 and abs(var - .72) < 1e-12
    assert abs(math.sqrt(var) - math.sqrt(.72)) < 1e-12
    cdf_values = []
    running = 0
    for p in probs:
        running += p
        cdf_values.append(running)
    assert [round(v, 3) for v in cdf_values] == [.216, .648, .936, 1]
    assert abs((1 - cdf_values[1]) - .352) < 1e-12
    assert abs((1 - probs[0]) - .784) < 1e-12
    assert [inclusion(z) for z in (1, 2, 3)] == [68.27, 95.45, 99.73]
    assert (80 - 100) / 20 == -1 and (120 - 100) / 20 == 1 and 20 ** 2 == 400
    for start, end, probability in ((0, 10, 1), (2, 6, .4), (4, 4, 0), (0, 5, .5), (8, 10, .2)):
        assert abs((end - start) / 10 - probability) < 1e-12

    example = {
        'description': '09장 학습용 가상 확률모형. 이항분포, 균등분포, 표준정규분포이며 실제 조사나 서비스 통계가 아님.',
        'binomial': {'n': 3, 'p': .4, 'probabilities': probs},
        'uniform': {'a': 0, 'b': .5},
        'normal': {'mu': 0, 'sigma': 1},
    }
    (ROOT / 'distributions-example.json').write_text(
        json.dumps(example, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )

    def t(x, y, text, extra=''):
        return f'<text x="{x}" y="{y}" {extra}>{escape(str(text))}</text>'

    def line(x, y, xx, yy, extra=''):
        return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#64748b" {extra}/>'

    def fig(svg_id, title, body, caption, height):
        return (
            f'<figure class="learn-chart learn-chart--wide pd-chart">'
            f'<svg viewBox="0 0 640 {height}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc">'
            f'<title id="{svg_id}-title">{escape(title)}</title>'
            f'<desc id="{svg_id}-desc">{escape(caption)}</desc>{body}</svg>'
            f'<figcaption id="{svg_id}-caption" class="learn-chart__caption">{escape(caption)}</figcaption></figure>'
        )

    body = t(24, 27, '3회 독립 추출에서 관심 대상이 선택된 횟수') + line(70, 245, 570, 245) + line(70, 45, 70, 245)
    for q in [0, .1, .2, .3, .4, .5]:
        body += t(58, 250 - q * 380, f'{q:.1f}', 'text-anchor="end"')
    for k, p in enumerate(probs):
        x = 115 + k * 130
        body += (
            f'<rect x="{x}" y="{245 - p * 380}" width="50" height="{p * 380}" fill="#2563eb" '
            f'data-k="{k}" data-p="{p}"/>'
            + t(x + 25, 235 - p * 380, f'{p:.3f}', 'text-anchor="middle"')
            + t(x + 25, 272, k, 'text-anchor="middle"')
        )
    body += t(250, 301, 'X: 선택된 횟수(회)') + t(80, 49, 'P(X=x)')
    figure1 = fig(
        'pmf', '이항분포의 확률질량', body,
        '그림 1. 성공확률 0.4인 독립 복원 추출 3회. 막대 높이는 각 횟수의 확률이며 합은 1입니다. 관측 인원이 아닙니다.',
        325,
    )

    body = t(24, 27, 'F(x)는 x 이하의 확률을 누적합니다') + line(70, 250, 570, 250) + line(70, 45, 70, 250)
    cumulative = 0
    for k, p in enumerate(probs):
        previous = cumulative
        cumulative += p
        x = 130 + k * 110
        y = 250 - cumulative * 180
        body += line(x, y, x + 110, y, 'stroke-width="3"')
        body += f'<circle cx="{x}" cy="{y}" r="4" fill="#2563eb" data-k="{k}" data-cdf="{cumulative}"/>'
        body += f'<circle cx="{x}" cy="{250 - previous * 180}" r="4" fill="white" stroke="#2563eb"/>'
        body += t(x + 40, y - 10, f'{cumulative:.3f}') + t(x, 276, k, 'text-anchor="middle"')
    body += line(70, 250, 130, 250) + t(24, 72, '1.0') + t(24, 254, '0') + t(250, 310, 'x: 선택된 횟수(회)')
    figure2 = fig(
        'cdf', '이산 누적분포함수', body,
        '그림 2. F(0)=0.216, F(1)=0.648, F(2)=0.936, F(3)=1. 채운 점은 그 x의 함수값이고 빈 점은 포함하지 않는 끝입니다.',
        334,
    )

    body = t(24, 27, '연속형에서는 높이가 아니라 면적이 확률입니다') + line(70, 235, 590, 235) + line(70, 50, 70, 235)
    body += '<rect id="pd-density-area" x="170" y="85" width="200" height="150" fill="#bfdbfe" data-area="0.4"/>'
    body += line(70, 85, 570, 85, 'stroke-width="3"') + line(570, 85, 570, 235)
    body += t(48, 90, '2', 'text-anchor="end"') + t(24, 58, '밀도(1/시간)')
    for i in range(6):
        body += t(70 + i * 100, 263, f'{i / 10:.1f}', 'text-anchor="middle"')
    body += t(205, 152, '면적 0.2×2=0.4', 'id="pd-density-label"') + t(360, 299, 'X: 대기시간(시간)')
    figure3 = fig(
        'density', '균등분포의 구간 확률', body,
        '그림 3. 대기시간이 0~0.5시간에 균등하다는 별도 가상 모형. 밀도는 2/시간이고 0.1~0.3시간의 확률은 0.4입니다.',
        323,
    )

    def point(z):
        return (320 + z * 65, 245 - normal(z) * 430)

    pts = [point(-4 + i * .025) for i in range(321)]
    shade = [point(-1 + i * .02) for i in range(101)]
    body = t(24, 27, '표준정규분포: 평균 0, 분산 1') + line(60, 245, 580, 245)
    body += '<polygon id="pd-normal-shade" points="255,245 ' + ' '.join(f'{x:.4f},{y:.4f}' for x, y in shade) + ' 385,245" fill="#bfdbfe"/>'
    body += '<polyline points="' + ' '.join(f'{x:.4f},{y:.4f}' for x, y in pts) + '" fill="none" stroke="#2563eb" stroke-width="2" data-normal="standard"/>'
    for z in range(-4, 5):
        body += t(320 + z * 65, 270, z, 'text-anchor="middle"')
    body += t(280, 166, '약 68.27%', 'id="pd-normal-label"')
    body += t(24, 310, '−2~2: 약 95.45% / −3~3: 약 99.73%') + t(525, 295, 'z')
    figure4 = fig(
        'normal-curve', '표준정규분포와 중심 구간', body,
        '그림 4. 색 면적은 −1≤Z≤1이며 포함확률은 약 68.27%입니다. 곡선은 −4~4만 그렸고 꼬리는 양쪽으로 이어집니다.',
        340,
    )

    def button(attr, value, label):
        return f'<button type="button" {attr}="{escape(str(value))}" aria-pressed="false">{escape(label)}</button>'

    discrete_buttons = ''.join(button('data-k-choice', i, f'{i}번') for i in range(4))
    discrete_buttons += ''.join(button('data-mode', value, label) for value, label in (
        ('exact', '정확히'), ('below', '이하'), ('above', '이상'),
    ))
    discrete_controls = (
        '<div class="pd-controls" hidden><p>횟수를 고르면 확률질량과 누적확률이 함께 바뀝니다. 정확히, 이하, 이상은 서로 다른 사건입니다.</p>'
        f'<div class="pd-shortcuts" role="group" aria-label="이항분포 횟수">{discrete_buttons}</div>'
    )
    uniform_buttons = ''.join(button('data-span', value, label) for value, label in (
        ('0-10', '0~0.5'), ('2-6', '0.1~0.3'), ('4-4', '0.2 한 점'), ('0-5', '0~0.25'), ('8-10', '0.4~0.5'),
    ))

    parts = []

    def sec(section_id, label, title, body_html):
        parts.append(
            f'<section class="learn-chapter__step" id="{section_id}" data-toc-label="{escape(label)}">'
            f'<p class="learn-chapter__label">{escape(label)}</p><h2>{title}</h2>{body_html}</section>'
        )

    sec(
        'quick-start', '서두 · 학습목표',
        '우연한 결과를 숫자로 나타내면 무엇을 알 수 있을까요?',
        '<p>동전을 세 번 던지면 앞면은 0번, 1번, 2번, 3번 가운데 하나입니다. 버스를 기다린 시간은 0.1시간, 0.2시간, 0.25시간처럼 연속적인 숫자로 적을 수 있습니다.</p>'
        '<p>우연한 결과에 숫자를 대응시키는 규칙이 <strong>확률변수</strong>입니다. 각 숫자에 어떤 확률이 붙는지를 나타낸 것이 <strong>확률분포</strong>입니다. 분포를 알면 한 결과의 가능성뿐 아니라 평균적인 수준과 퍼짐도 계산할 수 있습니다. 횟수처럼 하나씩 셀 수 있는 값과 시간처럼 연속적인 값은 확률을 매기는 방법이 다릅니다.</p>'
        '<ul class="learn-objectives">'
        '<li>확률변수와 확률분포, 이산형과 연속형을 구별합니다.</li>'
        '<li>확률질량함수, 확률밀도함수, 누적분포함수의 차이를 이해합니다.</li>'
        '<li>기대값과 분산, 베르누이분포와 이항분포를 계산합니다.</li>'
        '<li>정규분포, 표준정규분포, z점수와 포함확률을 구별합니다.</li>'
        '<li>관측된 거래가격 분포와 이론적 확률모형을 구별합니다.</li></ul>'
        '<p>이번 장에는 서로 섞지 않는 세 개의 가상 모형이 있습니다. 독서 동아리 선택을 세 번 하는 이항분포, 버스 대기시간의 균등분포, 평균 0·분산 1인 표준정규분포와 평균 100·표준편차 20인 정규모형입니다. <a href="/learn/stats/probability/">8장의 거래 100건</a>이나 1~7장의 공통 30건이 아닙니다.</p>',
    )
    sec(
        'random-variable', '확률변수',
        '우연한 결과에 숫자를 대응시키는 규칙입니다',
        '<p>8장에서 표본공간은 가능한 결과 전체이고, 사건은 그중 관심 있는 결과의 집합이었습니다. 이번에는 그 결과를 숫자로 바꿉니다. 동전을 세 번 던진 결과마다 앞면 횟수 X를 대응시키면 X는 0, 1, 2, 3 중 하나입니다.</p>'
        '<ul><li><strong>X:</strong> 확률변수입니다.</li>'
        '<li><strong>x:</strong> 그 변수가 가질 수 있는 한 값입니다.</li>'
        '<li><strong>P(X=x):</strong> X가 x가 될 확률입니다. P(X=2)는 앞면이 정확히 두 번일 확률입니다.</li></ul>'
        '<p>확률변수는 이미 모은 자료 그 자체가 아닙니다. 실험을 수행하면 그때 하나의 관측값을 얻습니다.</p>',
    )
    sec(
        'kinds', '이산형과 연속형',
        '가능한 값을 하나씩 셀 수 있는지가 중요합니다',
        '<p><strong>이산 확률변수</strong>는 가능한 값을 개별적으로 구별해 셀 수 있습니다. 세 번 추출한 관심 대상의 횟수, 한 달의 거래 건수, 조건을 충족한 건물 수가 예입니다. 이산형이라고 반드시 정수만 가능한 것은 아닙니다.</p>'
        '<p><strong>연속 확률변수</strong>는 시간, 높이, 연속적으로 잰 면적처럼 구간 위의 값을 모형화할 때 씁니다. 기록을 소수 한 자리로 반올림했다고 해서 측정 대상이 이산형이 되지는 않습니다. 화폐의 최소 단위로 적힌 거래금액과, 분석에서 쓰는 연속 근사도 구별합니다. 데이터베이스의 숫자 자료형만으로 이산형과 연속형이 결정되지는 않습니다.</p>',
    )
    sec(
        'pmf', '확률질량함수',
        '막대의 높이가 그 값의 확률입니다',
        '<p>학생 명단에서 독서 동아리 참여자 비율이 40%라고 가정합니다. 한 명을 뽑은 뒤 명단에 다시 넣고, 같은 확률로 세 번 뽑습니다. 각 추출은 독립이고 참여자를 뽑을 확률은 매번 0.4입니다. X는 세 번 가운데 참여자가 선택된 횟수이며 0, 1, 2, 3만 가능합니다. 같은 학생이 다시 뽑힐 수 있으므로 서로 다른 학생 수가 아닙니다. 이 모형은 8장의 거래 100건과 다릅니다.</p>'
        + discrete_controls + '<p id="pd-pmf-status" role="status"></p></div>'
        + figure1
        + '<div class="learn-data learn-data--full pd-table"><table><caption>Bin(3, 0.4)의 확률질량. 복원 독립 추출</caption>'
        '<thead><tr><th scope="col">X: 선택 횟수</th><th scope="col">P(X=x)</th></tr></thead><tbody>'
        '<tr><th scope="row">0</th><td>0.216</td></tr><tr><th scope="row">1</th><td>0.432</td></tr>'
        '<tr><th scope="row">2</th><td>0.288</td></tr><tr><th scope="row">3</th><td>0.064</td></tr>'
        '<tr><th scope="row">합계</th><td>1.000</td></tr></tbody></table></div>'
        '<p>각 확률은 0 이상이고 합은 1입니다. 막대는 관측한 학생 수가 아니라 모형에서 그 횟수가 나올 확률입니다. X=2이면 한 순서의 확률은 0.4×0.4×0.6=0.096이고, 가능한 순서는 3가지라 3×0.096=0.288입니다. <a href="../distributions-example.json">가상 모형의 확률표(JSON)</a>와 같은 계산입니다.</p>'
        '<p>두 번 이상일 확률은 P(X=2)+P(X=3)=0.288+0.064=<strong>0.352</strong>, 곧 35.2%입니다. 이산분포에서는 해당하는 값의 확률을 더합니다.</p>',
    )
    sec(
        'cdf', '누적분포함수',
        '특정 값 이하일 확률을 모읍니다',
        '<p><strong>F(x)=P(X≤x)</strong>는 X가 x 이하일 확률입니다. 이산형과 연속형에 모두 정의됩니다. 이번 예제는 F(0)=0.216, F(1)=0.648, F(2)=0.936, F(3)=1입니다. F(1)=0.216+0.432이고 F(2)는 여기에 0.288을 더한 값입니다.</p>'
        + discrete_controls + '<p id="pd-cdf-status" role="status"></p></div>'
        + figure2
        + '<p>이산 누적분포는 각 값에서 그 확률만큼 계단으로 올라갑니다. 점프 높이는 그림 1의 확률질량과 같습니다. 함수값은 0과 1 사이이고, x가 커져도 감소하지 않으며, 왼쪽 끝은 0, 오른쪽 끝은 1에 가까워집니다. 점프가 있는 위치에서는 오른쪽 연속입니다. 채운 점이 그 x의 함수값입니다.</p>'
        '<p>정수만 가능한 이번 X에서는 P(X&gt;1)와 P(X≥2)가 같습니다. 둘 다 0.352입니다. 그러나 P(X≥1)=1−P(X=0)=0.784이고 P(X&gt;1)=1−F(1)=0.352입니다. 경계값이 확률을 가지므로 부등호를 구별합니다. 일반적으로 P(a&lt;X≤b)=F(b)−F(a)입니다. a부터 b까지 모두 포함하려면 a보다 작은 쪽의 누적을 빼며, 정수 횟수에서는 F(a−1)을 쓸 수 있습니다. 다른 이산 변수는 가능한 값의 위치를 확인합니다.</p>',
    )
    sec(
        'moments', '기대값과 분산',
        '확률을 비중으로 중심과 퍼짐을 구합니다',
        '<p>기대값은 가능한 값에 그 확률을 곱해 더한 값입니다. E[X]=0(0.216)+1(0.432)+2(0.288)+3(0.064)=<strong>1.2</strong>입니다. 한 번의 결과는 0·1·2·3뿐이라 1.2회가 나오지는 않습니다. 기대값은 가능한 값 중 하나일 필요가 없고, 같은 모형을 반복할 때의 평균적인 수준입니다. 확률이 가장 큰 값은 X=1, P(X=1)=0.432입니다. 기대값과 최빈값은 다를 수 있습니다.</p>'
        '<p>관측평균은 관측값을 관측수로 나눕니다. 기대값은 모형의 확률을 곱합니다. 예를 들어 10번 실험의 횟수가 0, 1, 2, 1, 1, 3, 0, 1, 2, 1이면 합은 12이고 평균은 1.2입니다. 이 목록은 우연히 기대값과 같습니다. 다른 10번에서는 0.9나 1.5가 될 수 있습니다. 반복이 충분하면 관측평균이 기대값에 가까워지는 경향을 말할 수 있지만, 표본이 작으면 차이가 납니다.</p>'
        '<p>분산은 Var(X)=E[X²]−E[X]²입니다. E[X²]=0+0.432+1.152+0.576=2.16이므로 Var(X)=2.16−1.44=<strong>0.72</strong>입니다. 표준편차는 √0.72≈0.8485이고, 반올림하면 약 0.849회입니다. 한 번의 결과가 기대값에서 반드시 0.849회 떨어진다는 뜻은 아닙니다. 이 계산은 이미 정의된 분포의 분산이라 6장의 n−1 보정을 붙이지 않습니다.</p>'
        '<div class="learn-data learn-data--full pd-table"><table><caption>Bin(3, 0.4)의 중심과 퍼짐</caption>'
        '<thead><tr><th scope="col">항목</th><th scope="col">계산 결과</th></tr></thead><tbody>'
        '<tr><th scope="row">기대값 E[X]</th><td>1.2회</td></tr>'
        '<tr><th scope="row">E[X²]</th><td>2.16회²</td></tr>'
        '<tr><th scope="row">분산 Var(X)</th><td>0.72회²</td></tr>'
        '<tr><th scope="row">표준편차 SD(X)</th><td>약 0.849회</td></tr>'
        '</tbody></table></div>'
        '<details class="learn-more"><summary>값을 더하거나 곱하면 어떻게 되나요?</summary><div class="learn-more__body">'
        '<p>Y=aX+b이면 E[Y]=aE[X]+b이고 Var(Y)=a²Var(X), SD(Y)=|a|SD(X)입니다. 모든 값에 같은 수를 더해도 평균과의 차이는 그대로라 b는 분산에 나타나지 않습니다. E[X]=1.2, Var(X)=0.72일 때 Y=2X+3이면 E[Y]=5.4, Var(Y)=2.88입니다.</p>'
        '<p>E[X+Y]=E[X]+E[Y]에는 독립이 필요하지 않습니다. Var(X+Y)=Var(X)+Var(Y)+2Cov(X,Y)입니다. 독립이고 분산이 유한하면 공분산은 0이라 분산을 더할 수 있습니다. 같은 단지나 같은 시점의 거래는 공통 요인의 영향을 받을 수 있으므로, 여러 건을 모았다는 이유만으로 독립이라고 보지 않습니다. 이 구분은 <a href="/learn/stats/sampling-distributions/">10장 표본분포</a>에서 이어집니다.</p>'
        '</div></details>',
    )
    sec(
        'binomial', '베르누이분포와 이항분포',
        '같은 확률의 독립 시행을 정해진 횟수만큼 반복합니다',
        '<p>베르누이분포는 한 번의 시행에서 관심 사건이 일어나면 1, 아니면 0입니다. P(X=1)=p, P(X=0)=1−p이고 E[X]=p, Var(X)=p(1−p)입니다. 1을 관습적으로 성공이라고 부르지만 좋은 결과라는 뜻은 아닙니다. 오류가 있는 거래를 1로 적어도 오류가 바람직하다는 뜻은 아닙니다.</p>'
        '<p>이항분포 Bin(n, p)는 다음 네 가지가 있을 때 성공 횟수의 분포입니다. 시행 횟수 n이 정해져 있고, 각 시행이 성공과 실패로 나뉘며, 시행이 서로 독립이고, 성공확률 p가 같습니다. 이번 예제는 X~Bin(3, 0.4)입니다.</p>'
        '<p>P(X=k)=C(n, k)p<sup>k</sup>(1−p)<sup>n−k</sup>입니다. C(3, 2)=3이므로 P(X=2)=3×0.16×0.6=0.288입니다. 공식으로도 E[X]=np=1.2, Var(X)=np(1−p)=0.72이며 확률표를 직접 더한 값과 같습니다.</p>'
        '<p>뽑은 학생을 다시 넣지 않으면 다음 추출의 명단이 달라집니다. 그때는 시행이 일반적으로 독립이 아니고 성공확률도 달라지므로, 횟수를 센다는 이유만으로 이항분포를 쓰지 않습니다. 명단의 비율이 40%라는 사실과, 이후 세 번의 독립 선택이 Bin(3, 0.4)를 따른다는 모형은 다른 문장입니다. 이번 예제는 복원 독립 추출을 가정했기 때문에 이항분포를 씁니다.</p>',
    )
    sec(
        'uniform', '확률밀도함수',
        '밀도의 높이가 아니라 구간 아래 면적이 확률입니다',
        '<p>연속 모형에서는 각 점에 확률을 붙여 더하는 대신 <strong>확률밀도함수</strong> f(x)를 씁니다. 밀도는 0 이상이고 전체 면적은 1이며, 구간의 확률은 그 아래 면적입니다. 높이 자체가 확률은 아닙니다.</p>'
        '<p>버스 대기시간 X가 0시간부터 0.5시간까지 균등하다고 가정합니다. 실제 운행 기록이 아니라 면적을 보이기 위한 모형입니다. 전체 면적이 1이려면 f(x)=1/0.5=<strong>2/시간</strong>입니다. 2는 200%가 아닙니다. 범위 밖 밀도는 0입니다.</p>'
        '<div class="pd-controls" hidden><p>구간을 바꾸면 색 면적과 확률이 함께 바뀝니다. 밀도 높이 2는 그대로입니다.</p>'
        f'<div class="pd-shortcuts" role="group" aria-label="대기시간 구간">{uniform_buttons}</div>'
        '<div class="pd-sliders"><label>시작 <span id="pd-uniform-start-label">0.1시간</span>'
        '<input id="pd-uniform-start" type="range" min="0" max="10" step="1" value="2" aria-label="구간 시작, 0.05시간 간격"></label>'
        '<label>끝 <span id="pd-uniform-end-label">0.3시간</span>'
        '<input id="pd-uniform-end" type="range" min="0" max="10" step="1" value="6" aria-label="구간 끝, 0.05시간 간격"></label></div>'
        '<p id="pd-uniform-status" role="status"></p></div>'
        + figure3
        + '<p>0.1~0.3시간의 폭은 0.2시간입니다. 0.2×2=<strong>0.4</strong>이므로 확률은 40%입니다. 6분~18분과 같은 구간입니다. 시간을 분으로 바꾸면 범위는 0~30분이고 밀도는 1/30입니다. 같은 사건의 확률은 바뀌지 않습니다.</p>'
        '<p>연속 밀도에서 P(X=0.2)=0입니다. 그 시각이 불가능하다는 뜻이 아니라, 폭이 없는 한 점의 면적이 0이라는 뜻입니다. 0.19~0.21시간의 폭은 0.02이므로 확률은 0.04입니다. P(0.1&lt;X&lt;0.3)과 P(0.1≤X≤0.3)은 둘 다 0.4입니다. 반올림해 기록한 0.2시간은 여러 실제 시간을 대표할 수 있으므로, 수학적인 한 점과 구별합니다.</p>'
        '<p>이 균등분포의 누적은 x&lt;0이면 0, 0≤x≤0.5이면 F(x)=2x, x&gt;0.5이면 1입니다. F(0.1)=0.2, F(0.3)=0.6이고 차이는 0.4입니다. 이산형은 계단, 연속 밀도는 이어지는 곡선으로 나타날 수 있습니다. 이산 질량과 연속 부분이 함께 있는 혼합분포도 있지만, 이번 장의 그림은 순수한 두 경우만 다룹니다.</p>'
        '<details class="learn-more"><summary>면적을 수식으로는 어떻게 나타내나요?</summary><div class="learn-more__body">'
        '<p>구간 확률은 a부터 b까지 밀도를 적분한 값입니다. 기대값과 분산도 밀도에 x 또는 (x−μ)²를 곱해 적분합니다. 그 값이 유한해야 합니다. 이번 장에서 필요한 내용은 이산형은 확률을 더하고, 연속형은 면적을 구한다는 구분입니다.</p>'
        '</div></details>',
    )
    sec(
        'gaussian', '정규분포와 z점수',
        '포함확률 68%·95%·99.7%는 정규분포일 때의 성질입니다',
        '<p>정규분포는 평균 μ를 중심으로 대칭인 종 모양의 연속분포입니다. X~N(μ, σ²)에서 두 번째 값은 표준편차가 아니라 분산이고, 표준편차 σ는 0보다 큽니다. 평균이 바뀌면 중심이 이동하고, 표준편차가 커지면 곡선은 넓고 낮아집니다. 어느 경우에도 전체 면적은 1입니다.</p>'
        '<p>Z=(X−μ)/σ로 표준화합니다. X가 정규분포이면 Z는 평균 0, 분산 1인 표준정규분포 N(0, 1)을 따릅니다. z점수는 평균에서 표준편차 몇 개만큼 떨어져 있는지를 나타냅니다. z점수가 크다는 사실만으로 관측이 오류인 것은 아니고, 표준화만으로 분포가 정규분포가 되지도 않습니다.</p>'
        '<div class="pd-controls" hidden><p>±1σ, ±2σ, ±3σ는 표준정규분포의 포함확률입니다. 모든 자료의 포함 비율이 아닙니다.</p>'
        '<div class="pd-shortcuts" role="group" aria-label="표준편차 구간">'
        + ''.join(button('data-sigma', value, label) for value, label in ((1, '±1σ'), (2, '±2σ'), (3, '±3σ')))
        + '</div><p id="pd-normal-status" role="status"></p></div>'
        + figure4
        + '<div class="learn-data learn-data--full pd-table"><table><caption>표준정규분포의 포함확률</caption>'
        '<thead><tr><th scope="col">구간</th><th scope="col">정규분포의 포함확률</th></tr></thead><tbody>'
        '<tr><th scope="row">평균 ± 1표준편차</th><td>약 68.27%</td></tr>'
        '<tr><th scope="row">평균 ± 2표준편차</th><td>약 95.45%</td></tr>'
        '<tr><th scope="row">평균 ± 3표준편차</th><td>약 99.73%</td></tr>'
        '</tbody></table></div>'
        '<p>별도의 가상 모형 X~N(100, 400)은 평균 100, 분산 400, 표준편차 20입니다. X=80이면 z=−1, X=100이면 z=0, X=120이면 z=1입니다. 80~120은 표준정규분포의 −1~1에 대응하고, 이 모형이 정규분포라면 그 확률은 약 68.27%입니다. ±2표준편차는 60~140, 약 95.45%이고 ±3표준편차는 40~160, 약 99.73%입니다.</p>'
        '<p>거래단가 30건을 표준화했다고 해서 약 68%가 z=−1과 1 사이에 들어가야 하는 것은 아닙니다. 표준화는 중심과 척도를 바꾸지만 모양을 정규분포로 만들지 않습니다. 그림은 z=−4부터 4까지 그렸지만 정규분포의 꼬리는 그 밖에서 이어지고, 아주 먼 구간의 확률은 작습니다.</p>'
        '<details class="learn-more"><summary>정규분포의 밀도식</summary><div class="learn-more__body">'
        '<p>밀도는 1/(σ√(2π))에 exp(−(x−μ)²/(2σ²))를 곱한 값입니다. 식을 외울 필요는 없습니다. 곡선의 중심과 높이가 평균과 표준편차로 정해지고, 전체 면적은 1이라는 점이 중요합니다.</p>'
        '</div></details>'
        '<p>거래단가는 0보다 작은 값을 해석하기 어려운 경우가 많습니다. 정규분포는 수학적으로 음수 영역에도 확률을 둡니다. 평균이 크고 표준편차가 작으면 그 확률은 매우 작을 수 있지만, 0 이상이어야 하는 제한이 중요하면 정규모형이 맞는지 확인합니다. 낮은 구간에 관측이 몰리고 고가 쪽으로 꼬리가 길거나, 용도와 규모와 시점이 섞이면 하나의 정규분포로 설명하기 어렵습니다. 로그정규분포도 자료가 그 분포를 따른다는 확인 없이 자동으로 고르지 않습니다.</p>',
    )
    sec(
        'empirical', '관측 분포와 중심극한정리',
        '히스토그램의 건수와 확률모형의 밀도는 다른 대상입니다',
        '<p><a href="/learn/stats/graphs/">3장의 히스토그램</a>은 관측한 자료를 구간으로 모아 건수나 밀도를 보여 줍니다. 확률분포는 모형에서 값이 생길 가능성을 나타냅니다. 건수 축 위에 정규분포 밀도를 그대로 겹치면 단위가 다릅니다. 비교하려면 히스토그램을 밀도로 맞추거나, 밀도를 같은 조건의 예상 건수로 바꿔야 합니다. 구간 폭과 표본수도 맞춥니다.</p>'
        '<p>히스토그램이 종 모양이라고 정규분포인 것은 아닙니다. 구간 폭과 표본수에 따라 모양이 달라지고, 표본이 적으면 우연히 비슷해 보일 수 있습니다. 대칭, 꼬리, 이상치, 집단 구성, 분석 목적을 함께 봅니다.</p>'
        '<p>거래가 100건에서 1만 건으로 늘어도 개별 단가의 분포가 정규분포로 바뀌지는 않습니다. 오른쪽으로 긴 분포는 자료가 많아져도 그 특징이 남을 수 있습니다. 10장의 중심극한정리는 조건이 맞을 때 <strong>표본평균의 분포</strong>가 정규분포에 가까워진다는 결과입니다. 개별 거래단가의 분포와 다릅니다.</p>',
    )
    sec(
        'practice', '확인 문제',
        '값의 확률과 밀도 아래 면적을 구별해 보세요',
        '<ol class="learn-exercises">'
        '<li>X~Bin(3, 0.4)일 때 독서 동아리 참여자를 두 번 이상 선택할 확률은 얼마일까요?'
        '<details><summary>답과 해설</summary><p>X=2 또는 X=3을 더합니다. 0.288+0.064=0.352, 곧 35.2%입니다. 1−F(1)=1−0.648로도 같습니다.</p></details></li>'
        '<li>한 번의 결과는 0·1·2·3회뿐입니다. 기대값 1.2회는 잘못된 계산일까요?'
        '<details><summary>답과 해설</summary><p>아닙니다. 기대값은 가능한 값에 확률을 곱한 가중평균이라, 한 번에 나올 수 없는 소수도 기대값이 될 수 있습니다.</p></details></li>'
        '<li>확률밀도함수의 높이가 2라면 확률이 200%라는 뜻일까요?'
        '<details><summary>답과 해설</summary><p>그렇지 않습니다. 연속형에서 확률은 면적입니다. 폭 0.5시간에 높이 2/시간을 곱하면 전체 면적은 1입니다.</p></details></li>'
        '<li>거래단가를 z점수로 바꾸면 항상 약 68%가 −1에서 1 사이에 들어갈까요?'
        '<details><summary>답과 해설</summary><p>그렇게 단정할 수 없습니다. 표준화는 분포의 모양을 정규분포로 바꾸지 않습니다. 약 68.27%는 정규분포의 성질입니다.</p></details></li>'
        '<li>지역의 거래자료를 100건에서 1만 건으로 늘리면 개별 거래단가도 반드시 정규분포를 따를까요?'
        '<details><summary>답과 해설</summary><p>아닙니다. 표본수가 늘어도 개별 관측값의 분포가 정규분포로 바뀌지는 않습니다. 중심극한정리는 조건이 맞을 때 표본평균의 분포에 관한 결과입니다.</p></details></li>'
        '</ol>',
    )
    sec(
        'macro', 'CH2 Macro에서 읽기',
        '가격의 분포를 특정 확률모형으로 미리 정하지 않습니다',
        '<p>CH2 Macro의 평균, 중앙값, 분위수, 표준편차는 선택한 거래단가를 요약한 값입니다. 그 값이 있다고 해서 거래가격이 정규분포나 다른 확률분포를 따른다는 뜻은 아닙니다. 서비스가 모든 거래의 미래 가격 확률이나 보정된 상승 확률을 보여 주는 것도 아닙니다.</p>'
        '<ul>'
        '<li><strong>평균과 표준편차:</strong> 평균 100만원/㎡, 표준편차 40만원/㎡라는 숫자만으로 거래의 약 68%가 60~140에 있다고 말하지 않습니다. 정규분포라는 근거가 따로 필요합니다.</li>'
        '<li><strong>분포의 모양:</strong> 평균과 중앙값의 차이, 25%와 75%의 거리, 고가 쪽 꼬리, 특정 구간의 집중, 극단값, 집단이 섞였는지를 함께 봅니다.</li>'
        '<li><strong>확인한 단가 분포:</strong> 유료 매트릭스의 단가 분포는 구간별 거래 건수입니다. 밀도 축이 아니고, 정규분포 곡선을 겹쳐 두지 않습니다. 정규성 검정이나 로그변환 비교를 기본 화면에서 수행하지 않습니다.</li>'
        '<li><strong>집단:</strong> 일반상업지역 대지와 계획관리지역 답은 수준과 모양이 다를 수 있습니다. 너무 잘게 나누면 건수가 부족할 수 있습니다.</li>'
        '<li><strong>고가 거래:</strong> 오른쪽 꼬리를 만든다는 이유만으로 정규분포에 맞추려 빼지 않습니다. 원자료와 비교 집단을 먼저 확인합니다.</li>'
        '<li><strong>기간:</strong> 기간을 늘리면 여러 시점의 거래가 함께 들어갑니다. 건수가 늘었다는 사실만으로 더 단순한 확률분포가 되지는 않습니다. 단가 분포는 전체 기간과 연도·롤링 구간을 나눠 건수를 볼 수 있습니다.</li>'
        '<li><strong>잔차:</strong> 회귀의 잔차는 거래단가에서 예측을 뺀 값입니다. 거래단가가 정규분포가 아니라고 회귀의 모든 가정이 깨지는 것은 아니고, 거래단가가 종 모양이라고 잔차의 독립성이나 등분산이 보장되지도 않습니다.</li>'
        '<li><strong>예측확률:</strong> 이후 분류모형이 내는 확률은 관측 비율과 다릅니다. 검증에서 보정 여부를 따로 봅니다. 이번 장의 이항분포, 균등분포, 평균 100·표준편차 20 모형은 학습용이며 실제 거래 확률이 아닙니다.</li>'
        '</ul>'
        '<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>',
    )
    sec(
        'recap', '결론 · 학습 요약',
        '확률변수는 가능한 결과를, 확률분포는 그 가능성을 나타냅니다',
        '<p>이산형은 각 값의 확률을 더하고, 연속형은 밀도 아래 면적을 구합니다. 기대값과 분산은 분포의 중심과 퍼짐입니다. 관측자료가 어떤 분포를 따른다고 말하려면 모형의 조건을 확인합니다.</p>'
        '<ul class="learn-recap-list">'
        '<li><strong>확률변수:</strong> 우연한 결과에 숫자를 대응시키는 규칙입니다.</li>'
        '<li><strong>확률질량함수:</strong> 이산형에서 P(X=x)입니다.</li>'
        '<li><strong>누적분포함수:</strong> F(x)=P(X≤x)입니다.</li>'
        '<li><strong>기대값과 분산:</strong> 가능한 값을 확률로 가중한 중심과 제곱편차입니다.</li>'
        '<li><strong>이항분포:</strong> 횟수가 고정되고, 결과가 둘이며, 독립이고, 성공확률이 같을 때 씁니다.</li>'
        '<li><strong>확률밀도:</strong> 연속형에서는 높이가 아니라 구간 면적이 확률입니다.</li>'
        '<li><strong>정규분포와 z점수:</strong> 포함확률 약 68.27%·95.45%·99.73%는 정규모형의 결과입니다.</li>'
        '<li><strong>표본수:</strong> 거래가 많아져도 개별 단가가 정규분포가 되지는 않습니다. 중심극한정리는 표본평균의 분포에 관한 이야기입니다.</li>'
        '</ul>'
        '<p>다음 <a href="/learn/stats/sampling-distributions/">10장 「표본분포와 중심극한정리」</a>에서는 표본을 반복할 때 표본평균이 어떤 분포를 나타내는지 살펴봅니다. 개별 값의 분포와 여러 표본에서 계산한 평균의 분포를 구별합니다.</p>'
        '<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/4-2-mean-or-expected-value-and-standard-deviation">OpenStax, Introductory Statistics 2e §4.2</a> — 기대값과 분산.</li>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/4-3-binomial-distribution">OpenStax, Introductory Statistics 2e §4.3</a> — 이항분포.</li>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/6-1-the-standard-normal-distribution">OpenStax, Introductory Statistics 2e §6.1</a> — 표준정규분포.</li>'
        '</ul><p class="learn-source-note">참고자료 확인일: 2026-10-07. 네 그림은 교육용 가상 확률모형입니다. 공통 학습자료 30건이나 CH2 Macro의 운영 통계가 아닙니다.</p></div></details>',
    )

    page = ROOT / 'probability-distributions' / 'index.html'
    html = page.read_text(encoding='utf-8')
    article = (
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" '
        'aria-label="확률변수와 확률분포">\n' + '\n'.join(parts) + '\n</article>'
    )
    html = re.sub(r'<article.*?</article>', article, html, count=1, flags=re.S)
    html = re.sub(
        r'(name="description"\s+content=").*?("\s*/>)',
        r'\1이산·연속 확률변수, 이항분포, 균등분포, 정규분포의 확률을 가상 모형으로 계산합니다.\2',
        html, count=1, flags=re.S,
    )
    if 'probability-distributions/chapter.css' not in html:
        html = html.replace(
            'learn-reader.css?v=20261026-toc" />',
            'learn-reader.css?v=20261026-toc" />\n    <link rel="stylesheet" href="/learn/stats/probability-distributions/chapter.css?v=20261026-18" />',
        )
    html = re.sub(r'\n\s*<script type="application/json" id="pd-data">.*?</script>', '', html, flags=re.S)
    html = re.sub(
        r'\n\s*<script type="module" src="/learn/stats/probability-distributions/experiment\.js[^"]*"></script>',
        '', html,
    )
    payload = json.dumps({'probabilities': probs, 'bands': {str(z): f'{inclusion(z):.2f}%' for z in (1, 2, 3)}}, ensure_ascii=False)
    html = html.replace(
        '</body>',
        f'    <script type="application/json" id="pd-data">{payload}</script>\n'
        '    <script type="module" src="/learn/stats/probability-distributions/experiment.js?v=20261026-19"></script>\n  </body>',
    )
    assert '1단계, 심화' in html and '★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화' in html
    page.write_text(html, encoding='utf-8')

    written = page.read_text(encoding='utf-8')
    charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', written, re.S)]
    assert len(charts) == 4 and written.count('<svg ') == 4
    for bar in charts[0].findall('rect'):
        attrs = bar.attrib
        p = probs[int(attrs['data-k'])]
        assert abs(float(attrs['height']) - p * 380) < 1e-8
        assert abs(float(attrs['y']) - (245 - p * 380)) < 1e-8
    for dot in charts[1].findall('circle'):
        if 'data-cdf' in dot.attrib:
            expected = sum(probs[:int(dot.attrib['data-k']) + 1])
            assert abs(float(dot.attrib['data-cdf']) - expected) < 1e-12
            assert abs(float(dot.attrib['cy']) - (250 - expected * 180)) < 1e-8
    curve = charts[3].find('polyline')
    points = curve.attrib['points'].split()
    assert len(points) == 321 and curve.attrib['data-normal'] == 'standard'
    for i, pair in enumerate(points):
        x, y = map(float, pair.split(','))
        z = -4 + i * .025
        assert abs(x - (320 + z * 65)) < .0001 and abs(y - (245 - normal(z) * 430)) < .0001
    ids = re.findall(r'\bid="([^"]+)"', written)
    assert len(ids) == len(set(ids))
    assert written.count('<summary>답과 해설</summary>') == 5
    practice = re.search(r'<section[^>]*id="practice".*?</section>', written, re.S).group(0)
    assert not re.search(r'<details\b[^>]*\bopen', practice)
    assert '09. 확률변수와 확률분포' in written and '[그림 ' not in written
    course = json.loads((ROOT / 'course.json').read_text(encoding='utf-8'))
    items = [item for group in course for item in group['items']]
    assert next(item['macro_relevance'] for item in items if item['slug'] == 'probability-distributions') == 1
    saved = json.loads((ROOT / 'distributions-example.json').read_text(encoding='utf-8'))
    assert saved['binomial']['probabilities'] == probs
    print('chapter 09 mean', mu, 'sd', round(math.sqrt(var), 4), 'bands', [inclusion(z) for z in (1, 2, 3)])


if __name__ == '__main__':
    build()
