"""Chapter 3 body. Reuses example-data.json and the checked chart coordinates."""
from pathlib import Path
from html import escape
from statistics import median
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
BLOCK = '''        "slug": "graphs",
        "title": "그래프로 보는 데이터와 분포",
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


def num(value):
    return f'{value:.10f}'.rstrip('0').rstrip('.') or '0'


def tx(x, y, text, extra=''):
    return f'<text x="{x}" y="{y}"{extra}>{escape(str(text))}</text>'


def bins_for(rows, width):
    found = []
    for low in range(60, 540, width):
        ids = [row['id'] for row in rows if low <= row['price'] < low + width]
        found.append({'low': low, 'high': low + width, 'count': len(ids), 'ids': ids})
    return found


def build():
    rows = json.loads((ROOT / 'example-data.json').read_text(encoding='utf-8'))['rows']
    assert len(rows) == 30
    assert sum(row['group'] == '주거' for row in rows) == 15
    assert sum(row['group'] == '상업' for row in rows) == 15
    assert min(row['area'] for row in rows) == 22 and max(row['area'] for row in rows) == 310
    assert min(row['price'] for row in rows) == 62 and max(row['price'] for row in rows) == 480
    row7 = next(row for row in rows if row['id'] == 7)
    assert (row7['group'], row7['area'], row7['floor'], row7['price']) == ('상업', 22, 1, 480)
    ordered = sorted(row['price'] for row in rows)
    q1, q2, q3 = median(ordered[:15]), median(ordered), median(ordered[15:])
    assert (q1, q2, q3) == (98, 122, 168)
    assert q3 - q1 == 70
    low_fence, high_fence = q1 - 1.5 * 70, q3 + 1.5 * 70
    assert (low_fence, high_fence) == (-7, 273)
    inside = [value for value in ordered if low_fence <= value <= high_fence]
    assert (min(inside), max(inside)) == (62, 268)
    bins = {str(width): bins_for(rows, width) for width in (30, 60, 120)}
    assert [item['count'] for item in bins['60']] == [14, 10, 3, 2, 0, 0, 0, 1]
    assert [item['count'] for item in bins['120']] == [24, 5, 0, 1]
    assert all(sum(item['count'] for item in bins[key]) == 30 for key in bins)
    assert 7 in bins['60'][-1]['ids']
    assert not any(row['price'] == 120 and row['price'] < 120 for row in rows)
    page_data = {
        'rows': rows,
        'bins': bins,
    }

    def fig1():
        body = tx(16, 22, '주거·상업 · 축은 0부터')
        for index, name in enumerate(('주거', '상업')):
            y = 48 + index * 58
            body += tx(16, y, name)
            body += f'<rect data-bar="{index}" x="24" y="{y + 8}" width="180" height="26" fill="#93c5fd" stroke="#64748b"/>'
            body += tx(210, y + 26, '15건', f' data-freq-label="{index}"')
        body += '<line x1="24" y1="180" x2="204" y2="180" stroke="#64748b"/>'
        for index, (label, x) in enumerate((('0', 24), ('5', 84), ('10', 144), ('15', 204))):
            body += tx(x, 198, label, f' data-freq-tick="{index}" text-anchor="middle"')
        body += tx(16, 220, '건수(건) · 0부터', ' id="grp-freq-axis"')
        return (
            '<figure class="learn-chart learn-chart--wide grp-chart"><svg id="grp-bars" viewBox="0 0 640 240" role="img" '
            'aria-labelledby="category-bars-title category-bars-desc"><title id="category-bars-title">범주별 막대그래프</title>'
            '<desc id="category-bars-desc">그림 1. 주거 15건, 상업 15건. 가로축은 0부터입니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 1. 막대 길이는 건수 또는 비율입니다. 두 범주의 건수가 같다고 단가가 같은 것은 아닙니다.</figcaption></figure>'
        )

    def fig2():
        body = tx(16, 22, '거래단가 히스토그램 · 건수')
        body += '<line x1="70" y1="230" x2="610" y2="230" stroke="#64748b"/>'
        for value, y in ((0, 230), (10, 180), (20, 130)):
            body += f'<line x1="64" y1="{y}" x2="70" y2="{y}" stroke="#64748b"/>'
            body += tx(58, y + 4, value, ' text-anchor="end"')
        for width, items in ((30, bins['30']), (60, bins['60']), (120, bins['120'])):
            for index, item in enumerate(items):
                height = item['count'] * 5
                x = 70 + index * width * 1.1
                opacity = '1' if width == 60 else '0'
                events = 'auto' if width == 60 else 'none'
                stroke = '#d97706' if width == 60 and index == 0 else '#64748b'
                thick = '3' if width == 60 and index == 0 else '1'
                body += (
                    f'<rect data-bin-width="{width}" data-count="{item["count"]}" data-low="{item["low"]}" '
                    f'x="{num(x)}" y="{num(230 - height)}" width="{num(max(width * 0.9, 8))}" height="{num(height)}" '
                    f'fill="#93c5fd" stroke="{stroke}" stroke-width="{thick}" opacity="{opacity}" pointer-events="{events}"/>'
                )
        for index in range(4):
            body += tx(70, 248, '', f' data-hist-tick="{index}" text-anchor="middle"')
        body += tx(16, 270, '단가 구간 시작(만원/㎡)')
        return (
            '<figure class="learn-chart learn-chart--wide grp-chart"><svg id="grp-histogram" viewBox="0 0 640 290" role="img" '
            'aria-labelledby="histogram-widths-title histogram-widths-desc"><title id="histogram-widths-title">구간 폭에 따른 히스토그램</title>'
            '<desc id="histogram-widths-desc">그림 2. 폭 60은 14, 10, 3, 2, 0, 0, 0, 1건. 폭 120은 24, 5, 0, 1건. 빈 구간도 자리를 둡니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 2. 같은 30건입니다. 구간은 왼쪽을 포함하고 오른쪽을 빼며 60부터 시작합니다. 세로축은 건수입니다.</figcaption></figure>'
        )

    def fig3():
        cards = [
            ('symmetric', 36, '대칭', ((8, 8), (20, 16), (36, 28), (20, 16), (8, 8))),
            ('right', 112, '오른쪽 꼬리', ((28, 28), (20, 18), (12, 12), (8, 8), (4, 4))),
            ('peaks', 188, '두 봉우리', ((8, 8), (24, 22), (8, 8), (24, 22), (8, 8))),
        ]
        body = tx(16, 22, '분포 개념도 · 공통 30건이 아님')
        for key, y, label, bars in cards:
            fill = '#fff7ed' if key == 'symmetric' else '#ffffff'
            stroke = '#d97706' if key == 'symmetric' else '#94a3b8'
            thick = '3' if key == 'symmetric' else '1'
            body += f'<rect data-shape="{key}" data-role="card" x="8" y="{y}" width="320" height="68" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="{thick}"/>'
            body += tx(16, y + 22, label)
            for index, (bar_h, _) in enumerate(bars):
                body += f'<rect x="{100 + index * 28}" y="{y + 50 - bar_h}" width="22" height="{bar_h}" fill="#93c5fd" stroke="#64748b" pointer-events="none"/>'
        return (
            '<figure class="learn-chart learn-chart--wide grp-chart"><svg id="grp-shapes" viewBox="0 0 640 270" role="img" '
            'aria-labelledby="distribution-shapes-title distribution-shapes-desc"><title id="distribution-shapes-title">분포의 세 가지 모양</title>'
            '<desc id="distribution-shapes-desc">그림 3. 대칭, 오른쪽 꼬리, 두 봉우리의 개념도입니다. 공통 학습자료의 히스토그램이 아닙니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 3. 막대 높이는 설명을 위해 정한 값입니다. 공통 30건이나 실제 시장의 밀도가 아닙니다.</figcaption></figure>'
        )

    def fig4():
        body = tx(16, 22, '면적–단가 · 원=주거 · 사각형=상업')
        for value in (0, 100, 200, 300, 400, 500):
            y = 285 - value * 0.42
            body += f'<line x1="70" y1="{num(y)}" x2="250" y2="{num(y)}" stroke="#e2e8f0"/>'
            body += tx(64, y + 4, value, ' text-anchor="end"')
        for value in (0, 50, 100, 150):
            body += tx(70 + value * 1.6, 308, value, ' text-anchor="middle"')
        body += tx(180, 328, '면적(㎡)')
        body += tx(16, 348, '단가(만원/㎡)')
        for row in rows:
            cx = 70 + row['area'] * 1.6
            cy = 285 - row['price'] * 0.42
            on = row['id'] == 7
            stroke = '#d97706' if on else '#1e3a8a'
            thick = '3' if on else '1'
            if row['group'] == '주거':
                body += (
                    f'<circle data-observation="{row["id"]}" cx="{num(cx)}" cy="{num(cy)}" r="4.5" '
                    f'fill="#2563eb" stroke="{stroke}" stroke-width="{thick}"/>'
                )
            else:
                fill = '#d97706' if on else '#64748b'
                body += (
                    f'<rect data-observation="{row["id"]}" x="{num(cx - 4.5)}" y="{num(cy - 4.5)}" width="9" height="9" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="{thick}"/>'
                )
        return (
            '<figure class="learn-chart learn-chart--wide grp-chart"><svg id="grp-scatter" viewBox="0 0 640 370" role="img" '
            'aria-labelledby="grouped-scatter-title grouped-scatter-desc"><title id="grouped-scatter-title">면적과 단가의 산점도</title>'
            '<desc id="grouped-scatter-desc">그림 4. 공통 30건. 주거는 원, 상업은 사각형, 7번은 주황 사각형입니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 4. 한 점은 한 관측입니다. 같은 좌표는 겹칠 수 있습니다. 번호 순서로 점을 잇지 않습니다.</figcaption></figure>'
        )

    def fig5():
        body = [
            tx(16, 24, '단가 상자그림 · 1.5×IQR'),
            '<line x1="122" y1="100" x2="328" y2="100" stroke="#475569"/>',
            '<rect data-part="iqr" x="158" y="80" width="70" height="40" fill="#93c5fd" stroke="#64748b"/>',
            '<line data-part="median" x1="182" y1="80" x2="182" y2="120" stroke="#1d4ed8" stroke-width="3"/>',
            '<line data-part="low" x1="122" y1="90" x2="122" y2="110" stroke="#475569"/>',
            '<line data-part="high" x1="328" y1="90" x2="328" y2="110" stroke="#475569"/>',
            '<line data-part="q1" x1="158" y1="76" x2="158" y2="124" stroke="#475569"/>',
            '<line data-part="q3" x1="228" y1="76" x2="228" y2="124" stroke="#475569"/>',
            '<circle data-part="extreme" cx="540" cy="100" r="5" fill="#d97706" stroke="#d97706" stroke-width="3"/>',
            tx(122, 144, '62', ' text-anchor="middle"'),
            tx(158, 68, 'Q1 98', ' text-anchor="middle"'),
            tx(182, 148, '122', ' text-anchor="middle"'),
            tx(228, 68, 'Q3 168', ' text-anchor="middle"'),
            tx(328, 144, '268', ' text-anchor="middle"'),
            tx(540, 78, '480', ' text-anchor="middle"'),
            '<line x1="60" y1="190" x2="580" y2="190" stroke="#cbd5e1"/>',
        ]
        for label, x in (('0', 60), ('100', 160), ('200', 260), ('300', 360), ('400', 460), ('500', 560)):
            body.append(tx(x, 208, label, ' text-anchor="middle"'))
        body.append(tx(16, 230, '단가(만원/㎡)'))
        return (
            '<figure class="learn-chart learn-chart--wide grp-chart"><svg id="grp-box" viewBox="0 0 640 250" role="img" '
            'aria-labelledby="box-summary-title box-summary-desc"><title id="box-summary-title">거래단가 상자그림</title>'
            '<desc id="box-summary-desc">그림 5. Q1 98, 중앙값 122, Q3 168. 수염은 62와 268, 480은 별도 점입니다.</desc>'
            f'{"".join(body)}</svg><figcaption class="learn-chart__caption">그림 5. 아래 15개와 위 15개의 중앙값으로 사분위수를 구했습니다. 수염은 경계 안의 실제 관측까지입니다.</figcaption></figure>'
        )

    def sec(sid, label, title, inner):
        return (
            f'<section class="learn-chapter__step" id="{sid}" data-toc-label="{escape(label)}">'
            f'<p class="learn-chapter__label">{escape(label)}</p><h2>{escape(title)}</h2>{inner}</section>'
        )

    table_rows = ''.join(
        f'<tr><th scope="row">{row["id"]}</th><td>{escape(row["group"])}</td><td>{row["area"]}</td><td>{row["floor"]}</td><td>{row["price"]}</td></tr>'
        for row in rows
    )
    controls_freq = (
        '<div class="grp-controls" hidden><div class="grp-shortcuts">'
        '<button type="button" data-freq="count" aria-pressed="true">건수</button>'
        '<button type="button" data-freq="share">비율</button></div>'
        '<p role="status" id="grp-freq-status"></p></div>'
    )
    controls_hist = (
        '<div class="grp-controls" hidden><div class="grp-shortcuts">'
        '<button type="button" data-width="30">폭 30</button>'
        '<button type="button" data-width="60" aria-pressed="true">폭 60</button>'
        '<button type="button" data-width="120">폭 120</button></div>'
        '<p role="status" id="grp-histogram-status"></p></div>'
    )
    controls_shape = (
        '<div class="grp-controls" hidden><div class="grp-shortcuts">'
        '<button type="button" data-shape-button="symmetric" aria-pressed="true">대칭</button>'
        '<button type="button" data-shape-button="right">오른쪽 꼬리</button>'
        '<button type="button" data-shape-button="peaks">두 봉우리</button></div>'
        '<p role="status" id="grp-shape-status"></p></div>'
    )
    controls_scatter = (
        '<div class="grp-controls" hidden><div class="grp-shortcuts">'
        '<button type="button" data-group="all" aria-pressed="true">전체 30건</button>'
        '<button type="button" data-group="주거">주거 원</button>'
        '<button type="button" data-group="상업">상업 사각형</button></div>'
        '<p><label for="grp-id">관측번호 <input id="grp-id" type="number" min="1" max="30" value="7"></label></p>'
        '<p role="status" id="grp-scatter-status"></p></div>'
    )
    controls_box = (
        '<div class="grp-controls" hidden><div class="grp-shortcuts">'
        '<button type="button" data-box="q1">Q1</button>'
        '<button type="button" data-box="median">중앙값</button>'
        '<button type="button" data-box="q3">Q3</button>'
        '<button type="button" data-box="iqr">IQR</button>'
        '<button type="button" data-box="low">아래 수염</button>'
        '<button type="button" data-box="high">위 수염</button>'
        '<button type="button" data-box="extreme" aria-pressed="true">480</button></div>'
        '<p role="status" id="grp-box-status"></p></div>'
    )
    parts = [
        sec('quick-start', '서두 · 학습목표', '같은 거래자료를 그래프로 나타내면 무엇이 달라질까요?',
            '<p>부동산 거래 30건에서 주거와 상업이 몇 건인지를 보려면 막대그래프가 맞습니다. 단가가 어느 가격대에 모였는지는 히스토그램이, 면적과 단가가 함께 어떻게 놓였는지는 산점도가 보여 줍니다. 같은 자료라도 그래프마다 보이는 정보가 다릅니다.</p>'
            '<p><strong>같은 종류의 그래프라도 축의 범위나 구간 폭을 바꾸면 인상이 달라질 수 있습니다.</strong> 무엇을 그린 그림인지와 어떤 기준으로 그렸는지를 함께 확인합니다.</p>'
            '<ul class="learn-objectives"><li>분석 질문에 적합한 그래프를 선택합니다.</li><li>막대그래프와 히스토그램의 차이를 이해합니다.</li><li>히스토그램의 구간 폭이 분포의 모양에 미치는 영향을 알아봅니다.</li><li>분포의 중심·퍼짐·꼬리·봉우리를 구별합니다.</li><li>산점도에서 두 변수의 관계를 살펴봅니다.</li><li>상자그림의 중앙값·사분위수·수염·이상치를 이해합니다.</li><li>그래프의 축과 표본 조건이 해석에 미치는 영향을 알아봅니다.</li><li>CH2 Macro의 통계표를 읽을 때 분포를 함께 고려하는 방법을 이해합니다.</li></ul>'),
        sec('choose', '그래프 선택', '알고 싶은 질문에 따라 그림이 달라집니다',
            '<div class="learn-data learn-data--full grp-table"><table><caption>질문과 그에 맞는 그래프</caption><thead><tr><th scope="col">알고 싶은 것</th><th scope="col">그래프</th></tr></thead><tbody>'
            '<tr><td>주거와 상업이 각각 몇 건인가</td><td>막대그래프</td></tr>'
            '<tr><td>단가가 어느 가격대에 몰려 있는가</td><td>히스토그램</td></tr>'
            '<tr><td>집단별 중앙값과 퍼짐은 어떠한가</td><td>상자그림</td></tr>'
            '<tr><td>면적과 단가는 어떤 관계인가</td><td>산점도</td></tr>'
            '<tr><td>월별 거래 건수는 어떻게 변했는가</td><td>시계열 선그래프</td></tr>'
            '</tbody></table></div>'
            '<p>모든 질문에 여러 그래프를 쓸 필요는 없습니다. <strong>먼저 질문을 정하고 그 질문에 맞는 그림을 고릅니다.</strong></p>'),
        sec('data', '이번 장의 자료', '그림 1·2·4·5는 같은 30건을 사용합니다',
            '<p>1장의 공통 학습자료 30건을 다시 사용합니다. 각 행에는 구분, 면적(㎡), 층, 단가(만원/㎡)가 있습니다. 주거 15건, 상업 15건, 면적 22~310㎡, 단가 62~480만원/㎡입니다.</p>'
            '<p>이 자료는 학습 예제입니다. 실제 거래 원천과 표집 설계가 확인된 자료가 아니므로 특정 지역의 시장 수준으로 읽지 않습니다. 번호 1~30은 식별자이며 거래 시각이 아닙니다. 그림 3은 분포 모양을 위한 별도 개념도입니다.</p>'
            f'<div class="learn-data learn-data--full grp-table"><table><caption>공통 학습자료 30건</caption><thead><tr><th scope="col">번호</th><th scope="col">구분</th><th scope="col">면적</th><th scope="col">층</th><th scope="col">단가</th></tr></thead><tbody>{table_rows}</tbody></table></div>'
            '<p><a href="../example-data.json">원본 JSON</a>의 키는 바꾸지 않습니다.</p>'),
        sec('bar-chart', '막대그래프', '범주마다 막대 하나로 건수를 비교합니다',
            '<p>주거 15건, 상업 15건, 각각 50%입니다. 합은 30건, 100%입니다.</p>'
            + controls_freq + fig1() +
            '<p>이 그림이 말하는 것은 <strong>이번 자료에서 두 범주의 건수가 같다</strong>는 사실입니다. 단가가 같다거나, 면적 분포가 같다거나, 실제 시장에서 두 유형의 거래량이 같다는 결론은 나오지 않습니다.</p>'
            '<div class="learn-data learn-data--full grp-table"><table><caption>건수와 비율이 다른 방향을 가리킬 수 있습니다</caption><thead><tr><th scope="col">구분</th><th scope="col">전체</th><th scope="col">상업</th><th scope="col">상업 비율</th></tr></thead><tbody>'
            '<tr><th scope="row">A 지역</th><td>100건</td><td>20건</td><td>20%</td></tr>'
            '<tr><th scope="row">B 지역</th><td>20건</td><td>10건</td><td>50%</td></tr>'
            '</tbody></table></div>'
            '<p>상업 거래의 건수는 A가 더 많고, 상업이 차지하는 비율은 B가 더 큽니다. 이 지역 비교는 공통 30건과 다른 가상 예제입니다.</p>'
            '<p>순서가 없는 범주는 목적에 따라 자리를 바꿀 수 있습니다. 낮음·보통·높음처럼 순서가 있는 범주는 그 순서를 유지하는 편이 읽기 좋습니다. 막대 길이로 수량을 비교할 때는 축을 0부터 시작합니다. 100과 110을 90부터 그리면 길이가 10과 20이 되어 두 배처럼 보일 수 있습니다. 실제 차이는 10%입니다.</p>'),
        sec('histograms', '히스토그램', '수치형 값을 구간으로 나누어 분포를 봅니다',
            '<p>히스토그램의 가로축은 단가의 크기와 간격입니다. 구간은 수치 순서대로 두고, 관측이 없는 구간도 자리를 남깁니다. 막대그래프의 주거·상업처럼 범주를 뒤섞는 축이 아닙니다.</p>'
            '<p>이번 예제의 경계는 <strong>왼쪽 포함, 오른쪽 제외</strong>입니다. 60 이상 120 미만에는 120이 들어가지 않고, 120은 다음 구간으로 갑니다. 480은 420 이상 480 미만에 들어가지 않고 480 이상 540 미만에 들어갑니다. 같은 폭이라도 시작점이 60인지 50인지에 따라 각 구간의 건수가 달라질 수 있습니다.</p>'
            + controls_hist + fig2() +
            '<p>폭 60에서 60 이상 120 미만은 14건, 120 이상 180 미만은 10건입니다. 폭 120으로 60 이상 180 미만을 묶으면 24건입니다. 막대가 높아진 것은 두 구간을 합쳐서이며, 거래가 10건 늘어난 것이 아닙니다. 전체는 30건입니다.</p>'
            '<p>폭을 좁히면 세부 굴곡이 보이고, 표본이 적으면 그 굴곡이 우연일 수 있습니다. 폭을 넓히면 큰 흐름이 보이지만 빈 구간이나 작은 봉우리가 가려질 수 있습니다. 한 모양만으로 분포를 확정하지 않습니다.</p>'
            '<details class="learn-more"><summary>구간 폭이 다르면 높이만으로 비교하기 어렵습니다</summary><div class="learn-more__body"><p>한 그림 안에서 구간 폭이 모두 같으면 세로축을 건수로 두어도 됩니다. 이번 기본 그림이 그 경우입니다. 폭이 20인 구간과 100인 구간에 각각 10건이 있을 때 높이만 같게 그리면, 넓은 구간이 더 넓은 범위를 묶었다는 사실이 잘 보이지 않습니다.</p><p>그때는 높이를 구간 건수 ÷ (전체 건수 × 구간 폭)으로 두는 밀도 히스토그램을 쓸 수 있고, 막대 면적이 그 구간의 비율이 됩니다. 이번 장에서는 밀도 히스토그램을 추가로 그리지 않습니다.</p></div></details>'),
        sec('shape', '분포의 모양', '평균만으로는 보이지 않는 특징이 있습니다',
            '<p>분포를 읽을 때는 값들이 모인 <strong>중심</strong>, 흩어진 <strong>퍼짐</strong>, 드문 값이 이어지는 <strong>꼬리</strong>, 많이 모인 구간인 <strong>봉우리</strong>를 살펴봅니다.</p>'
            + controls_shape + fig3() +
            '<p>대칭에 가까우면 평균과 중앙값이 비슷할 수 있습니다. 두 값이 비슷하다고 분포가 대칭이라고 확정하지는 않습니다. 오른쪽 꼬리가 길면 큰 값이 평균을 끌어올릴 수 있습니다. 봉우리가 여러 개 보여도 구간 폭과 표본 변동 때문에 생긴 모습일 수 있으므로, 서로 다른 시장이 있다고 단정하지 않습니다.</p>'
            '<p>이 자료에서 가장 큰 단가는 480만원/㎡이고 7번 관측입니다. 상업, 면적 22㎡, 1층입니다. 멀리 떨어져 보인다고 바로 삭제하지 않습니다. 유효한 거래인지, 입력 오류가 있는지, 다른 조건의 거래인지, 평균이나 이후 회귀계수에 얼마나 영향을 주는지를 먼저 확인합니다. 면적이 작아서 단가가 높다고 단정하지도 않습니다.</p>'),
        sec('scatter', '산점도', '두 수치형 변수가 함께 놓인 모습을 봅니다',
            '<p>가로축은 면적(㎡), 세로축은 단가(만원/㎡)입니다. 7번의 좌표는 (22, 480)입니다.</p>'
            + controls_scatter + fig4() +
            '<p>면적이 큰 관측이 낮은 단가 쪽에 많아 보여도, 면적이 커지면 단가가 반드시 하락한다고 결론 내리지 않습니다. 방향, 직선인지 곡선인지, 점의 퍼짐, 멀리 떨어진 점, 주거와 상업의 차이를 살펴봅니다. 용도지역, 입지, 거래 시점이 함께 달라졌을 수 있습니다. <strong>산점도는 관계를 보는 출발점이며 인과효과를 입증하지 않습니다.</strong></p>'
            '<details class="learn-more"><summary>점이 겹치거나 번호로 선을 잇는 경우</summary><div class="learn-more__body"><p>같은 좌표의 관측은 한 점처럼 겹칠 수 있습니다. 화면에 점이 30개보다 적어 보여도 관측이 빠진 것은 아닐 수 있습니다. 주거와 상업은 색과 모양으로 구분합니다. 번호 1~30을 선으로 잇는 것은 시간 추세가 아닙니다. 번호가 거래일이 아니기 때문입니다.</p></div></details>'),
        sec('boxplot', '상자그림', '중심과 퍼짐, 멀리 떨어진 값을 요약합니다',
            '<p>30개 단가를 정렬해 아래 15개와 위 15개로 나누고, 각 절반의 중앙값을 사분위수로 씁니다. Q1은 98, 중앙값은 122, Q3는 168, IQR은 168−98=70입니다.</p>'
            '<p>1.5×IQR은 105입니다. 아래 경계는 98−105=−7, 위 경계는 168+105=273입니다. 수염은 그 경계 안의 실제 관측인 62와 268까지 뻗습니다. 480은 273을 넘으므로 별도 점입니다. <strong>수염이 268에서 끝난다고 최댓값이 268인 것은 아닙니다.</strong> 경계 밖의 점이 입력 오류라는 뜻도 아닙니다.</p>'
            + controls_box + fig5() +
            '<p>상자그림은 여러 집단의 중앙값과 퍼짐을 나란히 보기 좋습니다. 봉우리의 수, 빈 구간, 서로 다른 가격 집단이 섞였는지는 잘 드러나지 않습니다. 히스토그램과 원래 점과 함께 봅니다. 사분위수 계산을 바꾸면 값이 달라질 수 있습니다. 이 과정의 공통 예제는 여기서 쓴 절반 중앙값 규칙을 유지합니다. <a href="/learn/stats/iqr-outliers/">7장</a>에서 같은 30건의 1.5×IQR과 다른 계산법을 비교합니다.</p>'),
        sec('reading', '그래프를 읽을 때', '숫자가 맞아도 인상이 달라질 수 있습니다',
            '<ul><li><strong>축의 시작:</strong> 막대 길이로 100과 110을 비교할 때 축을 90부터 두면 차이가 커 보입니다.</li>'
            '<li><strong>축의 범위:</strong> 두 그림을 비교하면 시작, 끝, 단위가 같은지 확인합니다. 산점도와 시계열은 필요한 구간을 확대해 볼 수 있습니다. 모든 축이 0에서 시작해야 하는 것은 아닙니다.</li>'
            '<li><strong>구간 폭:</strong> 넓은 구간에 더 많은 관측이 들어가므로, 막대가 높아졌다고 거래가 늘었다고 보지 않습니다.</li>'
            '<li><strong>건수와 비율:</strong> 거래가 많은 지역의 특정 유형 비율이 더 낮을 수 있습니다.</li>'
            '<li><strong>극단값:</strong> 멀리 떨어진 거래도 유효한 거래일 수 있습니다.</li>'
            '<li><strong>번호와 시간:</strong> 번호가 커진다고 거래 시점이 뒤로 간 것은 아닙니다.</li>'
            '<li><strong>표본 조건:</strong> 기간, 유형, 이상치 처리가 다르면 그림의 차이는 자료 구성의 차이일 수 있습니다.</li></ul>'),
        sec('practice', '확인 문제', '그래프에 보이는 숫자와 그 의미를 구별해 보세요',
            '<ol class="learn-exercises">'
            '<li>구간 폭을 60에서 120으로 바꾸자 첫 막대가 14건에서 24건이 되었습니다. 거래 10건이 추가된 것일까요?<details><summary>답과 해설</summary><p>아닙니다. 60 이상 120 미만 14건과 120 이상 180 미만 10건을 합친 것입니다. 전체는 30건입니다.</p></details></li>'
            '<li>산점도의 번호를 차례로 선으로 연결하면 가격의 시간 추세를 볼 수 있을까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 이 자료의 번호는 식별자입니다. 시간 추세에는 실제 날짜와 같은 집계 기준이 필요합니다.</p></details></li>'
            '<li>위쪽 수염이 268에서 끝났습니다. 최댓값도 268일까요?<details><summary>답과 해설</summary><p>아닙니다. 수염은 1.5×IQR 경계 안의 가장 큰 값 268까지입니다. 최댓값 480은 별도 점입니다.</p></details></li>'
            '<li>주거와 상업이 각각 15건이면 평균 단가도 같을까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 건수는 빈도입니다. 단가의 평균과 분포는 따로 계산합니다.</p></details></li>'
            '<li>그래프에서 평균이 크게 올랐습니다. 그 지역의 모든 부동산 가격이 올랐다고 볼 수 있을까요?<details><summary>답과 해설</summary><p>추가 확인이 필요합니다. 거래 구성, 기간, 면적, 유형이 달라졌을 수 있습니다. 평균의 변화와 같은 부동산의 가격 변화를 구별합니다.</p></details></li>'
            '</ol>'),
        sec('macro', 'CH2 Macro에서 읽기', '평균과 분위수만 보지 않고 분포도 함께 생각합니다',
            '<p>기본통계는 지역·용도지역·지목별로 건수, 평균, 중앙값, 분위수를 보여 줍니다. 각각은 분포의 일부입니다. 아래 두 화면은 과거 캡처이며 공통 30건이 아닙니다.</p>'
            '<figure class="learn-capture"><a href="../assets/captures/macro-12month-bucket-trend.png" target="_blank" rel="noopener"><img src="../assets/captures/macro-12month-bucket-trend.png" width="869" height="401" loading="lazy" alt="CH2 Macro 12개월 롤링 버킷 추이. 파란 선은 평균 단가, 회색 점선은 거래 건수입니다."/></a>'
            '<figcaption class="learn-capture__caption">12개월 구간별 평균 단가와 거래 건수입니다. 첫 구간은 2021년 10월~2022년 9월, 마지막은 2025년 10월~2026년 9월입니다. 수치는 캡처 당시 값입니다.</figcaption></figure>'
            '<ol class="learn-screen-reading"><li><strong>파란 선</strong>은 평균 단가(만원/㎡)입니다. 캡처에는 첫 구간 201.7, 세 번째 구간 188.3, 마지막 구간 213.4가 있습니다. 선이 올랐다고 같은 부동산의 가격이 그만큼 오른 것은 아닙니다.</li>'
            '<li><strong>회색 점선</strong>은 거래 건수입니다. 첫 구간 52건, 마지막 구간 18건입니다. 단가와 건수는 단위가 다르므로 두 선의 높이만으로 비교하지 않습니다.</li></ol>'
            '<figure class="learn-capture"><a href="../assets/captures/macro-analysis-price-distribution.png" target="_blank" rel="noopener"><img src="../assets/captures/macro-analysis-price-distribution.png" width="868" height="395" loading="lazy" alt="CH2 Macro 분석 구간 전체의 단가 분포. 분석 기간은 2021-10-01부터 2026-09-30까지이며 세로축은 빈도입니다."/></a>'
            '<figcaption class="learn-capture__caption">분석 구간 2021-10-01~2026-09-30의 단가 분포입니다. 가장 높은 막대의 36은 그 구간의 거래 건수이며 평균 단가가 아닙니다.</figcaption></figure>'
            '<p>거래가 5건인 집단과 500건인 집단의 분위수를 같은 안정성으로 읽지 않습니다. 같은 지역의 지목별 평균이 달라도 그것이 지목의 인과효과는 아닙니다. 3년과 5년 롤링은 기간이 겹치므로 독립된 두 집단도 아닙니다.</p>'
            '<p>토지 기본통계 매트릭스의 25%·75%는 단가 목록의 백분위입니다. 이 장의 절반 중앙값 Q1 98·Q3 168과 같은 규칙은 아닙니다. 7장에서 같은 30건을 그 백분위로 구하면 Q1 99, Q3 166이 됩니다. 유료 매트릭스 칸의 단가 분포는 관측된 범위에 구간 개수를 나눠 그립니다. 이 장의 시작점 60, 폭 30·60·120, 왼쪽 포함·오른쪽 제외와 같지 않습니다. 기본통계 표에 산점도와 상자그림이 함께 들어 있지는 않습니다. 이번 장의 다섯 그림은 학습용입니다.</p>'
            '<p>표를 볼 때도 이 평균이 어떤 거래로 모였는지, 중앙값과 분위수의 간격은 얼마인지, 고가 거래의 영향은 있는지, 건수와 유형이 어떻게 섞였는지를 물어 봅니다.</p>'
            '<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p>'),
        sec('recap', '결론 · 학습 요약', '그래프는 특징을 보여 주지만 모든 것을 설명하지는 않습니다',
            '<ul class="learn-recap-list">'
            '<li><strong>막대그래프:</strong> 범주별 건수와 비율을 비교합니다.</li>'
            '<li><strong>히스토그램:</strong> 수치형 값의 분포를 구간별로 보여 줍니다.</li>'
            '<li><strong>구간 폭:</strong> 같은 자료의 막대 높이를 바꿀 수 있습니다.</li>'
            '<li><strong>중심·퍼짐·꼬리·봉우리:</strong> 분포를 읽을 때의 네 가지 질문입니다.</li>'
            '<li><strong>산점도:</strong> 두 수치형 변수의 관계를 탐색합니다.</li>'
            '<li><strong>상자그림:</strong> 중앙값, 사분위수, 수염, 경계 밖 점을 요약합니다.</li>'
            '<li><strong>축과 표본 조건:</strong> 그림의 인상과 비교 가능성을 좌우합니다.</li>'
            '</ul>'
            '<p>다음 <a href="/learn/stats/mean-and-median/">4장 「평균과 중앙값」</a>에서는 분포의 중심을 두 숫자로 비교합니다. 극단적인 거래가 있으면 두 값이 달라질 수 있습니다.</p>'
            '<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul>'
            '<li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/histogra.htm">NIST/SEMATECH e-Handbook: Histogram</a></li>'
            '<li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/scatterp.htm">NIST/SEMATECH e-Handbook: Scatter Plot</a></li>'
            '</ul><p class="learn-source-note">참고자료 확인일: 2026-10-07. 그림 1·2·4·5는 공통 학습자료이고 그림 3은 개념도입니다. 학습용 자료를 실제 시장 통계로 읽지 않습니다.</p></div></details>'),
    ]
    html = f'''<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>03. 그래프로 보는 데이터와 분포 | 통계학 &amp; 데이터 분석</title>
    <meta name="description" content="막대그래프, 히스토그램, 산점도, 상자그림으로 같은 자료의 분포와 관계를 읽고 축과 구간 설정을 확인합니다." />
    <link rel="canonical" href="https://ch2data.com/learn/stats/graphs/" />
    <script src="/learn/stats/learn-stats-theme.js?v=20261023-1"></script>
    <link rel="stylesheet" href="/style.css" />
    <link rel="stylesheet" href="/learn/stats/learn-stats.css?v=20261023-1" />
    <link rel="stylesheet" href="/learn/stats/learn-reader.css?v=20261026-toc" />
    <link rel="stylesheet" href="/learn/stats/graphs/chapter.css?v=20261026-8" />
  </head>
  <body>
    <div class="page">
      <header class="hero hero--document">
        <p class="learn-breadcrumb"><a href="https://ch2data.com/">CH2 DATA</a> · <a href="/learn/stats/">통계학 &amp; 데이터 분석</a></p>
        <p class="hero__eyebrow">I. 데이터와 기술통계</p>
        <h1 class="hero__title">03. 그래프로 보는 데이터와 분포</h1>
        <p class="learn-chapter-relevance">Macro 활용도 <span class="learn-relevance" aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span></span></p>
        <p class="learn-relevance-guide">Macro 활용도: ★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화<br>별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.</p>
      </header>
      <article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="그래프로 보는 데이터와 분포">{''.join(parts)}</article>
      <nav class="learn-chapter-nav" aria-label="장 이동">
        <a href="/learn/stats/population-and-sampling/">← 02. 모집단과 표본, 자료 수집과 편향</a>
        <a href="/learn/stats/mean-and-median/">04. 평균과 중앙값 →</a>
      </nav>
      <footer class="footer"><nav class="footer__links"><a href="https://ch2data.com/">홈</a><a href="/learn/stats/">통계학 &amp; 데이터 분석</a></nav><p>© CH2 DATA</p></footer>
    </div>
    <script src="/learn/stats/learn-stats-toc.js?v=20261026-8" defer></script>
    <script type="application/json" id="grp-data">{json.dumps(page_data, ensure_ascii=False)}</script>
    <script type="module" src="/learn/stats/graphs/experiment.js?v=20261026-8"></script>
  </body>
</html>
'''
    ids = re.findall(r'id="([^"]+)"', html)
    if len(ids) != len(set(ids)):
        raise SystemExit(f'duplicate ids: {[item for item in ids if ids.count(item) > 1]}')
    charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', html, re.S)]
    assert len(charts) == 5
    histogram = next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('histogram-widths'))
    for width in (60, 120):
        bars = [node for node in histogram.findall('rect') if node.attrib.get('data-bin-width') == str(width)]
        counts = [sum(low <= row['price'] < low + width for row in rows) for low in range(60, 540, width)]
        assert len(bars) == len(counts) and sum(counts) == 30
        for index, (bar, count) in enumerate(zip(bars, counts)):
            assert int(bar.attrib['data-count']) == count
            assert abs(float(bar.attrib['height']) - count * 5) < 1e-8
            assert abs(float(bar.attrib['x']) - (70 + index * width * 1.1)) < 1e-8
    scatter = next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('grouped-scatter'))
    points = [node for node in scatter if 'data-observation' in node.attrib]
    assert len(points) == 30
    for point in points:
        row = next(item for item in rows if item['id'] == int(point.attrib['data-observation']))
        x = float(point.attrib.get('cx', point.attrib.get('x'))) + (4.5 if point.tag == 'rect' else 0)
        y = float(point.attrib.get('cy', point.attrib.get('y'))) + (4.5 if point.tag == 'rect' else 0)
        assert abs(x - (70 + row['area'] * 1.6)) < 1e-8
        assert abs(y - (285 - row['price'] * 0.42)) < 1e-8
    box = next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('box-summary'))
    assert box.find('rect').attrib['width'] == '70'
    assert box.find('circle').attrib['cx'] == '540'
    assert html.count('<summary>답과 해설</summary>') == 5
    assert 'id="data"' in html and 'id="shape"' in html
    assert ' open' not in html.split('<ol class="learn-exercises">')[1].split('</ol>')[0]
    assert '[그림 ' not in html and '★☆☆ 심화' in html and '3단계, 핵심' in html
    assert 'macro-12month-bucket-trend.png' in html and 'macro-analysis-price-distribution.png' in html
    (ROOT / 'graphs' / 'index.html').write_text(html, encoding='utf-8')
    promote(ROOT / 'course.json')
    promote(ROOT / 'learn-stats-toc.js')
    listing = ROOT / 'index.html'
    listing_text = listing.read_text(encoding='utf-8')
    old_link = 'data-macro-relevance="2"><a href="/learn/stats/graphs/">03. 그래프로 보는 데이터와 분포 <span class="learn-relevance" aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>'
    new_link = old_link.replace('data-macro-relevance="2"', 'data-macro-relevance="3"').replace('2단계, 권장', '3단계, 핵심').replace('★★☆', '★★★')
    if old_link not in listing_text and new_link not in listing_text:
        raise SystemExit('course listing relevance missing')
    if old_link in listing_text:
        listing.write_text(listing_text.replace(old_link, new_link, 1), encoding='utf-8')
    try:
        import numpy as np
        prices = [row['price'] for row in rows]
        print('numpy percentile', float(np.percentile(prices, 25)), float(np.percentile(prices, 75)))
    except Exception as exc:
        print('numpy percentile skipped', exc)
    print('chapter 3 rebuilt', 'bins30', [item['count'] for item in bins['30']])


if __name__ == '__main__':
    build()
