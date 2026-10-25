"""Chapter 32: reading statistical results, with the shared example kept intact."""
from pathlib import Path
from statistics import mean, median, stdev
from html import escape
import json
import math
import re
from scipy.stats import t, linregress

ROOT = Path(__file__).resolve().parent


def build():
    rows = json.loads((ROOT / 'example-data.json').read_text(encoding='utf-8'))['rows']
    y = [row['price'] for row in rows]
    x = [row['area'] for row in rows]

    def evaluate(train, test):
        fit = linregress([row['area'] for row in train], [row['price'] for row in train])
        return mean(abs(row['price'] - (fit.intercept + fit.slope * row['area'])) for row in test)

    fit = linregress(x, y)
    mu = mean(y)
    half = float(t.ppf(0.975, 29)) * stdev(y) / math.sqrt(30)
    errs = [
        evaluate(rows, rows),
        evaluate(rows[:20], rows[20:]),
        mean(evaluate(rows[:i] + rows[i + 10:], rows[i:i + 10]) for i in [0, 10, 20]),
    ]
    effects = [
        dict(label='A: 작은 효과·좁은 구간', estimate=0.2, low=0.1, high=0.3),
        dict(label='B: 큰 추정·넓은 구간', estimate=2, low=-1, high=5),
        dict(label='C: 작고 불확실', estimate=0, low=-0.5, high=0.5),
    ]
    payload = dict(
        source='공통 30개 관측: 출처 미확인 학습 자료. 효과 크기 패널은 별도 가상 예제.',
        mean=mu, median=median(y), mean_ci=[mu - half, mu + half],
        slope=fit.slope, intercept=fit.intercept, r_squared=fit.rvalue ** 2,
        mae=errs, area_range=[min(x), max(x)], effects=effects,
    )
    ymin = min(y)
    assert median(y) == 122 and abs(mu - 146.33333333333334) < 1e-9
    assert abs((mu - half) - 115.89003791982441) < 1e-9 and abs((mu + half) - 176.77662874684228) < 1e-9
    assert abs(fit.intercept - 232.5090245256157) < 1e-9 and abs(fit.slope + 0.6842961185199762) < 1e-12
    assert abs(fit.rvalue ** 2 - 0.4213409676262018) < 1e-12
    assert [round(value, 2) for value in errs] == [38.16, 41.08, 39.85]
    assert min(x) == 22 and max(x) == 310 and ymin == 62
    pred = lambda value: fit.intercept + fit.slope * value
    assert abs(pred(0) - fit.intercept) < 1e-12
    assert round(pred(310), 2) == 20.38 and round(pred(0), 2) == 232.51
    (ROOT / 'reading-results-example.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    steps = [
        dict(title='1. 질문', short='무엇을 알고 싶은가?', ask='기술통계, 추론, 예측, 인과 가운데 무엇을 알고 싶은가?', mistake='평균 차이를 원인이나 미래 예측으로 바로 읽습니다.', rule='질문이 정해지지 않으면 결론의 종류를 정하지 않습니다.', review='04장 평균, 12장 구간, 22장 지도·비지도, 25장 예측오차'),
        dict(title='2. 자료', short='누구를 언제 관측했는가?', ask='지역·기간·유형, 관측 단위, 원래 표본수와 유효 표본수, 결측·중복·이상치 처리는 무엇인가?', mistake='제외된 관측을 빼고도 원래 시장 전체를 대표한다고 말합니다.', rule='빠진 자료의 특성을 보고 말할 수 있는 범위를 줄입니다.', review='02장 표본, 07장 이상치'),
        dict(title='3. 방법', short='어떻게 계산했는가?', ask='어떤 기법, 변수, 변환, 가정을 썼고 전처리는 어느 자료에서 정했는가?', mistake='R²나 p값만 보고 가정이 맞다고 봅니다.', rule='방법과 학습에만 쓴 전처리를 결과 숫자와 분리합니다.', review='17장 회귀, 26장 교차검증, 27장 규제'),
        dict(title='4. 결과', short='어떤 숫자가 나왔는가?', ask='추정치의 크기, 구간, 잔차, 어느 자료의 예측오차인가?', mistake='학습 적합도를 새 자료의 성능으로 부릅니다.', rule='크기와 불확실성, 학습 오차와 검증 오차를 따로 읽습니다.', review='13장 검정, 21장 구간, 25장 오차'),
        dict(title='5. 적용', short='어디까지 말할 수 있는가?', ask='다른 지역·시점, 관측 밖, 인과나 개별 적정가격으로 넓혀도 되는가?', mistake='식이 계산된다는 이유로 적용 범위를 확정합니다.', rule='근거가 없는 확장은 보류하고 한계를 문장에 남깁니다.', review='23장 분할, 24장 일반화'),
    ]
    procedures = [
        dict(name='재대입', train='30건 전체', test='같은 30건', n=30, fits=1, mae=errs[0], note='학습에 쓴 자료를 다시 평가한 값입니다. 새 자료의 성능이 아닙니다.'),
        dict(name='홀드아웃', train='1~20번', test='21~30번', n=10, fits=1, mae=errs[1], note='번호 블록이며 거래 시점이 아닙니다. 미래 검증으로 읽지 않습니다.'),
        dict(name='번호 블록 3폴드', train='각 폴드에서 나머지 20건', test='각 폴드의 10건', n=30, fits=3, mae=errs[2], note='폴드 크기가 같아 폴드 MAE의 평균과 합친 OOF MAE가 같습니다. 세 막대의 우열이 아닙니다.'),
    ]
    page_data = dict(
        steps=steps, effects=effects, procedures=procedures, xs=x,
        fit=dict(intercept=fit.intercept, slope=fit.slope, xmin=min(x), xmax=max(x), ymin=ymin),
    )

    def tx(px, py, text, extra=''):
        return f'<text x="{px}" y="{py}"{extra}>{escape(str(text))}</text>'

    def line(x1, y1, x2, y2, color='#94a3b8', extra=''):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}"{extra}/>'

    body = tx(16, 28, '질문 → 자료 → 방법 → 결과 → 적용')
    for index, row in enumerate(steps):
        yy = 44 + index * 62
        stroke = '#d97706' if index == 0 else '#94a3b8'
        width = '3' if index == 0 else '1'
        body += f'<rect data-step="{index}" x="16" y="{yy}" width="328" height="52" rx="6" fill="#eaf2ff" stroke="{stroke}" stroke-width="{width}"/>'
        body += tx(28, yy + 22, row['title']) + tx(28, yy + 42, row['short'])
        if index < 4:
            body += line(180, yy + 52, 180, yy + 62)
    figure1 = (
        '<figure class="learn-chart learn-chart--wide read-chart"><svg viewBox="0 0 640 410" role="img" '
        'aria-labelledby="workflow-title workflow-desc"><title id="workflow-title">결과 읽기 순서</title>'
        '<desc id="workflow-desc">그림 1. 질문, 자료, 방법, 결과, 적용 순서입니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 1. 숫자를 보기 전에 질문과 자료를 확인합니다. 조건이 확인되지 않으면 결론을 좁힙니다.</figcaption></figure>'
    )
    body = tx(16, 28, '별도 가상 예제 · 공통 자료의 회귀계수가 아님') + line(40, 330, 340, 330) + line(94, 48, 94, 330, '#94a3b8')
    for index, row in enumerate(effects):
        yy = 100 + index * 78
        lo = round(48 + (row['low'] + 1) * 46, 1)
        hi = round(48 + (row['high'] + 1) * 46, 1)
        xx = round(48 + (row['estimate'] + 1) * 46, 1)
        body += tx(16, yy - 18, f'{row["label"][0]} · 추정 {row["estimate"]} · 구간 {row["low"]}~{row["high"]}')
        body += line(lo, yy, hi, yy, '#2563eb', f' data-effect="{index}"')
        body += line(lo, yy - 6, lo, yy + 6, '#2563eb') + line(hi, yy - 6, hi, yy + 6, '#2563eb')
        body += f'<circle data-effect="{index}" cx="{xx}" cy="{yy}" r="5" fill="#2563eb"/>'
    for value in [-1, 0, 1, 2, 3, 4, 5]:
        body += tx(40 + (value + 1) * 46, 352, value)
    body += '<line id="read-threshold" x1="94" y1="48" x2="94" y2="330" stroke="#d97706" stroke-dasharray="4 3" visibility="hidden"/>'
    body += tx(16, 390, '가로: 가상 효과 · 점 추정 / 선 구간 · 세로선은 0')
    figure2 = (
        '<figure class="learn-chart learn-chart--wide read-chart"><svg viewBox="0 0 640 410" role="img" '
        'aria-labelledby="uncertainty-title uncertainty-desc"><title id="uncertainty-title">효과 크기와 신뢰구간</title>'
        '<desc id="uncertainty-desc">그림 2. A는 0을 제외하지만 작고, B는 넓어 0을 포함합니다. C도 0을 포함합니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 2. 공통 학습자료가 아닌 가상 구간입니다. 0을 제외해도 실무적 중요가 확정되지는 않습니다.</figcaption></figure>'
    )
    body = tx(16, 28, '같은 직선 절차 · 다른 학습과 평가') + line(36, 335, 330, 335)
    for index, row in enumerate(procedures):
        yy = 70 + index * 86
        width = row['mae'] * 5.6
        body += tx(16, yy - 8, f'{row["name"]} · 평가 {row["n"]}건')
        body += f'<rect data-eval="{index}" x="36" y="{yy}" width="{width}" height="28" fill="#2563eb"/>'
        body += tx(44 + width, yy + 19, f'{row["mae"]:.2f}')
    for value in [0, 20, 40]:
        body += tx(28 + value * 5.6, 356, value)
    body += tx(16, 390, '가로: MAE · 막대 길이는 우열이 아닙니다')
    figure3 = (
        '<figure class="learn-chart learn-chart--wide read-chart"><svg viewBox="0 0 640 410" role="img" '
        'aria-labelledby="prediction-title prediction-desc"><title id="prediction-title">평가 자료가 다른 오차</title>'
        '<desc id="prediction-desc">그림 3. 재대입 38.16, 홀드아웃 41.08, 3폴드 39.85입니다. 시간 분할이 아닙니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 3. 세 값은 알고리즘 순위가 아닙니다. 번호 1~30은 거래 시점이 아닙니다.</figcaption></figure>'
    )
    x0, x22, x310, x350 = (28 + value * 0.86 for value in [0, 22, 310, 350])
    body = tx(16, 28, '관측 X 22~310 · 선택한 X의 위치') + line(28, 210, 340, 210)
    body += f'<rect x="{x22}" y="176" width="{x310 - x22}" height="34" fill="#dbeafe"/>'
    body += tx(x22 + 8, 198, '관측 X 22~310')
    for value in [0, 22, 100, 200, 310, 350]:
        px = 28 + value * 0.86
        body += line(px, 210, px, 222) + tx(px - 10, 242, value)
    body += f'<line id="read-x" x1="{28 + 100 * 0.86}" y1="150" x2="{28 + 100 * 0.86}" y2="250" stroke="#d97706"/>'
    body += tx(28 + 100 * 0.86 + 6, 146, 'X=100', ' id="read-x-label"')
    body += tx(16, 280, '범위 안이라도 밀도·잔차·다른 지역은 따로 봅니다')
    body += tx(16, 390, '가로: X · 파란 띠는 최소~최대일 뿐 고른 밀도는 아닙니다')
    figure4 = (
        '<figure class="learn-chart learn-chart--wide read-chart"><svg viewBox="0 0 640 410" role="img" '
        'aria-labelledby="scope-title scope-desc"><title id="scope-title">관측 범위와 적용 범위</title>'
        '<desc id="scope-desc">그림 4. X=0은 범위 밖이고 X=310의 예측은 관측 Y 최솟값보다 낮을 수 있습니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 4. 식을 계산할 수 있는 위치와 그 예측을 믿을 근거가 있는 위치는 다릅니다.</figcaption></figure>'
    )

    def buttons(attr, labels, pressed):
        chunks = []
        for index, label in enumerate(labels):
            state = ' aria-pressed="true"' if index == pressed else ''
            chunks.append(f'<button type="button" data-{attr}="{index}"{state}>{escape(label)}</button>')
        return ''.join(chunks)

    controls1 = (
        '<div class="read-controls" hidden><div class="read-shortcuts">'
        + buttons('step-button', ['질문', '자료', '방법', '결과', '적용'], 0)
        + '</div><p role="status" id="read-step-status"></p></div>'
    )
    controls2 = (
        '<div class="read-controls" hidden><div class="read-shortcuts">'
        + buttons('effect-button', ['사례 A', '사례 B', '사례 C'], 0)
        + '</div><div class="read-shortcuts"><button type="button" data-threshold="none" aria-pressed="true">기준 없음</button>'
        '<button type="button" data-threshold="0.5">기준 0.5</button><button type="button" data-threshold="1">기준 1</button></div>'
        '<p role="status" id="read-effect-status"></p></div>'
    )
    controls3 = (
        '<div class="read-controls" hidden><div class="read-shortcuts">'
        + buttons('eval-button', ['재대입', '홀드아웃', '3폴드'], 0)
        + '</div><p role="status" id="read-eval-status"></p></div>'
    )
    controls4 = (
        '<div class="read-controls" hidden><p><label>입력 X <input class="read-x" type="number" min="0" max="400" step="1" value="100"></label></p>'
        '<div class="read-shortcuts"><button type="button" data-x="0">X=0</button><button type="button" data-x="22">X=22</button>'
        '<button type="button" data-x="100" aria-pressed="true">X=100</button><button type="button" data-x="310">X=310</button></div>'
        '<p role="status" id="read-scope-status"></p></div>'
    )
    parts = []

    def sec(section_id, label, title, section_body):
        parts.append(
            f'<section class="learn-chapter__step" id="{section_id}" data-toc-label="{label}">'
            f'<p class="learn-chapter__label">{label}</p><h2>{title}</h2>{section_body}</section>'
        )

    sec('quick-start', '서두 · 학습목표', '통계 결과가 나왔을 때 무엇부터 확인해야 할까요?',
        '<p>어떤 지역의 아파트 평균 거래단가가 전년보다 10% 올랐다고 해서, 그 지역 아파트 가격이 전반적으로 10% 올랐다고 말할 수는 없습니다. 올해와 지난해에 거래된 아파트의 구성이 달라졌을 수 있습니다. 회귀에서 면적계수가 음수이고 p값이 0.01이어도, 면적을 늘리면 단가가 반드시 내린다는 뜻은 아닙니다. 관측된 관계와 인과효과는 다르고, 표본과 모형에 따라 결과가 달라질 수 있습니다.</p>'
        '<p>숫자를 읽는 일과 함께, 그 숫자가 어떤 질문의 답인지, 어떤 자료와 가정에서 계산됐는지를 확인합니다. 이번 마지막 장은 평균과 분산, 확률, 구간과 검정, 회귀, 예측, 기초 머신러닝을 하나의 판단 절차로 연결합니다.</p>'
        '<ul class="learn-objectives"><li>기술통계·추론·예측·인과 질문을 구별합니다.</li><li>대상, 관측 단위, 포함·제외 기준을 확인합니다.</li><li>평균·회귀계수·R²·p값·예측오차를 서로 다른 의미로 읽습니다.</li><li>통계적 유의성과 실무적으로 중요한 차이를 구별합니다.</li><li>학습 성능과 새 자료의 검증 성능을 구별합니다.</li><li>계산할 수 있는 범위와 적용할 수 있는 범위를 구분합니다.</li><li>한계를 포함한 해석 문장을 작성합니다.</li></ul>')
    sec('workflow', '통계 결과를 읽는 다섯 단계', '숫자보다 먼저 질문과 자료를 확인합니다',
        '<p>가장 높은 R²나 가장 작은 p값부터 보기 쉽습니다. 그 전에 질문, 자료, 방법, 결과, 적용을 순서대로 봅니다. 어느 단계에서 문제가 보이면 결론을 좁히거나 추가 검증이 필요합니다. 표본이 적은 지역의 높은 R²는 방법과 결과만 보면 좋아 보여도, 자료의 규모를 먼저 보면 판단이 달라질 수 있습니다. 좋은 해석은 결과를 크게 말하는 일이 아니라 근거가 허용하는 범위까지 정확하게 말하는 일입니다.</p>'
        + controls1 + figure1)
    sec('purposes', '기술통계·추론·예측·인과', '같은 숫자라도 답하려는 질문이 다릅니다',
        '<table class="read-metrics"><caption>네 가지 질문</caption><thead><tr><th>구분</th><th>주요 질문</th><th>대표적인 결과</th></tr></thead><tbody>'
        '<tr><td>기술통계</td><td>관측된 자료가 어떤 모습인가?</td><td>평균·중앙값·분산·분위수</td></tr>'
        '<tr><td>통계적 추론</td><td>모집단 특성을 어떻게 추정할까?</td><td>추정값·신뢰구간·p값</td></tr>'
        '<tr><td>예측</td><td>아직 보지 않은 값을 얼마나 맞힐까?</td><td>MAE·RMSE·검증 결과</td></tr>'
        '<tr><td>인과 분석</td><td>조건을 바꾸면 결과가 어떻게 달라질까?</td><td>설계와 가정 아래의 인과효과 추정</td></tr></tbody></table>'
        '<p>면적과 거래단가의 음의 상관은 그 자료에서 두 변수가 반대 방향으로 움직였다는 관측입니다. 면적을 늘리면 단가가 같은 크기로 내린다는 뜻도, 미래 가격을 정확히 맞힌다는 보장도 아닙니다. 지금 보는 숫자가 관측의 요약인지, 예측인지, 원인에 대한 주장인지 먼저 묻습니다.</p>')
    sec('units', '분석 대상과 관측 단위', '거래 100건과 부동산 100개는 다른 자료입니다',
        '<p>같은 세대가 다른 시점에 반복 거래되면 100건이 100채는 아닙니다. 한 단지의 여러 거래는 입지와 시장 환경을 공유할 수 있어, 관측 100개가 독립된 정보 100개는 아닙니다. 거래 건수, 필지 수, 건물 수, 단지 수, 세대 수를 구별합니다. 단지별 평균을 다시 단순평균하는 일과 거래 건수로 가중하는 일은 다른 결과를 만듭니다. 무엇을 하나의 관측으로 계산했는지가 통계값의 의미입니다.</p>')
    sec('weighting', '단위와 가중 방식', '평균이라는 이름만으로 같은 숫자가 되지는 않습니다',
        '<p>거래 건마다 단가의 단순평균은 P̄=(1/n)ΣPᵢ입니다. 면적가중 단가는 Pw=ΣAᵢPᵢ/ΣAᵢ=ΣVᵢ/ΣAᵢ입니다. 단순평균은 한 건에 같은 비중을 주고, 면적가중은 넓은 거래에 더 큰 비중을 줍니다. 어느 쪽이 맞는지는 목적에 따릅니다. 기간별 평균이 달라진 이유는 같은 부동산의 가격 변화일 수도 있고 거래 구성의 변화일 수도 있습니다. 긴 기간에서는 명목가격과 물가를 조정한 실질가격도 구별합니다.</p>')
    sec('excluded', '표본과 제외된 관측', '분석에 포함되지 않은 자료도 결과에 영향을 줍니다',
        '<p>처음 100건에서 건축연도나 도로 조건이 없는 거래를 빼 65건이 됐다면, 그 회귀가 100건 전체를 대표한다고 확인 없이 말할 수 없습니다. 제외된 35건이 특정 지역이나 유형에 몰려 있을 수 있습니다. 필터 전후 관측수, 제외된 자료의 특성, 이상치를 뺀 이유가 오류인지 단지 큰 값인지, 결측을 어떤 기준으로 바꿨는지를 봅니다. IQR 밖이라는 사실만으로 잘못된 거래라고 단정하지 않습니다. 정제했다는 사실이 대표성을 자동으로 높이지는 않습니다.</p>')
    sec('summary', '공통 학습자료의 종합 해석', '평균과 기울기, R²는 서로 다른 질문에 답합니다',
        '<p>11장부터 쓴 공통 자료 30건의 X와 Y는 단위 없는 학습용 수치입니다. 실제 거래 출처와 표집 설계는 확인되지 않았으므로 특정 지역의 통계로 읽지 않습니다. 관측번호는 거래 시점이 아닙니다.</p>'
        f'<table class="read-metrics"><caption>Y의 기술통계</caption><thead><tr><th>항목</th><th>계산 결과</th></tr></thead><tbody>'
        f'<tr><td>관측수</td><td>30</td></tr><tr><td>평균</td><td>{mu:.2f}</td></tr><tr><td>중앙값</td><td>{median(y):.0f}</td></tr>'
        f'<tr><td>평균의 t 방식 95% 구간</td><td>{mu - half:.2f}~{mu + half:.2f}</td></tr></tbody></table>'
        '<p>평균이 중앙값보다 높으면 큰 값이 평균을 끌어올렸을 가능성을 더 보라는 단서입니다. 두 숫자만으로 분포 전체를 확정하지는 않습니다.</p>'
        f'<p>X 하나의 단순선형회귀는 Ŷ≈{fit.intercept:.3f}{fit.slope:.4f}X입니다. 기울기 약 {fit.slope:.4f}는 이 식에서 X가 1 큰 관측의 예측 Y가 약 {abs(fit.slope):.4f} 작다는 뜻입니다. X를 실제로 바꾸면 Y가 그만큼 줄어든다는 인과효과는 아닙니다. 학습 R² 약 {fit.rvalue ** 2:.4f}는 평균만 쓸 때보다 제곱오차를 약 {fit.rvalue ** 2 * 100:.2f}% 줄였다는 뜻이지, 그 비율의 거래를 정확히 맞혔다는 뜻은 아닙니다.</p>')
    sec('inference', '신뢰구간과 추론의 전제', '계산할 수 있는 구간과 신뢰할 수 있는 결론은 다릅니다',
        f'<p>t 방식으로 계산한 평균 Y의 95% 구간은 약 {mu - half:.2f}~{mu + half:.2f}입니다. 모집단 평균이 반드시 그 안에 있다고 말할 수는 없습니다. 독립적인 무작위 표본인지, 특정 거래만 들어 있는지가 해석에 필요합니다. 표집 방식이 확인되지 않았으므로 이 구간을 특정 모집단의 검증된 추론으로 부르지 않습니다.</p>'
        '<p>평균의 신뢰구간은 모집단 평균을 추정하고, 예측구간은 새 관측 하나의 변동까지 포함합니다. 같은 조건에서는 보통 예측구간이 더 넓습니다. 회귀에서도 평균 반응의 구간과 새 거래의 예측구간을 구별합니다. 구간을 계산하는 일과 그 구간을 시장에 적용할 근거는 별개입니다.</p>')
    sec('uncertainty', '통계적 유의성과 실질적 중요성', 'p값이 작아도 효과는 작을 수 있습니다',
        '<p>p값은 귀무가설과 검정 모형이 맞을 때, 관측만큼 또는 더 극단적인 통계량이 나올 확률입니다. 귀무가설이 참일 확률, 연구가설이 옳을 확률, 효과가 클 확률, 예측이 정확할 확률은 아닙니다. 표본이 많으면 작은 차이도 유의할 수 있고, 표본이 적으면 의미 있는 차이도 구간이 넓고 p값이 클 수 있습니다.</p>'
        + controls2 + figure2 +
        '<p>사례 A는 효과가 작지만 구간이 0을 넣지 않습니다. 대응하는 양측 검정에서는 유의할 수 있어도, 업무에서 중요한 크기인지는 따로 판단합니다. 사례 B는 추정이 더 크지만 구간이 넓고 0을 포함합니다. 큰 효과도, 효과가 없다는 결론도 이 자료만으로 배제하지 못합니다. 사례 C는 추정이 0이고 구간은 −0.5~0.5입니다. 추정치, 구간의 폭, 실무적으로 중요한 최소 효과, 표본수, 가정의 적절성을 함께 봅니다.</p>')
    sec('nonsignificant', '유의하지 않다는 것은 효과가 없다는 뜻일까요?', '결론을 내릴 자료가 부족할 수도 있습니다',
        '<p>p값이 0.05보다 크다는 것은 그 검정에서 귀무가설을 기각할 근거가 부족하다는 뜻입니다. 효과가 없다는 증명은 아닙니다. 거래가 적거나 설명변수가 서로 관련되면 표준오차가 커져, 중요한 관계도 불확실하게 보일 수 있습니다. 효과가 없거나 무시할 만큼 작다고 말하려면 허용할 크기를 정하고 그에 맞는 동등성 검정 등을 검토합니다.</p>')
    sec('regression-order', '회귀분석을 해석하는 순서', 'R²보다 변수와 잔차의 의미를 함께 살펴봅니다',
        '<ol><li>어떤 목표와 입력변수를 썼는가.</li><li>선형인지, 로그·제곱·상호작용을 넣었는가.</li><li>계수의 방향과 크기, 단위와 기준 범주는 무엇인가.</li><li>표준오차, 구간, p값, 유효 표본수는 어떠한가.</li><li>잔차 패턴, 큰 잔차, 영향력 있는 관측, 다중공선성은 어떠한가.</li><li>어느 지역·기간·관측 범위의 관계인가.</li></ol>'
        '<p>R²가 높다고 가정이 모두 맞지는 않고, 계수가 유의하다고 인과가 확인되지도 않습니다. 회귀계수는 다른 설명변수를 모형 안에서 고정한 조건부 관계입니다. 수정 R²는 변수 수와 잔차 자유도를 고려한 적합도이고, 예측오차는 정한 평가자료의 실제값과 예측값 차이입니다.</p>')
    sec('prediction', '예측 성능을 읽는 방법', '같은 모형도 어디에서 평가했는지에 따라 오차가 다릅니다',
        '<p>재대입은 학습한 자료에 다시 적용하고, 홀드아웃은 남겨 둔 자료에서 평가하며, 교차검증은 학습과 검증 부분을 바꿔 반복합니다. 아래 세 막대는 다른 알고리즘의 순위가 아니라, 같은 직선 절차를 다른 자료 구성에서 평가한 결과입니다.</p>'
        '<table class="read-metrics"><caption>공통 자료의 세 평가</caption><thead><tr><th>평가 내용</th><th>MAE</th></tr></thead><tbody>'
        f'<tr><td>전체 30건 재대입</td><td>{errs[0]:.2f}</td></tr>'
        f'<tr><td>1~20번 학습, 21~30번 확인</td><td>{errs[1]:.2f}</td></tr>'
        f'<tr><td>번호 블록 3폴드의 평균 MAE</td><td>{errs[2]:.2f}</td></tr></tbody></table>'
        + controls3 + figure3 +
        '<p>가장 작은 숫자를 더 우수한 모형이라고 고르지 않습니다. 1~20번과 21~30번은 미래 거래 검증이 아닙니다. 교차검증을 썼다는 사실만으로 선택에 쓰지 않은 최종 시험이 끝난 것도 아닙니다. 폴드가 각각 10건이라 세 폴드 MAE의 평균과 예측오차를 모두 합친 값은 같습니다.</p>')
    sec('error-reading', '예측오차를 종합해서 읽기', 'MAE 하나만으로 모든 오류를 설명할 수 없습니다',
        '<p>MAE는 평균 절대오차이고 RMSE는 큰 오차에 더 민감합니다. MAPE는 실제값 대비 백분율인데, 실제값이 아주 작거나 0이면 해석과 계산이 어려워집니다. 평가 건수, 어떤 거래를 넣었는지, 과소·과대 예측, 큰 오차의 특성, 지역·유형·가격대별 오차, 단순한 기준모형과의 차이를 함께 봅니다. 전체 MAE가 30이어도 모든 거래의 오차가 30 이하인 것은 아닙니다. 모형마다 평가 대상이 다르면 숫자만으로 직접 비교하기 어렵습니다.</p>')
    sec('choice', '모형 선택 결과의 함정', '여러 모형 가운데 가장 좋은 점수만 남기면 어떻게 될까요?',
        '<p>여러 후보 중 가장 작은 CV-MAE를 고르는 일은 선택 절차일 수 있습니다. 그 점수를 그대로 독립적인 최종 성능이라고 발표하면, 우연히 검증자료에 맞은 후보가 좋아 보일 수 있습니다. 변수 선택을 전체 자료에서 먼저 하면 교차검증도 낙관적으로 보일 수 있습니다. 무엇을 비교했는지, 어떤 지표로 골랐는지, 전처리와 변수 선택이 학습 부분 안에서 이뤄졌는지, 선택에 쓰지 않은 평가가 있는지를 확인합니다. 예측 오차가 작다고 설명형의 변수 유의성이 증명되지는 않고, 설명형에서 중요하다고 본 변수를 예측오차 하나만으로 빼야 하는 것도 아닙니다.</p>')
    sec('scope', '계산 가능한 범위와 적용 가능한 범위', '회귀식에 숫자를 대입할 수 있다고 해서 신뢰할 수 있는 예측은 아닙니다',
        f'<p>공통 식 Ŷ≈{fit.intercept:.3f}{fit.slope:.4f}X에 X=0을 넣으면 약 {pred(0):.2f}입니다. 관측된 X는 {min(x)}~{max(x)}이므로 0은 범위 밖입니다. X=310은 범위 안이지만 예측은 약 {pred(310):.2f}로, 관측 Y의 최솟값 {ymin}보다 낮습니다. 화면의 예측은 반올림한 계수가 아니라 적합에 쓴 계수로 계산합니다.</p>'
        + controls4 + figure4 +
        '<p>범위 밖의 외삽, 범위 안이지만 관측이 드문 구간, 각 변수는 범위 안인데 조합은 처음인 경우, 다른 지역이나 미래 시점을 구별합니다. 최소·최대만으로 적용 가능성을 정하지 않습니다.</p>')
    sec('transfer', '다른 지역의 회귀식을 그대로 사용할 수 있을까요?', '지역이 달라지면 가격 형성 구조도 달라질 수 있습니다',
        '<p>한 읍면동의 음수 관계를 옆 지역에 그대로 옮길 수는 없습니다. 용도지역과 이용상황, 규모 분포, 도로와 접근성, 개발 가능성과 수요, 거래량, 거래 시점과 시장 환경이 다르면 계수와 오차도 달라질 수 있습니다. 거래가 드문 곳에서는 일부 거래의 영향이 큽니다. 다른 지역에 적용하려면 변수 분포와 관계가 비슷한지 보고, 필요하면 그 지역을 평가대상으로 남기는 설계가 필요합니다.</p>')
    sec('exploration', '탐색적 발견과 독립적인 검증', '여러 분석을 시도한 뒤 가장 좋은 결과만 보고하면 문제가 생깁니다',
        '<p>여러 지역·기간·변수 조합을 시험한 뒤 유의한 것만 보고하면 우연한 발견이 사실처럼 보일 수 있습니다. 100개의 독립적인 귀무가설을 각각 5%로 검정하면, 모두 참이어도 평균적으로 약 5개의 거짓 양성이 나올 수 있습니다. 검정이 서로 의존하면 그 분포는 더 복잡해집니다. 가족별 오류율이나 거짓발견율을 조절하는 방법, 미리 정한 가설을 다른 자료에서 확인하는 방법을 검토할 수 있습니다. 같은 자료로 관계를 찾고 다시 검정했다면 독립된 검증이 아닙니다. 이번 학습 페이지는 그 보정 계산을 서비스에 넣지 않습니다.</p>')
    sec('sensitivity', '민감도 분석', '합리적인 조건을 조금 바꾸어도 결론이 유지될까요?',
        '<p>기간, 지역 범위, 이상치 포함 여부, 공시지가·도로·용도지역의 포함, 선형·로그·다항식처럼 합리적인 대안을 정해 비교할 수 있습니다. 결과를 좋게 만들려고 조건을 계속 바꾸는 일과는 다릅니다. 바뀌지 않았다는 사실만으로 인과나 다른 지역 적용이 증명되지는 않습니다.</p>')
    sec('reproducibility', '통계 결과의 재현성', '나중에 같은 분석을 다시 할 수 있어야 합니다',
        '<p>같은 지역과 기간인데 계수가 달라졌다면 원자료, 결측 처리, 변수 선택, 프로그램 설정이 바뀌었을 수 있습니다. 지역·기간·유형·단위·기준일, 원천 판본과 정제, 결과변수와 설명변수·인코딩·변환, 알고리즘과 분할·지표, 계수와 오차·진단·계산 시점을 남깁니다. 자료가 갱신되면 이전 숫자와 달라질 수 있습니다. 재현성은 같은 숫자를 다시 얻는 일뿐 아니라 왜 그 숫자가 나왔는지 설명하는 상태입니다.</p>')
    sec('sentences', '해석 문장을 작성하는 방법', '결과의 크기보다 근거와 한계를 정확하게 표현합니다',
        '<p><strong>피해야 할 문장:</strong> “X가 증가하면 Y는 반드시 감소하며, R²가 0.42이므로 이 모형은 42% 정확합니다.” 음의 기울기를 인과로 말했고, R²를 예측 정확도의 백분율로 읽었습니다.</p>'
        f'<p><strong>고쳐 쓴 문장:</strong> 출처와 표집 설계가 확인되지 않은 공통 학습자료 30건에서 X 하나를 쓴 단순선형회귀의 기울기는 약 {fit.slope:.4f}입니다. 이는 그 자료의 음의 관계이며 인과효과가 아닙니다. 학습 R²는 약 {fit.rvalue ** 2:.4f}이고, 1~20번으로 학습한 모형의 21~30번 확인 MAE는 약 {errs[1]:.2f}입니다. 다른 지역이나 시점에서도 같은 관계와 성능이 나오는지는 확인되지 않았습니다.</p>'
        '<p>보고서에는 분석 대상, 주요 결과, 불확실성과 검증, 결론의 범위를 나눕니다.</p>')
    sec('macro', 'CH2 Macro에서 읽기', '결과 화면을 볼 때 여섯 가지를 확인하세요',
        '<details><summary>① 범위</summary><p>지역, 기간, 부동산 유형, 용도지역이 목적에 맞는지 봅니다. 3년·5년·7년 자료는 같은 시장이라도 포함된 거래의 구성이 달라질 수 있습니다.</p></details>'
        '<details><summary>② 관측 단위</summary><p>거래인지 단지인지 필지인지, 총액인지 단가인지, 건수 기준인지 면적가중인지 구별합니다.</p></details>'
        '<details><summary>③ 포함·제외</summary><p>결측, 중복, 이상치, 대장 보강으로 어떤 거래가 빠지거나 보완됐는지, 전후 유효 표본수가 왜 달라졌는지 확인합니다.</p></details>'
        '<details><summary>④ 분석 방법</summary><p>단순 통계, 설명형 회귀, 예측형 모형, 유사거래 비교는 서로 다른 질문에 답합니다.</p></details>'
        '<details><summary>⑤ 결과와 불확실성</summary><p>계수, R², 표준오차, 잔차, 검증오차를 하나의 점수로 합치지 않습니다.</p></details>'
        '<details><summary>⑥ 적용 범위</summary><p>분석하지 않은 지역·기간으로의 일반화, 개별 적정가격, 인과효과로 자동 확장하지 않습니다.</p></details>'
        '<p>확인한 복합·집합 추천 화면은 예측형, 설명형, 쌍둥이 확장을 나눕니다. 토지 화면의 설명형은 AIC, 예측형은 MAPE 후보를 보여 주며, 그 안내에는 Twin Validation을 복합 쪽으로 적고 있습니다. 설명형은 관측된 관계를 보고, 예측형은 정한 평가의 오차를 보며, 쌍둥이는 어떤 특성으로 비슷하다고 봤는지와 비교 사례가 충분한지를 봅니다. 설명형이 인과를 확정하지 않고, 작은 검증오차가 감정평가액이 되지는 않습니다. 유사거래가 반드시 KNN이나 군집분석인 것도 아닙니다. 이번 장의 30건 계산은 그 화면의 결과가 아닙니다.</p>'
        '<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>'
        '<details><summary>확인한 서비스 범위</summary><p>복합 `RecommendationModal`과 집합 `CollectiveModelRecommend`, 토지 `landStatsExplain`에서 설명형·예측형 구분을 확인했습니다. 이 확인을 모든 화면이 같은 알고리즘과 세 탭을 가진다는 뜻으로 확대하지 않습니다. 다중검정 보정, 자동 민감도 실험, 재현에 필요한 판본 묶음은 이번 학습 페이지에서 새로 만들지 않았습니다.</p></details>')
    questions = [
        ('평균 Y의 95% 신뢰구간이 115.89~176.78이라면 관측 Y의 95%가 그 구간 안에 들어갈까요?', '<strong>그렇지 않습니다.</strong> 모집단 평균을 추정하는 구간이며 개별 관측의 범위가 아닙니다. 표집 설계가 확인되지 않은 학습자료이므로 특정 모집단의 검증된 구간으로 일반화하지 않습니다.'),
        ('회귀모형의 R²가 더 높다면 새로운 거래도 반드시 더 정확하게 예측할까요?', '<strong>아닙니다.</strong> 학습 R²는 학습자료의 적합도입니다. 새 자료의 성능은 검증자료의 MAE·RMSE 등으로 따로 확인합니다.'),
        ('회귀계수의 p값이 0.05보다 크면 해당 변수는 가격과 관련이 없다고 결론 내려도 될까요?', '<strong>그렇지 않습니다.</strong> 귀무가설을 기각할 근거가 부족하다는 뜻이지 효과가 없다는 증명은 아닙니다.'),
        ('군집분석에서 군집 2에 속한 거래들이 군집 1보다 우수한 거래일까요?', '<strong>그렇게 해석할 수 없습니다.</strong> 군집번호는 임의 이름표입니다. 관측의 특성을 본 뒤 의미를 말합니다.'),
        ('다른 지역에서 얻은 회귀식을 적용했더니 높은 R²가 나타났다면 인과관계가 확인된 것일까요?', '<strong>아닙니다.</strong> 적합도나 연관성이 높다는 사실만으로 인과효과가 확인되지 않습니다.'),
        ('전체 100건 가운데 결측치 때문에 40건을 제외하고 계산한 결과를 원래 100건의 시장 특성으로 해석해도 될까요?', '<strong>추가 확인이 필요합니다.</strong> 제외된 40건이 나머지와 다를 수 있습니다. 분포와 처리 방법을 본 뒤 결론의 범위를 정합니다.'),
    ]
    sec('practice', '종합 확인 문제', '지금까지 배운 통계 개념을 실제 결과에 연결해 보세요',
        '<ol class="learn-exercises">' + ''.join(
            f'<li>{question}<details><summary>답과 해설</summary><p>{answer}</p></details></li>' for question, answer in questions
        ) + '</ol>')
    sec('recap', '과정 마무리', '모든 공식을 외우기보다 숫자가 어떤 질문의 답인지 이해하세요',
        '<p>32개 장에서 분포와 중심, 표본의 불확실성, 회귀의 관계와 잔차, 학습과 검증, 비선형 관계와 분류, 이웃, 의사결정나무, 군집을 살펴봤습니다. 필요한 것은 공식의 암기보다, 숫자가 무엇을 설명하고 어떤 근거를 가지며 어디까지 말할 수 있는지 판단하는 일입니다.</p>'
        '<ol><li>무엇을 알고 싶은가?</li><li>무엇을 관측했는가?</li><li>어떻게 계산했는가?</li><li>얼마나 확실한가?</li><li>다른 조건에서도 성립하는가?</li><li>어디까지 말할 수 있는가?</li></ol>'
        '<p>통계분석은 자료가 알려 주는 사실과 아직 알려 주지 못하는 사실을 구별해 판단을 돕습니다.</p>'
        '<p class="read-closing">숫자의 크기보다 그 숫자가 어떤 질문과 자료에서 나왔는지 먼저 확인하세요.</p>'
        '<p><a href="/learn/stats/">전체 32장 목차로 돌아가기</a></p>'
        '<details class="learn-references"><summary>참고자료와 공통 학습자료 계산 조건</summary>'
        '<ul><li><a href="../reading-results-example.json">요약 수치·평가 오차·가상 효과 구간</a></li>'
        '<li><a href="../example-data.json">공통 학습자료 30건</a></li></ul>'
        '<p class="learn-source-note">본 장의 공통 자료는 출처와 표집 설계가 확인되지 않은 학습용 자료입니다. 그림 2의 효과크기와 신뢰구간도 별도 가상 예제입니다. 모든 결과는 통계 해석을 연습하기 위한 것이며 특정 부동산 시장의 실제 평가 결과가 아닙니다.</p></details>')

    page = ROOT / 'reading-results' / 'index.html'
    html = page.read_text(encoding='utf-8')
    html = re.sub(
        r'<article.*?</article>',
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="통계 결과를 읽고 판단하는 법">' + '\n'.join(parts) + '</article>',
        html, count=1, flags=re.S,
    )
    html = re.sub(
        r'(name="description"\s+content=").*?("\s*/>)',
        r'\1질문·자료·방법·결과·적용 순서로 평균, 회귀, 검증오차와 적용 범위를 읽는 방법을 학습합니다.\2',
        html, count=1, flags=re.S,
    )
    if 'reading-results/chapter.css' not in html:
        html = html.replace('</head>', '<link rel="stylesheet" href="/learn/stats/reading-results/chapter.css?v=20261025-4" /></head>')
    blob = '<script type="application/json" id="read-data">' + json.dumps(page_data, ensure_ascii=False) + '</script>'
    if 'id="read-data"' not in html:
        html = html.replace('</body>', blob + '\n</body>')
    else:
        html = re.sub(r'<script type="application/json" id="read-data">.*?</script>', blob, html, count=1, flags=re.S)
    if 'reading-results/experiment.js' not in html:
        html = html.replace('</body>', '<script type="module" src="/learn/stats/reading-results/experiment.js?v=20261025-3"></script>\n</body>')
    if '[그림 ' in html or '33장' in html:
        raise SystemExit('placeholder or next chapter remains')
    if html.count('<summary>답과 해설</summary>') != 6:
        raise SystemExit('exercise count changed')
    if 'Macro 활용도 3단계, 핵심' not in html or '★☆☆ 심화' not in html:
        raise SystemExit('relevance badge changed')
    page.write_text(html, encoding='utf-8')
    print(
        f'mean={mu:.2f} median={median(y):.0f} ci={mu - half:.2f}~{mu + half:.2f} '
        f'slope={fit.slope:.4f} r2={fit.rvalue ** 2:.4f} mae={[round(v, 2) for v in errs]} '
        f'y0={pred(0):.2f} y100={pred(100):.2f} y310={pred(310):.2f}'
    )


if __name__ == '__main__':
    build()
