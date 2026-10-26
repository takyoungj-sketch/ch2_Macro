"""Chapter 1: data and variables. Shared 30-row example stays unchanged."""
from pathlib import Path
from html import escape
import json
import re

ROOT = Path(__file__).resolve().parent
BLOCK = '''        "slug": "data-and-variables",
        "title": "데이터와 변수",
        "soon": false,
        "macro_relevance": 2'''
BLOCK_NEW = BLOCK.replace('"macro_relevance": 2', '"macro_relevance": 3')


def promote(path: Path):
    text = path.read_text(encoding='utf-8')
    if BLOCK_NEW in text:
        return
    if BLOCK not in text:
        raise SystemExit(f'relevance block missing: {path}')
    path.write_text(text.replace(BLOCK, BLOCK_NEW, 1), encoding='utf-8')


def build():
    rows = json.loads((ROOT / 'example-data.json').read_text(encoding='utf-8'))['rows']
    assert len(rows) == 30
    assert sum(row['group'] == '주거' for row in rows) == 15
    assert sum(row['group'] == '상업' for row in rows) == 15
    assert min(row['area'] for row in rows) == 22 and max(row['area'] for row in rows) == 310
    assert min(row['price'] for row in rows) == 62 and max(row['price'] for row in rows) == 480
    row7 = next(row for row in rows if row['id'] == 7)
    row14 = next(row for row in rows if row['id'] == 14)
    assert (row7['group'], row7['area'], row7['floor'], row7['price']) == ('상업', 22, 1, 480)
    assert (row14['group'], row14['area'], row14['floor'], row14['price']) == ('상업', 250, 2, 62)
    assert len({(row['area'], row['price']) for row in rows}) == 30
    assert round(24000 / 1111, 1) == 21.6
    preview = [next(row for row in rows if row['id'] == item) for item in (1, 7, 14)]
    page_data = dict(
        rows=rows,
        preview=[1, 7, 14],
        groups=[dict(name='주거', count=15, share=0.5), dict(name='상업', count=15, share=0.5)],
    )

    def tx(x, y, text, extra=''):
        return f'<text x="{x}" y="{y}"{extra}>{escape(str(text))}</text>'

    def cell(x, y, w, h, label, fill, extra=''):
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#94a3b8"{extra}/>'
            + tx(x + 8, y + 24, label)
        )

    cols = [('id', '번호', 8, 52), ('group', '구분', 64, 68), ('area', '면적', 136, 72), ('floor', '층', 212, 48), ('price', '단가', 264, 78)]
    body = tx(8, 24, '한 행은 관측, 한 열은 변수')
    for key, label, x, w in cols:
        body += cell(x, 36, w, 36, label, '#eaf2ff', f' data-col="{key}"')
    for index, row in enumerate(preview):
        y = 78 + index * 46
        values = {'id': row['id'], 'group': row['group'], 'area': row['area'], 'floor': row['floor'], 'price': row['price']}
        fill = '#fff7ed' if row['id'] == 7 else '#ffffff'
        for key, _label, x, w in cols:
            body += cell(x, y, w, 40, values[key], fill, f' data-id="{row["id"]}" data-col="{key}"')
    body += tx(8, 230, '기본 3행은 1·7·14번')
    figure1 = (
        '<figure class="learn-chart learn-chart--wide var-chart"><svg id="sheet" viewBox="0 0 640 250" role="img" '
        'aria-labelledby="sheet-title sheet-desc"><title id="sheet-title">표의 행과 열</title>'
        '<desc id="sheet-desc">그림 1. 공통 학습자료 30건 가운데 1번, 7번, 14번입니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 1. 공통 학습자료 30건 중 3건. 번호는 식별자이며 거래 시각이 아닙니다.</figcaption></figure>'
    )

    body = tx(16, 28, '구분별 빈도 · 전체 30건')
    for index, name in enumerate(('주거', '상업')):
        y = 58 + index * 62
        body += tx(16, y, name)
        body += f'<rect data-bar="{index}" x="24" y="{y + 8}" width="210" height="28" rx="6" fill="#93c5fd" stroke="#94a3b8"/>'
        body += tx(234, y + 28, '15건', f' id="var-freq-{index}"')
    body += '<line x1="24" y1="190" x2="250" y2="190" stroke="#64748b"/>'
    for index, (label, x) in enumerate((('0', 24), ('5', 94), ('10', 164), ('15', 234))):
        body += tx(x, 208, label, f' id="var-freq-tick-{index}" text-anchor="middle"')
    body += tx(16, 232, '건수(건)', ' id="var-freq-axis"')
    figure2 = (
        '<figure class="learn-chart learn-chart--wide var-chart"><svg viewBox="0 0 640 250" role="img" '
        'aria-labelledby="frequency-title frequency-desc"><title id="frequency-title">구분별 빈도와 비율</title>'
        '<desc id="frequency-desc">그림 2. 주거 15건, 상업 15건, 각각 50%입니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 2. 건수와 비율은 같은 30건에서 계산합니다. 이 50%는 실제 시장의 거래 비중이 아닙니다.</figcaption></figure>'
    )

    def sx(area):
        return round(48 + area * 0.88, 2)

    def sy(price):
        return round(292 - price * 0.42, 2)

    body = tx(48, 22, '면적과 단가 · 점 하나 = 관측 하나')
    for value in (0, 100, 200, 300, 400, 500):
        y = sy(value)
        body += f'<line x1="48" y1="{y}" x2="330" y2="{y}" stroke="#e2e8f0"/>'
        body += tx(44, y + 4, value, ' text-anchor="end"')
    for value in (0, 100, 200, 300):
        body += tx(sx(value), 314, value, ' text-anchor="middle"')
    for row in rows:
        fill = '#d97706' if row['id'] == 7 else '#2563eb'
        stroke = '#d97706' if row['id'] == 7 else '#1e3a8a'
        width = '3' if row['id'] == 7 else '1'
        body += (
            f'<circle data-id="{row["id"]}" cx="{sx(row["area"])}" cy="{sy(row["price"])}" r="6" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )
    body += tx(250, 338, '면적(㎡)')
    body += tx(48, 354, '단가(만원/㎡)')
    figure3 = (
        '<figure class="learn-chart learn-chart--wide var-chart"><svg id="scatter" viewBox="0 0 640 370" role="img" '
        'aria-labelledby="scatter-title scatter-desc"><title id="scatter-title">면적과 단가의 산점도</title>'
        '<desc id="scatter-desc">그림 3. 공통 학습자료 30건. 기본 강조는 7번, 면적 22㎡, 단가 480만원입니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 3. 각 점은 한 관측입니다. 같은 좌표가 겹치면 여러 점이 한 자리에 보일 수 있습니다. 점은 원인과 결과를 정하지 않습니다.</figcaption></figure>'
    )

    body = tx(16, 28, '별도 가상 자료 100, 120, 미확인')
    body += tx(16, 62, '확인된 2건 · 평균 110')
    body += '<rect data-missing="drop" x="16" y="72" width="220" height="28" rx="6" fill="#93c5fd" stroke="#d97706" stroke-width="3"/>'
    body += tx(16, 132, '0으로 가정한 3건 · 평균 73.33')
    body += '<rect data-missing="zero" x="16" y="142" width="146.7" height="28" rx="6" fill="#cbd5e1" stroke="#94a3b8"/>'
    body += '<line x1="16" y1="190" x2="250" y2="190" stroke="#64748b"/>'
    body += tx(16, 210, '0') + tx(236, 210, '110')
    body += tx(16, 234, '막대 길이는 평균(만원/㎡)에 비례')
    figure4 = (
        '<figure class="learn-chart learn-chart--wide var-chart"><svg id="missing-chart" viewBox="0 0 640 250" role="img" '
        'aria-labelledby="missing-title missing-desc"><title id="missing-title">결측 처리와 평균</title>'
        '<desc id="missing-desc">그림 4. 확인된 두 값의 평균은 110, 미확인을 0으로 바꾸면 약 73.33입니다.</desc>'
        f'{body}</svg><figcaption class="learn-chart__caption">그림 4. 공통 학습자료 30건과 다른 가상 자료입니다. 0으로 바꾼 값은 원자료에 저장하지 않습니다.</figcaption></figure>'
    )

    controls1 = (
        '<div class="var-controls" hidden><div class="var-shortcuts">'
        '<button type="button" data-row-button="1">1번 행</button>'
        '<button type="button" data-row-button="7" aria-pressed="true">7번 행</button>'
        '<button type="button" data-row-button="14">14번 행</button>'
        '</div><div class="var-shortcuts">'
        '<button type="button" data-col-button="group">구분</button>'
        '<button type="button" data-col-button="area" aria-pressed="true">면적</button>'
        '<button type="button" data-col-button="floor">층</button>'
        '<button type="button" data-col-button="price">단가</button>'
        '</div><p><label>관측번호 <input class="var-id" type="number" min="1" max="30" step="1" value="7"></label></p>'
        '<p role="status" id="var-row-status"></p></div>'
    )
    controls2 = (
        '<div class="var-controls" hidden><div class="var-shortcuts">'
        '<button type="button" data-freq="count" aria-pressed="true">건수</button>'
        '<button type="button" data-freq="share">비율</button>'
        '</div><p role="status" id="var-freq-status"></p></div>'
    )
    controls4 = (
        '<div class="var-controls" hidden><div class="var-shortcuts">'
        '<button type="button" data-missing-button="drop" aria-pressed="true">확인된 값만</button>'
        '<button type="button" data-missing-button="zero">결측을 0으로</button>'
        '</div><p role="status" id="var-missing-status"></p></div>'
    )
    parts = []

    def sec(section_id, label, title, section_body):
        parts.append(
            f'<section class="learn-chapter__step" id="{section_id}" data-toc-label="{label}">'
            f'<p class="learn-chapter__label">{label}</p><h2>{title}</h2>{section_body}</section>'
        )

    sec('quick-start', '서두 · 학습목표', '숫자를 계산하기 전에 무엇을 기록한 숫자인지부터 알아야 합니다',
        '<p>어떤 지역에서 토지 거래가 100건 발생했다고 가정해 보겠습니다. 평균 거래단가를 계산하기 전에, 100건이 서로 다른 토지 100필지인지 확인해야 합니다. 같은 토지가 두 번 거래되었을 수 있습니다. 거래면적 100이 100㎡인지 100평인지도, 거래단가의 빈칸이 0원인지 0이 아닌 미기록인지도 다릅니다.</p>'
        '<p>숫자 자체는 정확하더라도 그 숫자가 무엇을 의미하는지 잘못 이해하면 통계분석의 결론도 잘못될 수 있습니다. 통계학의 첫걸음은 복잡한 수식이 아니라, 한 행이 무엇을 나타내고 각 열에 어떤 정보가 기록되어 있는지 아는 일입니다.</p>'
        '<ul class="learn-objectives"><li>데이터와 관측값의 의미를 이해합니다.</li><li>표의 행과 열, 관측 단위와 변수를 구별합니다.</li><li>범주형 변수와 수치형 변수의 차이를 알아봅니다.</li><li>이산형과 연속형 변수를 구별합니다.</li><li>명목·서열·등간·비율척도를 이해합니다.</li><li>변수의 정의와 측정 단위가 중요한 이유를 알아봅니다.</li><li>결측값과 실제 0의 차이를 이해합니다.</li><li>CH2 Macro의 거래 목록과 요약표를 읽는 방법을 배웁니다.</li></ul>')
    sec('what-data', '데이터란 무엇일까요?', '관찰하거나 측정한 결과를 기록한 것입니다',
        '<p><strong>데이터</strong>는 어떤 대상에 대해 관찰하거나 측정한 결과를 기록한 것입니다. 숫자일 수도 있고 문자, 날짜, 범주일 수도 있습니다. 아래 표는 개념을 보이기 위한 가상 예시이며, 공통 학습자료 30건과는 별개입니다.</p>'
        '<table class="var-table"><caption>가상 거래 3건</caption><thead><tr><th>거래번호</th><th>구분</th><th>면적(㎡)</th><th>층</th><th>단가(만원/㎡)</th></tr></thead><tbody>'
        '<tr><td>1</td><td>주거</td><td>84</td><td>5</td><td>210</td></tr>'
        '<tr><td>2</td><td>주거</td><td>59</td><td>12</td><td>260</td></tr>'
        '<tr><td>3</td><td>상업</td><td>120</td><td>2</td><td>350</td></tr></tbody></table>'
        '<p>각 행은 하나의 거래이고, 각 열은 거래번호·구분·면적·층·단가입니다. 행과 열이 만나는 칸의 값을 <strong>관측값</strong>이라고 합니다. 첫 행의 면적 84는 그 거래의 면적 관측값이고, 면적 열 전체는 여러 거래에서 공통으로 측정한 <strong>변수</strong>입니다.</p>')
    sec('observations', '관측 단위와 변수', '한 행은 무엇을 나타내고, 한 열은 무엇을 나타낼까요?',
        '<p><strong>관측 단위</strong>는 데이터를 기록하는 기본 대상입니다. 거래 목록의 한 행은 거래 기록이고, 토지대장은 필지 또는 대장 기록, 건축물대장은 그 대장 종류의 건축물 기록, 단지 통계는 단지, 지역별 월간 통계는 특정 지역의 특정 월일 수 있습니다. 행이 100개라고 부동산이 100개 있는 것은 아닙니다.</p>'
        '<p>같은 건물이 2024년과 2026년에 한 번씩 거래되면 거래 목록에는 두 행이 생깁니다. 거래 건수는 2건이고 서로 다른 건물 수는 1개입니다. 같은 자료라도 어떻게 묶느냐에 따라 관측 단위가 바뀝니다.</p>'
        '<p>이 과정은 공통 학습자료 30건을 여러 장에서 다시 씁니다. 그림 1은 그중 1번, 7번, 14번입니다. 7번은 구분 상업, 면적 22㎡, 층 1, 단가 480만원/㎡입니다. 관측번호는 자료를 구별하는 식별자이며 거래 시각이 아닙니다.</p>'
        + controls1 + figure1 +
        '<details><summary>관측번호도 변수일까요?</summary><p>관측번호도 표에 기록된 열이므로 데이터 항목으로 관리할 수 있습니다. 다만 시장 특성을 설명하는 수량과, 관측을 구별하는 식별자는 다릅니다. 거래번호의 평균 2가 시장을 설명하지는 않습니다. 식별자를 특별한 근거 없이 회귀의 입력에 넣는 일도 주의합니다.</p></details>')
    sec('types', '변수의 두 가지 기본 유형', '종류를 나타내는 변수와 크기를 나타내는 변수는 다릅니다',
        '<p><strong>범주형 변수</strong>는 용도지역, 지목, 건물 구조, 주거·상업, 거래 유형처럼 종류를 나타냅니다. 각 범주에 몇 건이 있는지를 <strong>빈도</strong>라고 하고, 전체에서 차지하는 비율도 계산합니다. 비율은 해당 범주의 관측수 ÷ 전체 관측수 × 100입니다. 주거는 15/30×100=50%이고 상업도 같습니다.</p>'
        + controls2 + '<section id="frequency">' + figure2 + '</section>' +
        '<p>이 자료는 계산을 연습하는 학습 예제입니다. 주거와 상업이 절반씩이라는 결과를 실제 시장의 거래 비중으로 읽지 않습니다.</p>')
    sec('numeric', '수치형 변수', '숫자의 크기와 차이에 의미가 있는 변수입니다',
        '<p><strong>수치형 변수</strong>는 토지면적, 거래금액, 거래단가, 건축연도, 거래 건수, 주차대수처럼 측정하거나 세어서 얻은 수량입니다. 이산형은 거래 건수처럼 셀 수 있는 값입니다. 일반적인 거래 건수에서 1.5건이라는 개별 관측은 없습니다. 연속형은 면적처럼 측정 정밀도에 따라 84㎡, 84.2㎡, 84.23㎡로 적을 수 있는 값입니다. 면적이 84라는 정수로 적혀 있어도 거래 건수처럼 이산형이 되지는 않습니다.</p>'
        '<p>층은 보통 정수로 기록됩니다. 1층과 2층의 높이 차이와 20층과 21층의 높이 차이가 같다고 보장할 수 없고, 지하층이나 건너뛴 번호도 있을 수 있습니다. 숫자로 적혀 있어도 그 숫자가 무엇을 측정하는지 확인합니다.</p>')
    sec('codes', '숫자로 기록되어도 범주형일 수 있습니다', '코드번호는 수량이 아니라 이름표일 수 있습니다',
        '<p>용도지역을 1·2·3으로 저장해도 코드가 1에서 3으로 늘었다고 용도가 세 배 커진 것은 아닙니다. 코드의 평균이 2라고 평균 용도가 제2종일반주거지역인 것도 아닙니다. 법정동 코드와 지목 코드도 종류를 구별하는 이름표입니다.</p>'
        '<p>예외로 주거를 1, 상업을 0으로 두면 15건과 15건의 평균은 (15×1+15×0)/30=0.5입니다. 이 0.5는 1로 표시한 주거의 비율 50%로 읽을 수 있습니다. 중요한 것은 숫자의 모양이 아니라 숫자에 부여된 의미입니다.</p>')
    sec('scales', '측정척도', '어떤 비교가 의미 있는지를 구분합니다',
        '<table class="var-table"><caption>네 가지 측정척도</caption><thead><tr><th>척도</th><th>예시</th><th>가능한 해석</th></tr></thead><tbody>'
        '<tr><td>명목척도</td><td>지목·용도 구분</td><td>같은 종류인지 구분</td></tr>'
        '<tr><td>서열척도</td><td>낮음·보통·높음</td><td>순서 비교</td></tr>'
        '<tr><td>등간척도</td><td>섭씨온도</td><td>값의 차이 비교</td></tr>'
        '<tr><td>비율척도</td><td>면적·거래금액</td><td>차이와 비율 비교</td></tr></tbody></table>'
        '<p>명목척도는 대와 답을 구별하지만 대가 답보다 두 배라고 말하지 않습니다. 서열척도는 높음이 보통보다 높은 단계라는 것은 알 수 있어도, 단계 사이 간격이 같다고 볼 근거는 없습니다. 등간척도인 섭씨 20℃와 10℃의 차이는 10℃이지만, 20℃가 두 배 덥다는 뜻은 아닙니다. 0℃가 열이 없는 절대 기준이 아니기 때문입니다. 비율척도인 100㎡는 50㎡의 두 배이고, 0㎡는 면적이 없는 상태입니다.</p>'
        '<details><summary>서열척도의 평균은 계산하면 안 될까요?</summary><p>1·2·3을 붙이면 수학적으로 평균을 계산할 수 있습니다. 단계 사이 간격이 같다는 근거가 없으면 평균의 해석에 주의합니다. 서열형 자료에서는 범주별 비율과 중앙 범주, 분포를 함께 봅니다. 척도는 계산을 무조건 막거나 허용하는 규칙이 아니라, 결과를 어떻게 읽을 수 있는지 판단하는 기준입니다.</p></details>')
    sec('units', '단위는 왜 중요할까요?', '같은 100이라도 전혀 다른 크기일 수 있습니다',
        '<p>면적 100이 100㎡인지 100평인지에 따라 크기가 다릅니다. 단위가 모두 ㎡여도 대지면적, 전용면적, 연면적, 거래 대상 면적은 서로 다른 정의일 수 있습니다. 단위가 같다는 사실과 측정 대상의 정의가 같다는 사실은 구분합니다.</p>'
        '<p>거래금액 24,000만원을 거래면적 1,111㎡로 나누면 약 21.60만원/㎡입니다. 화면의 단가 21.6은 이 나눗셈을 소수 한 자리로 보인 값입니다. 면적 기준이 달라지면 같은 거래금액에서도 단가가 달라집니다.</p>')
    sec('scatter-plot', '산점도에서 행과 열 읽기', '표의 한 행은 그래프의 한 점이 될 수 있습니다',
        '<p>산점도는 두 수치형 변수를 좌표로 나타낸 그림입니다. 면적 100㎡, 단가 200만원/㎡이면 가로 100, 세로 200에 점을 찍습니다. 공통 학습자료 30건이면 점도 30개입니다. 같은 좌표가 있으면 화면에서 겹칠 수 있습니다. 그림 1에서 고른 관측은 이 산점도에서도 같은 점으로 표시됩니다.</p>'
        + figure3 +
        '<p>면적이 큰 쪽의 단가가 낮아 보여도, 면적이 커지면 단가가 반드시 내린다고 결론 내리지는 않습니다. 다른 변수, 표본 구성, 우연한 변동이 있을 수 있습니다. 점은 관측값이지 원인과 결과를 자동으로 설명하지 않습니다.</p>')
    sec('dictionary', '자료 사전', '열 이름만으로 뜻을 알 수 없다면 설명이 필요합니다',
        '<p>변수의 정의를 적은 설명서를 <strong>자료 사전</strong>이라고 합니다.</p>'
        '<table class="var-table"><caption>자료 사전에 적을 수 있는 항목</caption><thead><tr><th>항목</th><th>기록 예시</th></tr></thead><tbody>'
        '<tr><td>변수명</td><td>거래면적</td></tr><tr><td>정의</td><td>해당 거래에서 기록된 대상 면적</td></tr>'
        '<tr><td>자료 유형</td><td>수치형</td></tr><tr><td>단위</td><td>㎡</td></tr>'
        '<tr><td>허용값</td><td>0보다 큰 면적</td></tr><tr><td>결측 표시</td><td>미확인 또는 NULL</td></tr>'
        '<tr><td>기준</td><td>면적 정의와 원천자료의 기준</td></tr></tbody></table>'
        '<p>같은 이름이어도 원천마다 정의가 다를 수 있습니다. 거래금액과 거래단가, 건축연도와 사용승인일, 범주 코드의 의미, 결측과 해당 없음과 0, 원천자료와 기준일을 구별합니다. 거래 DB와 대장 DB에 같은 이름의 열이 있어도 의미와 기준시점이 다를 수 있습니다.</p>')
    sec('missing', '결측값이란 무엇인가요?', '기록되지 않은 값과 실제 0은 다릅니다',
        '<p><strong>결측값</strong>은 기록되어야 할 값이 없거나 확인되지 않은 상태입니다. 건축연도가 미확인이라고 건축연도가 0년인 것은 아니고, 거래금액이 빈칸이라고 0원인 것도 아닙니다. 조사하지 못한 경우, 입력이 누락된 경우, 그 변수 자체가 해당하지 않는 경우는 서로 다른 의미입니다. 가능한 때는 원인을 구별합니다.</p>')
    sec('missing-zero', '결측값을 0으로 바꾸면 어떻게 될까요?', '없는 값을 만들어 평균을 바꾸게 됩니다',
        '<p>단가 100, 120, 미확인인 세 건은 공통 학습자료와 별개입니다. 확인된 두 값의 평균은 (100+120)/2=110입니다. 미확인을 0으로 바꾸면 (100+120+0)/3≈73.33입니다. 단가 0인 거래를 새로 확인한 것이 아니라, 알 수 없는 값을 임의로 0으로 넣어서 평균이 낮아진 것입니다. 어느 쪽이 세 거래의 실제 평균에 더 가까운지는 세 번째 단가를 모르므로 확정할 수 없습니다. 결측을 뺀 평균이 곧바로 전체의 올바른 평균이라는 뜻도 아닙니다.</p>'
        + controls4 + figure4)
    sec('missing-rows', '그렇다면 결측값이 있는 행은 삭제하면 될까요?', '남은 자료의 구성도 달라질 수 있습니다',
        '<p>결측이 있는 행을 모두 빼는 일이 언제나 가장 좋은 방법은 아닙니다. 100건 가운데 건축연도 미확인 30건이 대부분 오래된 건물이라면, 그 행을 뺀 자료는 신축에 치우칠 수 있습니다. 어느 변수에 몇 건이 빠졌는지, 특정 지역이나 유형에 몰려 있는지, 유효 표본수가 얼마나 줄었는지, 대체할 근거가 있는지, 처리 방법을 바꾸면 결과가 달라지는지를 함께 봅니다. 완전사례 분석, 적절한 대체, 결측 여부를 따로 나타내는 방법이 있고, 모든 상황에 하나의 정답은 없습니다.</p>')
    sec('duplicates', '중복 자료도 확인해야 합니다', '값이 같다고 반드시 같은 거래는 아닙니다',
        '<p>면적 100㎡, 거래금액 3억원이 두 행에 있어도 바로 한 행을 지우지는 않습니다. 서로 다른 부동산이 우연히 같은 값일 수도 있고, 같은 거래가 두 번 수집된 것일 수도 있습니다. 계약일, 위치, 거래유형, 식별 정보와 원천 기록을 확인합니다. 같은 부동산의 반복 거래와 잘못 중복 수집된 기록은 다릅니다. 정제의 목적은 비슷한 숫자를 지우는 일이 아니라, 각 기록이 무엇을 나타내는지 유지하는 일입니다.</p>')
    sec('shared-check', '공통 학습자료의 계산 확인', '앞으로 여러 장에서 사용할 30건의 자료입니다',
        '<table class="var-table"><caption>공통 학습자료 30건</caption><thead><tr><th>항목</th><th>내용</th></tr></thead><tbody>'
        '<tr><td>관측수</td><td>30건</td></tr><tr><td>구분</td><td>주거 15건·상업 15건</td></tr>'
        '<tr><td>구분별 비율</td><td>각각 50%</td></tr><tr><td>면적 범위</td><td>22~310㎡</td></tr>'
        '<tr><td>단가 범위</td><td>62~480만원/㎡</td></tr></tbody></table>'
        '<p>공통 자료는 실제 거래 원천, 거래 시점, 구체적인 면적 정의가 확인되지 않은 학습 예제입니다. 그림의 단위는 교재의 예제상 단위이며, 특정 지역의 시장 수준이나 시점별 변화를 설명하지 않습니다.</p>'
        '<p><a href="../example-data.json">공통 학습자료 원본 JSON 확인</a></p>')
    sec('macro', 'CH2 Macro에서 읽기', '거래 목록과 요약표는 한 행의 의미가 다릅니다',
        '<p>거래 목록의 한 행은 개별 거래 기록입니다. 용도지역과 지목별 기본통계표의 한 칸은 여러 거래를 묶은 요약일 수 있습니다. 아래 캡처는 CH2 Macro 토지 통계의 롤링 구간별 평균 변동 창에서 거래 목록을 연 화면입니다. 용도 자녹, 지목 답, 전체 394건, 이상치 제외 안 함으로 보입니다. 이 건수와 금액은 촬영 당시의 예시이며 현재 운영통계나 공통 학습자료 30건이 아닙니다.</p>'
        '<figure class="learn-capture"><a href="../assets/captures/land-heungdeok-transactions.png" target="_blank" rel="noopener" aria-label="토지 거래 목록 화면 크게 보기"><img src="../assets/captures/land-heungdeok-transactions.png" width="1229" height="679" loading="lazy" alt="CH2 Macro 토지 거래 목록. 용도 자녹·지목 답, 전체 394건, 이상치 제외 안 함. 계약일·지역·지번·면적·금액·단가·도로·지분·유형 열이 보입니다."/></a>'
        '<figcaption class="learn-capture__caption">토지 거래 목록의 화면 예시입니다. 첫 행은 면적 1,111㎡, 금액 24,000만원, 단가 21.6입니다. <a href="../assets/captures/land-heungdeok-transactions.png" target="_blank" rel="noopener">원본 크게 보기</a></figcaption></figure>'
        '<ol class="learn-screen-reading"><li><strong>무엇을 한 건으로 계산했나요?</strong> 거래 한 건과 필지 한 개, 건물 한 개는 같지 않을 수 있습니다.</li>'
        '<li><strong>무엇으로 자료를 구분했나요?</strong> 용도지역, 지목, 도로 조건, 거래 유형은 범주나 조건일 수 있습니다. 도로 조건의 8미만은 하나의 구간 범주일 수 있습니다.</li>'
        '<li><strong>어떤 크기를 측정했나요?</strong> 면적, 거래금액, 거래단가의 기준을 확인합니다. 면적 기준이 달라지면 단가도 달라집니다.</li>'
        '<li><strong>결측과 제외는 어떻게 처리되었나요?</strong> 미확인 값과 이상치 제외, 계산에 쓴 건수를 확인합니다. 캡처의 — 는 0으로 읽지 않습니다.</li>'
        '<li><strong>요약표에서는 무엇을 평균했나요?</strong> 평균단가가 거래별 단가의 단순평균인지, 다른 가중을 썼는지는 그 화면의 계산을 확인합니다.</li>'
        '<li><strong>거래 DB와 대장 DB를 연결했다면?</strong> 관측 단위와 기준시점이 다릅니다. 같은 필지의 여러 거래, 한 건물의 여러 필지가 있을 수 있습니다.</li></ol>'
        '<p>통계 결과를 읽을 때 먼저 할 일은 숫자의 크기를 비교하는 일이 아니라, 무엇을 세고 무엇을 측정한 결과인지 확인하는 일입니다.</p>'
        '<p><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>'
        '<details><summary>확인한 서비스 범위</summary><p>확인한 <code>compute_stats</code>는 유한한 단가 목록의 산술평균이고, 숫자가 아닌 값은 그 평균에서 뺍니다. 이번 장의 0 대체는 그 함수가 원자료에 0을 넣는 기능이 아닙니다. 이 확인을 모든 화면이 같은 가중 방식을 쓴다는 뜻으로 확대하지 않습니다. 거래 DB와 대장 DB의 연결 규칙은 이번 학습 페이지에서 바꾸지 않았습니다.</p></details>')
    questions = [
        ('주거를 1, 상업을 2로 기록한 변수의 평균이 1.5입니다. 이를 중간 용도라고 해석할 수 있을까요?', '<strong>그렇지 않습니다.</strong> 1과 2는 용도를 구별하는 코드입니다. 주거와 상업의 중간 용도를 나타내는 수치가 아닙니다. 범주별 건수와 비율을 확인합니다.'),
        ('같은 건물이 두 번 거래되어 거래 목록에 두 행이 있습니다. 건물도 두 개일까요?', '<strong>아닙니다.</strong> 거래 건수는 두 건이지만 서로 다른 건물 수는 하나입니다. 관측 단위가 거래인지 건물인지에 따라 결과가 달라집니다.'),
        ('면적이 84와 84.00으로 기록되어 있으면 서로 다른 유형의 변수일까요?', '<strong>그렇지 않습니다.</strong> 표시 자릿수가 다를 뿐 모두 면적이라는 측정값입니다.'),
        ('단가가 100, 120, 미확인이라면 세 번째 값을 0으로 바꾸어 평균 73.33을 사용해도 될까요?', '<strong>실제 단가가 0이라는 근거 없이 그렇게 처리해서는 안 됩니다.</strong> 확인된 두 값만의 평균은 110입니다. 결측을 뺀 평균도 세 건 전체의 실제 평균이라고 확정할 수는 없습니다.'),
        ('어떤 용도지역의 거래가 20건이라는 사실만으로 다른 용도지역보다 가격 수준이 높다고 판단할 수 있을까요?', '<strong>그렇지 않습니다.</strong> 거래 건수는 빈도입니다. 가격 수준은 거래단가의 분포와 면적, 시점 등 다른 특성을 함께 봅니다.'),
    ]
    sec('practice', '확인 문제', '한 행과 한 열의 의미를 구별해 보세요',
        '<ol class="learn-exercises">' + ''.join(
            f'<li>{question}<details><summary>답과 해설</summary><p>{answer}</p></details></li>' for question, answer in questions
        ) + '</ol>')
    sec('recap', '결론 · 학습 요약', '통계분석의 시작은 표에 적힌 숫자의 의미를 이해하는 일입니다',
        '<ul class="learn-recap-list"><li><strong>데이터:</strong> 관찰하거나 측정한 결과를 기록한 것입니다.</li>'
        '<li><strong>관측 단위:</strong> 한 행이 나타내는 기본 대상입니다.</li>'
        '<li><strong>변수:</strong> 여러 관측에서 공통으로 기록한 특성입니다.</li>'
        '<li><strong>관측값:</strong> 특정 대상에서 기록한 변수의 값입니다.</li>'
        '<li><strong>범주형 변수:</strong> 종류를 나타내며 빈도와 비율로 살펴봅니다.</li>'
        '<li><strong>수치형 변수:</strong> 수량이나 측정값을 나타냅니다.</li>'
        '<li><strong>이산형·연속형:</strong> 세어서 얻는 값과 측정하는 값을 구별합니다.</li>'
        '<li><strong>측정척도:</strong> 순서와 차이, 비율 중 어떤 비교가 의미 있는지 판단합니다.</li>'
        '<li><strong>단위:</strong> 숫자의 의미를 결정하는 정보입니다.</li>'
        '<li><strong>결측값:</strong> 실제 0과 다르며 처리 방법에 따라 결과가 달라질 수 있습니다.</li>'
        '<li><strong>자료 사전:</strong> 정의와 단위, 코드 및 결측 표기를 기록합니다.</li>'
        '<li><strong>요약표:</strong> 원자료를 집계하면 관측 단위와 결과의 의미가 달라질 수 있습니다.</li></ul>'
        '<p>다음 <a href="/learn/stats/population-and-sampling/">2장 「모집단과 표본, 자료 수집과 편향」</a>에서는 자료가 어떤 전체에서 어떻게 모였는지 살펴봅니다. 거래자료가 많아도 특정 유형만 들어 있다면 그 결과를 전체 시장에 그대로 적용하기 어려울 수 있습니다.</p>'
        '<details class="learn-references"><summary>참고자료</summary><ul>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/1-2-data-sampling-and-variation-in-data-and-sampling">OpenStax, Introductory Statistics 2e §1.2</a> — 범주형·수치형 변수와 이산형·연속형 변수</li>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/1-3-frequency-frequency-tables-and-levels-of-measurement">OpenStax, Introductory Statistics 2e §1.3</a> — 빈도 및 측정척도</li>'
        '<li><a href="../example-data.json">공통 학습자료 원본 JSON</a></li></ul>'
        '<p class="learn-source-note">이번 장의 부동산 자료와 계산 예시는 통계 개념을 설명하기 위한 학습자료입니다. 실제 원천과 표집 설계가 확인되지 않은 값은 특정 부동산 시장의 통계로 해석하지 않습니다. 참고자료의 기존 확인일: 2026-10-07.</p></details>')

    page = ROOT / 'data-and-variables' / 'index.html'
    html = page.read_text(encoding='utf-8')
    html = re.sub(
        r'<article.*?</article>',
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="데이터와 변수">' + '\n'.join(parts) + '</article>',
        html, count=1, flags=re.S,
    )
    html = html.replace(
        'aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>',
        'aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span>',
        1,
    )
    if 'data-and-variables/chapter.css' not in html:
        html = html.replace('</head>', '<link rel="stylesheet" href="/learn/stats/data-and-variables/chapter.css?v=20261026-1" /></head>')
    blob = '<script type="application/json" id="var-data">' + json.dumps(page_data, ensure_ascii=False) + '</script>'
    if 'id="var-data"' not in html:
        html = html.replace('</body>', blob + '\n</body>')
    if 'data-and-variables/experiment.js' not in html:
        html = html.replace('</body>', '<script type="module" src="/learn/stats/data-and-variables/experiment.js?v=20261026-2"></script>\n</body>')
    html = html.replace('experiment.js?v=20261026-1', 'experiment.js?v=20261026-2')
    if html.count('<svg ') != 4 or html.count('<circle ') != 30:
        raise SystemExit(f'svg={html.count("<svg ")} circles={html.count("<circle ")}')
    if html.count('<summary>답과 해설</summary>') != 5 or '[그림 ' in html:
        raise SystemExit('exercise or placeholder mismatch')
    if '★☆☆ 심화' not in html or 'Macro 활용도 3단계, 핵심' not in html:
        raise SystemExit('relevance text changed incorrectly')
    if 'land-heungdeok-transactions.png' not in html or 'population-and-sampling/' not in html:
        raise SystemExit('capture or next chapter missing')
    page.write_text(html, encoding='utf-8')
    promote(ROOT / 'course.json')
    promote(ROOT / 'learn-stats-toc.js')
    listing = ROOT / 'index.html'
    listing_text = listing.read_text(encoding='utf-8')
    old_link = 'data-macro-relevance="2"><a href="/learn/stats/data-and-variables/">01. 데이터와 변수 <span class="learn-relevance" aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>'
    new_link = old_link.replace('data-macro-relevance="2"', 'data-macro-relevance="3"').replace('2단계, 권장', '3단계, 핵심').replace('★★☆', '★★★')
    if old_link not in listing_text and new_link not in listing_text:
        raise SystemExit('course listing relevance missing')
    if old_link in listing_text:
        listing.write_text(listing_text.replace(old_link, new_link, 1), encoding='utf-8')
    print('chapter 1 rebuilt', 'row7', row7['area'], row7['price'], 'unit', round(24000 / 1111, 2))


if __name__ == '__main__':
    build()
