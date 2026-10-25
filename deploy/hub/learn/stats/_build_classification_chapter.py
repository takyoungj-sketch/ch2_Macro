"""Chapter 28: logistic probability, odds, threshold and probability scores."""
from pathlib import Path
from html import escape
import json, math, re

ROOT = Path(__file__).resolve().parent
PROBS = [.1, .2, .35, .45, .55, .65, .8, .9]
LABELS = [0, 0, 1, 0, 1, 0, 1, 1]


def confusion(threshold):
    tp = sum(y == 1 and p >= threshold for y, p in zip(LABELS, PROBS))
    fp = sum(y == 0 and p >= threshold for y, p in zip(LABELS, PROBS))
    fn = sum(y == 1 and p < threshold for y, p in zip(LABELS, PROBS))
    tn = sum(y == 0 and p < threshold for y, p in zip(LABELS, PROBS))
    precision = tp / (tp + fp)
    return dict(threshold=threshold, TP=tp, FP=fp, FN=fn, TN=tn, accuracy=(tp + tn) / 8,
                precision=precision, recall=tp / 4, specificity=tn / 4, F1=2 * tp / (2 * tp + fp + fn))


def build():
    curve = [dict(x=i / 20, p=1 / (1 + math.exp(-(-2 + .8 * i / 20)))) for i in range(101)]
    odds = [dict(before=p, after=2 * p / (1 + p)) for p in [.1, .2, .5, .8]]
    loss = [dict(p=i / 100, positive=-math.log(i / 100), negative=-math.log1p(-i / 100)) for i in range(1, 100)]
    log_loss = -sum(y * math.log(p) + (1 - y) * math.log1p(-p) for y, p in zip(LABELS, PROBS)) / 8
    brier = sum((y - p) ** 2 for y, p in zip(LABELS, PROBS)) / 8
    auc_score = sum(a > b for a, y in zip(PROBS, LABELS) if y == 1 for b, z in zip(PROBS, LABELS) if z == 0) / 16
    confusions = [confusion(.5), confusion(.3)]
    assert abs(curve[50]['p'] - .5) < 1e-12
    assert abs(1 / (1 + math.exp(2)) - .119202922) < 1e-8
    assert abs(1 / (1 + math.exp(-2)) - .880797078) < 1e-8
    assert abs(math.exp(.8) - 2.225540928) < 1e-8
    assert [round(row['after'] - row['before'], 4) for row in odds] == [.0818, .1333, .1667, .0889]
    assert confusions[0]['TP'] == 3 and confusions[0]['F1'] == .75 and confusions[0]['specificity'] == .75
    assert confusions[1]['TP'] == 4 and abs(confusions[1]['precision'] - 2 / 3) < 1e-12 and confusions[1]['F1'] == .8
    assert abs(log_loss - .4940) < 5e-5 and abs(brier - .1688) < 5e-5 and auc_score == .8125
    payload = dict(description='모든 자료는 별도 가상 예제. 시그모이드 계수는 사전 지정이며 학습으로 추정한 값이 아님.',
                   curve=curve, odds=odds, probabilities=PROBS, labels=LABELS, confusions=confusions, loss=loss,
                   log_loss=log_loss, brier=brier, AUC=auc_score)
    (ROOT / 'classification-example.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def tx(x, y, text, **attrs):
        extra = ''.join(f' {key}="{escape(str(value), quote=True)}"' for key, value in attrs.items())
        return f'<text x="{x}" y="{y}"{extra}>{escape(str(text))}</text>'

    def fig(fig_id, title, body, caption, controls='', viewbox='0 0 640 410'):
        return (f'{controls}<figure class="learn-chart learn-chart--wide cls-chart"><svg viewBox="{viewbox}" role="img" '
                f'aria-labelledby="{fig_id}-title {fig_id}-desc"><title id="{fig_id}-title">{title}</title>'
                f'<desc id="{fig_id}-desc">{caption}</desc>{body}</svg><figcaption class="learn-chart__caption">{caption}</figcaption></figure>')

    sigmoid = tx(24, 28, '가상 식: η=−2+0.8X, p=1/[1+exp(−η)]')
    sigmoid += '<line x1="70" y1="320" x2="570" y2="320" stroke="#94a3b8"/><line x1="70" y1="65" x2="70" y2="320" stroke="#94a3b8"/><line x1="70" y1="195" x2="570" y2="195" stroke="#94a3b8"/>'
    sigmoid += '<polyline points="' + ' '.join(f"{70 + row['x'] * 100},{320 - row['p'] * 250}" for row in curve) + '" fill="none" stroke="#2563eb" stroke-width="3"/>'
    sigmoid += '<line id="cls-sigmoid-guide" x1="320" y1="320" x2="320" y2="195" stroke="#0f766e" stroke-dasharray="4 3"/>'
    sigmoid += '<circle id="cls-sigmoid-point" cx="320" cy="195" r="6" fill="#2563eb"/>'
    for value in range(6):
        sigmoid += tx(65 + value * 100, 350, value)
    for value in [0, .25, .5, .75, 1]:
        sigmoid += tx(18, 325 - value * 250, value)
    sigmoid += tx(24, 385, '가로: 가상 입력 X / 세로: 양성 확률 p')
    sigmoid_controls = ('<div class="cls-controls" hidden=""><label for="cls-x">그림 1의 가상 입력 X</label>'
                        '<input id="cls-x" type="range" min="0" max="5" step="0.1" value="2.5"/>'
                        '<p id="cls-sigmoid-status" role="status" aria-live="polite"></p></div>')
    figure1 = fig('sigmoid', '로지스틱 확률곡선', sigmoid,
                   '그림 1. 계수 −2와 0.8은 설명용으로 직접 정했습니다. 이 곡선은 뒤의 8건을 적합해 얻은 결과가 아닙니다.', sigmoid_controls)

    odds_body = tx(24, 28, '오즈비 2를 적용해도 확률은 두 배가 되지 않습니다')
    odds_body += '<line x1="70" y1="320" x2="600" y2="320" stroke="#94a3b8"/>'
    for index, row in enumerate(odds):
        left = 78 + index * 135
        odds_body += f'<rect data-odds-p="{row["before"]}" x="{left}" y="{92}" width="78" height="228" fill="none"/>'
        for offset, key, color in [(0, 'before', '#94a3b8'), (36, 'after', '#2563eb')]:
            value = row[key]
            odds_body += f'<rect x="{left + offset}" y="{320 - value * 220}" width="30" height="{value * 220}" fill="{color}"/>'
            odds_body += tx(left + offset - 2, 308 - value * 220, f'{value * 100:.1f}')
        odds_body += tx(left, 348, f'시작 {row["before"] * 100:.0f}%')
    for value in [0, .5, 1]:
        odds_body += tx(18, 325 - value * 220, f'{value * 100:.0f}%')
    odds_body += tx(24, 385, '회색: 시작 확률 / 파랑: 오즈가 두 배인 뒤의 확률')
    odds_controls = ('<div class="cls-controls" hidden=""><label for="cls-p0">그림 2의 시작 확률. 오즈비는 2로 고정</label>'
                     '<input id="cls-p0" type="range" min="0.05" max="0.95" step="0.01" value="0.2"/>'
                     '<div class="cls-shortcuts">' + ''.join(f'<button type="button" data-odds-choice="{value}">{int(value * 100)}%</button>' for value in [.1, .2, .5, .8]) +
                     '</div><p id="cls-odds-status" role="status" aria-live="polite"></p></div>')
    figure2 = fig('odds', '오즈비와 확률 변화', odds_body,
                   '그림 2. p′=2p/(1+p)로 계산한 별도 예제입니다. 그림 1의 오즈비 약 2.23과는 다른 설정입니다.', odds_controls)

    matrix = tx(24, 32, '같은 가상 8건: 위는 선택한 임계값, 아래는 0.3 고정')
    for top, title, values, live in [
        (58, '선택 임계값 0.50', confusions[0], True),
        (390, '비교 기준 0.30', confusions[1], False)]:
        matrix += tx(16, top, title, id='cls-live-title' if live else 'cls-fixed-title')
        matrix += tx(118, top + 28, '음성')
        matrix += tx(210, top + 28, '양성')
        cells = [('실제 음성', 'TN', values['TN'], 'FP', values['FP']), ('실제 양성', 'FN', values['FN'], 'TP', values['TP'])]
        for row_index, (name, left_key, left_value, right_key, right_value) in enumerate(cells):
            yy = top + 40 + row_index * 86
            matrix += tx(16, yy + 42, name)
            for column, key, value in [(0, left_key, left_value), (1, right_key, right_value)]:
                matrix += f'<rect class="cls-cell" x="{108 + column * 92}" y="{yy}" width="80" height="72" fill="#dbeafe"/>'
                matrix += tx(122 + column * 92, yy + 28, key)
                number_id = f'cls-{key}' if live else f'cls-fixed-{key}'
                matrix += tx(148 + column * 92, yy + 54, value, id=number_id)
        metric = '정밀도 75% / 재현율 75%' if live else '정밀도 66.67% / 재현율 100%'
        matrix += tx(24, top + 230, metric, id='cls-live-metrics' if live else 'cls-fixed-metrics')
    matrix += tx(24, 700, '행은 실제, 열은 예측 · 칸 글자가 정오분류를 나타냅니다')
    threshold_controls = ('<div class="cls-controls" hidden=""><label for="cls-threshold">분류 임계값. 양성 판정은 예측확률 ≥ 임계값</label>'
                          '<input id="cls-threshold" type="range" min="0" max="1" step="0.05" value="0.5"/>'
                          '<div class="cls-shortcuts"><button type="button" data-threshold-choice="0.5">0.5로 복원</button>'
                          '<button type="button" data-threshold-choice="0.3">0.3과 비교</button></div>'
                          '<p id="cls-threshold-status" role="status" aria-live="polite"></p></div>')
    figure3 = fig('threshold', '임계값과 혼동행렬', matrix,
                   '그림 3. 임계값 0.5와 0.3의 정확도는 모두 75%이지만 정밀도와 재현율은 다릅니다. 이 8건으로 운영 임계값을 정하지 않습니다.', threshold_controls, '0 0 460 740')

    loss_body = tx(24, 28, '한 관측의 로그손실: 확신하며 틀리면 비용이 커집니다')
    loss_body += '<line x1="70" y1="320" x2="570" y2="320" stroke="#94a3b8"/><line x1="70" y1="65" x2="70" y2="320" stroke="#94a3b8"/>'
    for key, color in [('positive', '#2563eb'), ('negative', '#d97706')]:
        loss_body += f'<polyline data-label="{key}" points="' + ' '.join(f"{70 + row['p'] * 500},{320 - row[key] * 50}" for row in loss) + f'" fill="none" stroke="{color}" stroke-width="2"/>'
    loss_body += '<circle id="cls-loss-point" cx="520" cy="314.7" r="6" fill="#2563eb"/>'
    for value in [0, .25, .5, .75, 1]:
        loss_body += tx(58 + value * 500, 350, value)
    for value in [0, 2, 4]:
        loss_body += tx(30, 325 - value * 50, value)
    loss_body += tx(24, 385, '가로: 양성 예측확률 / 파랑 실제 양성 / 주황 실제 음성')
    loss_controls = ('<div class="cls-controls" hidden=""><label for="cls-loss-p">한 관측의 양성 예측확률. 표시 구간 0.01~0.99</label>'
                     '<input id="cls-loss-p" type="range" min="0.01" max="0.99" step="0.01" value="0.9"/>'
                     '<div class="cls-shortcuts"><button type="button" data-loss-y="1" aria-pressed="true">실제 양성</button>'
                     '<button type="button" data-loss-y="0" aria-pressed="false">실제 음성</button></div>'
                     '<p id="cls-loss-status" role="status" aria-live="polite"></p></div>')
    figure4 = fig('loss', '로그손실 곡선', loss_body,
                   '그림 4. 자연로그를 사용하고 p=0.01~0.99만 그렸습니다. 실제 양성에 p→0이거나 실제 음성에 p→1이면 로그손실은 무한히 커집니다.', loss_controls)

    def rate_row(name, key, digits=2):
        left = confusions[0][key] * 100
        right = confusions[1][key] * 100
        return f'<tr><th scope="row">{name}</th><td>{left:.{digits}f}%</td><td>{right:.{digits}f}%</td></tr>'

    observations = ''.join(
        f'<li>관측 {index} · 예측확률 {p:.2f} · 실제 {"양성" if y else "음성"} · 임계값 0.5에서 예측 {"양성" if p >= .5 else "음성"}</li>'
        for index, (p, y) in enumerate(zip(PROBS, LABELS), start=1))
    parts = []

    def sec(sec_id, label, title, body):
        parts.append(f'<section class="learn-chapter__step" id="{sec_id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')

    sec('quick-start', '서두 · 학습목표', '가격을 예측하는 것과 어떤 사건이 발생할 확률을 예측하는 것은 다릅니다',
        '<p>지금까지 살펴본 회귀분석은 주로 거래금액이나 거래단가처럼 숫자로 나타나는 결과를 다루었습니다. 예측하려는 결과가 두 가지 범주 중 하나라면, 예를 들어 사전에 정한 가격 기준을 넘었는지 또는 특정 유형에 해당하는지를 구별하는 문제가 됩니다. 이런 문제를 분류라고 합니다.</p>'
        '<p>가장 단순한 형태는 결과가 두 가지인 이진 분류입니다. Y=1을 양성, Y=0을 음성이라고 부르지만, 양성이 좋은 상태라는 뜻은 아닙니다. 분석자가 관심 대상으로 정한 범주입니다. 로지스틱 회귀는 그 범주에 속할 확률을 추정하고, 그다음 별도의 기준으로 양성인지 음성인지 판정할 수 있습니다. 확률을 계산하는 단계와 범주를 판정하는 단계는 다릅니다.</p>'
        '<ul class="learn-objectives"><li>회귀와 분류, 그리고 시그모이드로 만드는 조건부 양성 확률을 이해합니다.</li><li>확률·오즈·로그오즈·오즈비를 구별합니다.</li><li>최대우도추정과 로그손실, 완전 분리의 의미를 알아봅니다.</li><li>분류 임계값과 혼동행렬, 정확도·정밀도·재현율·특이도·F1을 구별합니다.</li><li>로그손실·브라이어 점수·AUC·확률 보정의 역할을 이해합니다.</li></ul>')
    sec('sigmoid', '로지스틱 회귀', '0과 1의 결과를 확률로 표현합니다',
        '<p>선형회귀의 Ŷ=β₀+β₁X는 −0.2나 1.3처럼 0과 1 바깥으로 나갈 수 있습니다. 그 값을 그대로 확률로 읽을 수는 없습니다. 로지스틱 회귀는 먼저 선형 예측값 η=β₀+β₁X₁+⋯+βₖXₖ를 계산하고, 시그모이드 함수 p(X)=P(Y=1∣X)=1/[1+exp(−η)]에 넣습니다. 유한한 η에서 이 값은 0과 1 사이이며 정확히 0이나 1이 되지는 않습니다.</p>'
        '<p>설명용으로 η=−2+0.8X를 직접 정하면, X=0에서 η=−2이고 양성 확률은 약 0.1192입니다. X=2.5에서는 η=0이므로 확률은 0.5입니다. X=5에서는 η=2이고 확률은 약 0.8808, 즉 약 88.1%입니다.</p>'
        + figure1 +
        '<p>X가 커지면 확률은 높아지지만 증가 속도는 일정하지 않습니다. 확률이 0이나 1에 가까워질수록 곡선은 완만해집니다. 로지스틱 회귀는 X가 1 증가할 때 확률이 일정한 크기만큼 증가하는 모형이 아닙니다. 계수 0.8을 확률이 0.8만큼, 또는 80%p 증가한다는 뜻으로 읽지 않습니다.</p>'
        '<details class="learn-more"><summary>확률식 자세히 보기</summary><div class="learn-more__body"><p>p(X)=1/[1+exp(−η)]이고 η=β₀+β₁X₁+⋯+βₖXₖ입니다. 다른 변수를 고정한 연속형 Xⱼ의 확률 기울기는 βⱼp(1−p)입니다. p가 바뀌면 기울기도 바뀝니다.</p></div></details>')
    sec('odds', '확률과 오즈', '같은 사건을 서로 다른 방식으로 표현할 수 있습니다',
        '<p>오즈는 사건이 발생할 확률을 발생하지 않을 확률로 나눈 p/(1−p)입니다. 양성 확률 0.5의 오즈는 1이고, 0.8의 오즈는 4입니다. 오즈 4는 양성의 오즈가 음성의 4배라는 뜻이지 양성 확률이 4라는 뜻은 아닙니다.</p>'
        '<div class="cls-scroll"><table class="cls-metrics"><caption>양성 확률과 오즈</caption><thead><tr><th scope="col">양성 확률 p</th><th scope="col">오즈 p/(1−p)</th></tr></thead><tbody>'
        '<tr><td>0.20</td><td>0.25</td></tr><tr><td>0.50</td><td>1</td></tr><tr><td>0.80</td><td>4</td></tr><tr><td>0.90</td><td>9</td></tr></tbody></table></div>'
        '<p>확률은 0과 1 사이이고, 오즈는 0보다 큰 값입니다. 확률이 1에 가까워지면 오즈는 매우 커집니다.</p>')
    sec('logit', '로그오즈와 계수', '로지스틱 회귀는 로그오즈를 선형식으로 표현합니다',
        '<p>로그오즈는 오즈의 자연로그인 logit(p)=ln[p/(1−p)]입니다. 로지스틱 회귀는 logit(p)=β₀+β₁X₁+⋯+βₖXₖ를 가정합니다. 다른 설명변수를 고정하고 상호작용이 없으면 X₁이 1 증가할 때 로그오즈는 β₁만큼 증가하고, 오즈는 exp(β₁)배가 됩니다. 이 배수를 오즈비라고 합니다.</p>'
        '<p>그림 1의 기울기 0.8에서는 오즈비가 exp(0.8)≈2.226입니다. X가 1 증가하면 양성의 오즈가 약 2.23배가 되는 관계입니다. 양성 확률이 2.23배가 되거나, 223% 증가하거나, 0.8만큼 증가한다는 뜻은 아닙니다. 오즈비와 확률비는 다른 값입니다. 관찰자료의 오즈비를 인과효과로 읽으려면 별도의 연구 설계와 가정이 필요합니다.</p>'
        '<details class="learn-more"><summary>조건부 오즈비와 확률 기울기</summary><div class="learn-more__body"><p>상호작용이 없으면 ORⱼ=exp(βⱼ)이고, 연속형 변수의 확률 기울기는 ∂p/∂Xⱼ=βⱼp(1−p)입니다. 상호작용이 있으면 한 변수의 오즈비는 다른 변수의 값에 따라 달라질 수 있습니다. 조건부 오즈비와 전체 집단에서 계산한 단순 오즈비도 서로 다를 수 있습니다.</p></div></details>')
    sec('odds-change', '오즈비와 확률 변화', '시작 확률에 따라 퍼센트포인트 변화가 달라집니다',
        '<p>이번에는 그림 1과 별도로, 오즈비가 정확히 2인 경우를 봅니다. 시작 확률이 p이면 새 확률은 p′=2p/(1+p)입니다.</p>'
        '<div class="cls-scroll"><table class="cls-metrics"><caption>오즈비 2의 확률 변화. %p는 퍼센트포인트</caption><thead><tr><th scope="col">시작 확률</th><th scope="col">오즈가 두 배가 된 후</th><th scope="col">확률 변화</th></tr></thead><tbody>'
        '<tr><td>10%</td><td>18.18%</td><td>+8.18%p</td></tr><tr><td>20%</td><td>33.33%</td><td>+13.33%p</td></tr><tr><td>50%</td><td>66.67%</td><td>+16.67%p</td></tr><tr><td>80%</td><td>88.89%</td><td>+8.89%p</td></tr></tbody></table></div>'
        + figure2 +
        '<p>네 경우 모두 오즈는 두 배가 되었지만 확률의 변화량은 다릅니다. 시작 확률이 중간일 때 퍼센트포인트 변화가 더 클 수 있습니다. 사건이 매우 드물면 오즈비가 확률비에 가까워질 수 있지만, 사건이 흔하면 차이가 커질 수 있습니다. 확률비 또는 위험비는 두 확률의 비율이고 오즈비는 두 오즈의 비율입니다.</p>')
    sec('fit', '학습 방법', '관측된 0과 1의 확률을 크게 만드는 계수를 찾습니다',
        '<p>선형회귀에서 자주 쓰는 최소제곱법과 달리, 로지스틱 회귀의 대표적 방법은 최대우도추정입니다. 실제 Y가 1이면 p가 클수록, Y가 0이면 1−p가 클수록 그 관측과 잘 맞습니다. 관측별 베르누이 우도는 Lᵢ=pᵢʸⁱ(1−pᵢ)¹⁻ʸⁱ이고, 독립 관측의 로그우도는 각 관측의 yᵢln pᵢ+(1−yᵢ)ln(1−pᵢ)를 더한 값입니다.</p>'
        '<p>최대우도추정은 이 로그우도를 가장 크게 만드는 계수를 찾습니다. 평균 음의 로그우도인 로그손실을 최소화하는 과정과 같습니다. 일반적인 로지스틱 회귀는 한 번의 닫힌 해보다 수치 최적화를 사용합니다. 결과 Y가 정규분포를 따른다고 가정하지 않습니다. Y는 0 또는 1인 조건부 베르누이 결과입니다. 대신 로그오즈의 함수 형태, 관측의 독립성과 표집 구조를 검토합니다.</p>'
        '<p>설명변수만으로 양성과 음성이 완전히 나뉘면 완전 분리라고 합니다. 벌점이 없는 최대우도에서는 일부 계수가 유한한 값으로 수렴하지 않을 수 있습니다. 계수가 지나치게 크거나 최적화가 수렴하지 않으면 분리, 희소 범주, 공선성과 수렴 상태를 확인합니다. 릿지 같은 규제를 검토할 수 있지만, 규제가 모든 자료 문제를 자동으로 해결하지는 않습니다.</p>'
        '<details class="learn-more"><summary>우도식 자세히 보기</summary><div class="learn-more__body"><p>ℓ(β)=Σ[yᵢln pᵢ+(1−yᵢ)ln(1−pᵢ)]입니다. 로그손실은 이 값의 평균에 음의 부호를 붙인 것입니다. 조건부 분산은 p(1−p)입니다.</p></div></details>')
    sec('threshold', '분류 임계값과 혼동행렬', '확률이 0.5보다 높아야 양성인 것은 아닙니다',
        '<p>확률을 양성 또는 음성으로 바꾸려면 분류 임계값이 필요합니다. 임계값 0.5라면 p≥0.5를 양성, p&lt;0.5를 음성으로 볼 수 있습니다. 0.5가 모든 문제의 가장 좋은 기준은 아닙니다. 양성을 놓치는 손실과 음성을 양성으로 잘못 판정하는 손실이 다를 수 있기 때문입니다.</p>'
        '<p>아래 8건의 예측확률과 실제 Y는 계산 원리를 보이려고 직접 정한 값입니다. 그림 1의 계수를 적합해 얻은 확률이 아닙니다.</p>'
        '<div class="cls-scroll"><table class="cls-metrics"><caption>가상 확률 8건</caption><thead><tr><th scope="col">관측</th><th scope="col">양성 예측확률</th><th scope="col">실제 Y</th></tr></thead><tbody>'
        + ''.join(f'<tr><td>{i}</td><td>{p:.2f}</td><td>{y}</td></tr>' for i, (p, y) in enumerate(zip(PROBS, LABELS), start=1))
        + '</tbody></table></div>' + figure3 +
        '<p id="cls-undefined" hidden="">양성으로 예측한 관측이 없으면 정밀도의 분모가 0이므로 정밀도는 정의되지 않습니다. 이 화면은 그 값을 0으로 바꾸지 않습니다.</p>'
        '<ul class="cls-observations" id="cls-observations">' + observations + '</ul>'
        '<p>TP는 실제 양성을 양성으로 판정한 경우, FP는 실제 음성을 양성으로 잘못 판정한 경우, FN은 실제 양성을 놓친 경우, TN은 실제 음성을 음성으로 판정한 경우입니다.</p>'
        '<div class="cls-scroll"><table class="cls-metrics"><caption>같은 8건에서 임계값만 바꾼 결과</caption><thead><tr><th scope="col">평가 항목</th><th scope="col">임계값 0.5</th><th scope="col">임계값 0.3</th></tr></thead><tbody>'
        '<tr><th scope="row">TP</th><td>3</td><td>4</td></tr><tr><th scope="row">FP</th><td>1</td><td>2</td></tr><tr><th scope="row">FN</th><td>1</td><td>0</td></tr><tr><th scope="row">TN</th><td>3</td><td>2</td></tr>'
        + rate_row('정확도', 'accuracy') + rate_row('정밀도', 'precision') + rate_row('재현율', 'recall') + rate_row('특이도', 'specificity') + rate_row('F1', 'F1')
        + '</tbody></table></div>'
        '<p>임계값을 0.3으로 낮추면 이 예제에서는 양성 4건을 모두 찾지만, 오탐은 1건에서 2건으로 늘어납니다. 정확도는 두 기준 모두 75%입니다. 정확도가 같아도 업무에서 보는 분류 결과는 다를 수 있습니다. 0.3이 이 8건에서 재현율이 높다는 이유만으로 모든 문제에 더 적절한 임계값이라고 말하지 않습니다.</p>')
    sec('metrics', '분류 평가', '정확도와 정밀도, 재현율은 서로 다른 질문에 답합니다',
        '<ul><li>정확도 (TP+TN)/(TP+FP+FN+TN): 전체 가운데 맞게 분류한 비율입니다.</li>'
        '<li>정밀도 TP/(TP+FP): 양성이라고 판정한 대상 가운데 실제 양성의 비율입니다.</li>'
        '<li>재현율 TP/(TP+FN): 실제 양성 가운데 찾아낸 비율입니다. 민감도라고도 합니다.</li>'
        '<li>특이도 TN/(TN+FP): 실제 음성 가운데 음성으로 맞힌 비율입니다.</li>'
        '<li>F1 2TP/(2TP+FP+FN): 정밀도와 재현율의 조화평균입니다. TN을 직접 반영하지 않습니다.</li></ul>'
        '<p>어떤 지표를 중시할지는 무엇을 양성으로 정했는지, 그리고 어떤 오류가 중요한지에 따라 달라집니다. 양성이라고 예측한 관측이 하나도 없으면 정밀도의 분모가 0이라 그 비율은 정의되지 않습니다. 어떤 프로그램은 이 경우를 0으로 보여 주기도 하므로 처리 규칙을 확인합니다. F1의 분모가 0일 때도 같은 방식으로 확인합니다.</p>'
        '<details class="learn-more"><summary>불균형 자료의 정확도</summary><div class="learn-more__body"><p>22장의 예처럼 100건 중 양성이 10건이고 음성이 90건일 때 모든 관측을 음성으로 판정하면 정확도는 90%이지만 재현율은 0%입니다. 양성 비율이 크게 다르면 정확도만으로 모형을 평가하기 어렵습니다. 양성을 놓치는 비용이 크면 재현율을, 오탐 비용이 크면 정밀도나 특이도를 더 볼 수 있습니다. 평가자료의 양성 비율이 바뀌면 같은 모형에서도 정밀도가 달라질 수 있습니다.</p></div></details>')
    sec('loss', '확률의 품질', '범주를 맞혔다는 사실만으로 확률이 정확하다고 보지 않습니다',
        '<p>실제 양성인 관측에 0.55를 예측한 경우와 0.99를 예측한 경우는, 임계값 0.5에서 둘 다 양성으로 판정됩니다. 정오분류는 같지만 모형이 얼마나 확신하는지는 다릅니다. 확률 자체를 보는 대표 지표가 로그손실과 브라이어 점수입니다. 둘 다 낮을수록 좋습니다.</p>'
        '<p>로그손실은 −(1/n)Σ[yᵢln pᵢ+(1−yᵢ)ln(1−pᵢ)]입니다. 실제 양성에 0.9를 주면 그 관측의 손실은 −ln(0.9)≈0.105이고, 0.1을 주면 −ln(0.1)≈2.303입니다. 확신하면서 반대 결과를 예측하면 손실이 크게 늘어납니다. 실제 양성인데 p=0이거나 실제 음성인데 p=1이면 수학적으로 로그손실은 무한대입니다. 프로그램이 확률을 아주 작은 양수와 1보다 작은 수 사이로 제한한다면 그 규칙을 확인합니다.</p>'
        + figure4 +
        '<p>브라이어 점수는 (1/n)Σ(yᵢ−pᵢ)²입니다. 실제 1에 확률 0.8을 주면 제곱오차는 0.04이고, 0.2를 주면 0.64입니다. 같은 가상 8건의 평균 로그손실은 약 0.4940, 브라이어 점수는 약 0.1688입니다.</p>'
        '<div class="cls-scroll"><table class="cls-metrics"><caption>가상 8건의 확률 점수</caption><thead><tr><th scope="col">지표</th><th scope="col">결과</th></tr></thead><tbody>'
        f'<tr><th scope="row">로그손실</th><td>{log_loss:.4f}</td></tr><tr><th scope="row">브라이어 점수</th><td>{brier:.4f}</td></tr></tbody></table></div>'
        '<p>두 지표는 서로 다른 손실이므로 0.49와 0.17의 크기만으로 우열을 정하지 않습니다. 예측확률이 같다면 분류 임계값만 바꿔도 두 값은 변하지 않습니다. 분류 판정의 성능과 확률 예측의 성능은 따로 평가합니다.</p>')
    sec('ranking', 'ROC와 확률 보정', '순서를 잘 매기는 것과 확률의 수준이 맞는 것은 다릅니다',
        f'<p>ROC 곡선은 임계값을 바꾸며 재현율(진양성률)과 위양성률 FP/(FP+TN)를 함께 봅니다. 곡선 아래 면적인 ROC-AUC는 양성 관측에 음성 관측보다 높은 점수를 주는 능력과 관련됩니다. 이 가상 자료는 양성 4건, 음성 4건이라 비교쌍이 16쌍입니다. 양성에 더 높은 확률을 준 쌍이 13쌍이므로 AUC=13/16=0.8125입니다. 같은 점수인 동점이 있으면 그 쌍은 0.5로 세며, 이번 8건에는 동점이 없습니다.</p>'
        '<p>AUC 0.8125는 관측의 81.25%를 맞게 판정했다는 뜻도, 예측확률 0.8이 실제 발생률 80%와 같다는 뜻도 아닙니다. AUC는 순위에 관한 성능입니다. PR 곡선은 정밀도와 재현율의 관계이며, 양성이 드문 문제에서 ROC와 함께 볼 수 있습니다. 정밀도는 실제 양성 비율의 영향을 받으므로 양성 비율이 다른 자료의 PR 성능을 조건 없이 비교하지 않습니다.</p>'
        '<p>확률 보정은 약 70%로 예측한 대상을 충분히 많이 모았을 때 실제 양성이 약 70% 나타나는 성질입니다. 순서는 잘 매기면서 모든 확률을 실제보다 높게 낼 수 있고, 그때는 AUC가 높아도 보정은 좋지 않을 수 있습니다. 보정이 양호해도 개별 순서가 잘 나뉜다고 보장되지는 않습니다. 구간별 관측수가 적으면 실제 양성 비율의 불확실성이 큽니다. 8건만으로 보정을 판단하지 않습니다. 보정 방법을 학습하거나 고를 때도 검증자료와 시험자료의 경계를 지킵니다.</p>')
    sec('decision', '임계값의 선택', '잘 보정된 확률과 업무 비용을 함께 고려합니다',
        '<p>확률모형을 만드는 과정과 그 확률로 의사결정하는 과정은 구분합니다. 오분류 비용만 보고, 확률이 잘 보정되어 있으며 그 밖의 제약이나 추가 비용이 없다는 단순한 조건에서는 t=C_FP/(C_FP+C_FN)을 생각할 수 있습니다. 양성 누락 비용이 오탐 비용보다 크면 임계값을 낮추는 쪽이 합리적일 수 있습니다.</p>'
        '<p>이 식은 모든 분류 업무의 보편적인 최적 기준이 아닙니다. 실제로는 비용을 금액으로 정하기 어렵고, 양성 비율, 검토할 수 있는 건수, 판정 뒤의 조치 비용도 영향을 줍니다. 임계값은 검증자료에서 정하고, 시험자료 점수에 반복해서 맞추지 않습니다. 0.5를 무조건 쓰거나 이 8건에서 점수가 좋은 값을 그대로 운영에 옮기지 않습니다.</p>'
        '<details class="learn-more"><summary>비용 공식의 조건</summary><div class="learn-more__body"><p>C_FN은 양성을 음성으로 놓치는 비용, C_FP는 음성을 양성으로 판정하는 비용입니다. 확률이 보정되어 있지 않거나 검토 건수 제한이 있으면 이 임계값을 그대로 적용하지 않습니다.</p></div></details>')
    sec('extensions', '변수, 누수, 불균형', '목표 범주를 먼저 정하고 평가자료의 경계를 지킵니다',
        '<p>로지스틱 회귀에도 면적, 건축연도, 층, 용도지역 더미, 도로 조건, 상호작용처럼 여러 설명변수를 넣을 수 있습니다. 계수는 함께 넣은 변수를 고정한 조건부 오즈비입니다. 결과 범주가 셋 이상이면 이진 로지스틱을 그대로 쓰기보다 다항 로지스틱 등을 검토합니다. 여러 라벨이 동시에 가능한 다중 라벨 문제는 서로 배타적인 다중 범주와 다릅니다. 모형을 만들기 전에 목표 범주가 무엇이며 서로 배타적인지 정합니다.</p>'
        '<p>분류에도 23장과 26장의 데이터 누수가 적용됩니다. 전체 자료를 먼저 표준화하거나 전체 라벨로 변수를 고른 뒤 교차검증하면 평가정보가 학습에 들어갈 수 있습니다. 실제 거래금액으로 만든 범주를 예측하면서 같은 거래의 거래금액을 입력에 넣지 않습니다. 양성 관측을 늘리거나 클래스 가중치를 주는 재표집은 학습자료 안에서 합니다. 평가자료까지 인위적으로 맞춘 정확도와 정밀도를 실제 양성 비율의 운영 성능으로 읽지 않습니다. 학습 중 클래스 비율이 바뀌면 출력 확률의 보정 상태도 달라질 수 있으므로, 확률을 쓸 때는 목적에 맞는 분포의 검증자료에서 보정까지 확인합니다.</p>'
        '<p>부동산 자료에서는 같은 단지의 반복 거래, 지역 특성, 거래시점의 변화도 평가 구성에 반영합니다. 어떤 새로운 거래와 시장에 적용할 것인지에 맞춰 평가자료를 만듭니다.</p>')
    sec('practice', '확인 문제', '확률과 오즈, 판정 결과를 구별하세요',
        '<ol class="learn-exercises">'
        '<li>오즈비가 2라면 양성 확률도 두 배로 증가할까요?<details><summary>답과 해설</summary><p>아닙니다. 시작 확률이 p이면 새 확률은 p′=2p/(1+p)입니다. 시작 확률에 따라 퍼센트포인트 변화량이 달라집니다.</p></details></li>'
        '<li>같은 확률모형에서 임계값을 0.5에서 0.3으로 낮추면 로그손실도 변할까요?<details><summary>답과 해설</summary><p>예측확률 자체가 같다면 변하지 않습니다. 임계값은 확률을 범주로 바꾸는 기준이고, 로그손실은 확률 자체를 평가합니다.</p></details></li>'
        '<li>AUC가 높으면 예측확률 80%가 실제 발생확률 80%와 일치한다고 볼 수 있을까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. AUC는 양성과 음성의 순위 구분입니다. 예측확률이 실제 발생 비율과 맞는지는 확률 보정으로 따로 확인합니다.</p></details></li>'
        '<li>로지스틱 회귀에서 양성과 음성이 완벽하게 분리되면 항상 안정적인 계수를 얻을까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 완전 분리에서는 비규제 최대우도 계수가 유한한 값으로 수렴하지 않을 수 있습니다. 수렴 상태와 자료 구조를 확인하고, 필요하면 규제 등 적절한 추정 방법을 검토합니다.</p></details></li>'
        '</ol>')
    sec('macro', 'CH2 Macro에서 읽기', '분류 결과를 해석할 때는 무엇을 양성으로 정했는지 먼저 확인하세요',
        '<p>CH2 Macro는 부동산 거래자료로 가격 구조와 시장의 특징을 살펴봅니다. 이번 장의 로지스틱 회귀와 분류 지표는 특정 범주에 속할 확률을 이해하는 학습 내용입니다. 거래가 정한 기준을 넘는지, 특정 유형에 해당하는지를 목표로 삼을 수는 있지만, 그 기능이 현재 회귀분석과 모형추천 화면에 구현되어 있다는 뜻은 아닙니다.</p>'
        '<p>양성의 정의에 따라 같은 확률도 다른 대상이 됩니다. 사건이 발생한 뒤에야 알 수 있는 정보, 특히 예측하려는 거래금액 자체를 입력에 넣으면 데이터 누수가 됩니다. 계수는 확률 변화량이 아니라 로그오즈의 변화량이고, 오즈비는 확률비나 인과효과와 같지 않습니다. 분류 정확도만으로 확률이 보정되었다고 보지 않으며, 임계값은 누락과 오탐의 비용과 목적에 따라 정합니다.</p>'
        '<p>이번 계산을 개별 부동산의 감정평가상 적정가격이나 투자 성과가 보장되는 확률로 읽지 않습니다. 분류를 보더라도 무엇을 예측한 확률이며 어떤 자료와 조건에서 추정했는지를 확인합니다.</p>'
        '<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>'
        '<details class="learn-more"><summary>확인한 서비스 범위</summary><div class="learn-more__body"><p>backend/app와 토지·복합·집합 주거 프론트에서 logistic, sigmoid, log loss, Brier, ROC-AUC에 해당하는 분류모형 구현은 확인하지 못했습니다. 용도지역이나 유형을 나누는 명칭은 이 장의 로지스틱 분류와 다릅니다. 이진 분류, 양성 확률, 임계값, 혼동행렬, 정밀도·재현율·F1, ROC, 로그손실, 브라이어 점수, 확률 보정, 클래스 가중치를 현재 회귀·모형추천이 제공한다고 소개하지 않습니다. 학습 예제의 표준화와 분할도 서비스의 검증 정책을 대체하지 않습니다.</p></div></details>')
    sec('recap', '결론 · 학습 요약', '확률을 추정하는 것과 그 확률로 판단하는 것은 다릅니다',
        '<p>로지스틱 회귀는 선형 예측값을 시그모이드로 바꾸어 양성 확률을 구합니다. 계수와 오즈비를 확률의 고정된 변화로 읽지 않습니다. 확률을 범주로 바꿀 때는 별도의 임계값이 필요합니다.</p>'
        '<ul class="learn-recap-list"><li>이진 분류는 미리 정한 두 범주 중 하나를 다룹니다.</li><li>로지스틱 회귀는 로그오즈를 설명변수의 선형식으로 표현합니다.</li><li>시그모이드는 선형 예측값을 0과 1 사이 확률로 바꿉니다.</li><li>오즈비는 계수의 지수이며 확률비와 다릅니다.</li><li>최대우도추정은 관측된 결과의 확률을 크게 만드는 계수를 찾습니다.</li><li>임계값과 혼동행렬은 판정 결과를, 로그손실과 브라이어 점수는 확률을 평가합니다.</li><li>AUC의 순위 성능과 확률 보정은 다릅니다.</li><li>분류에서도 학습자료와 평가자료의 경계를 지킵니다.</li></ul>'
        '<p>다음 <a href="/learn/stats/knn/">29장 「최근접 이웃과 변수의 스케일」</a>에서는 비슷한 관측값을 찾는 거리 기반 방법과 변수의 측정 단위가 결과에 미치는 영향을 알아보겠습니다.</p>'
        '<details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul>'
        '<li><a href="https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression">scikit-learn: Logistic regression</a></li>'
        '<li><a href="../classification-example.json">가상 확률·혼동행렬·손실 계산 자료</a></li></ul>'
        '<p class="learn-source-note">모든 그림과 숫자는 별도 가상 예제입니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')

    page = ROOT / 'classification' / 'index.html'
    html = page.read_text(encoding='utf-8')
    html = re.sub(r'<article.*?</article>', '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="분류와 로지스틱 회귀">' + '\n'.join(parts) + '</article>', html, count=1, flags=re.S)
    html = re.sub(r'(name="description"\s+content=").*?("\s*/>)', r'\1로지스틱 확률·오즈비·임계값과 혼동행렬, 로그손실·AUC·확률 보정을 예제로 학습합니다.\2', html, count=1, flags=re.S)
    html = html.replace('aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span>', 'aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>')
    if 'classification/chapter.css' not in html:
        html = html.replace('</head>', '<link rel="stylesheet" href="/learn/stats/classification/chapter.css?v=20261025-4" /></head>')
    html = html.replace('classification/chapter.css?v=20261025-3', 'classification/chapter.css?v=20261025-4')
    if 'id="cls-data"' not in html:
        html = html.replace('</body>', '<script type="application/json" id="cls-data">' + json.dumps({'probabilities': PROBS, 'labels': LABELS}, ensure_ascii=False) + '</script>\n</body>')
    if 'classification/experiment.js' not in html:
        html = html.replace('</body>', '<script type="module" src="/learn/stats/classification/experiment.js?v=20261025-3"></script></body>')
    if '[그림 ' in html:
        raise SystemExit('figure placeholder remains')
    page.write_text(html, encoding='utf-8')
    block = '"slug": "classification",\n        "title": "분류와 로지스틱 회귀",\n        "soon": false,\n        "macro_relevance": 1'
    replacement = block.replace('"macro_relevance": 1', '"macro_relevance": 2')
    for path in [ROOT / 'course.json', ROOT / 'learn-stats-toc.js']:
        text = path.read_text(encoding='utf-8')
        if block in text:
            path.write_text(text.replace(block, replacement, 1), encoding='utf-8')
    home = ROOT / 'index.html'
    home_text = home.read_text(encoding='utf-8')
    home_old = 'data-macro-relevance="1"><a href="/learn/stats/classification/">28. 분류와 로지스틱 회귀 <span class="learn-relevance" aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span></span>'
    home_new = home_old.replace('data-macro-relevance="1"', 'data-macro-relevance="2"').replace('1단계, 심화', '2단계, 권장').replace('★☆☆', '★★☆')
    if home_old in home_text:
        home.write_text(home_text.replace(home_old, home_new, 1), encoding='utf-8')
    print(f'log_loss={log_loss:.6f} brier={brier:.6f} auc={auc_score:.4f} or={math.exp(.8):.4f}')


if __name__ == '__main__':
    build()
