"""Generate chapter 07 with reproducible fences and sensitivity figures."""
from pathlib import Path
from statistics import mean, median, pstdev
from html import escape
import json, re
import xml.etree.ElementTree as ET
from _build_quantiles_chapter import summary, type7
ROOT = Path(__file__).resolve().parent

def build():
    rows = json.loads((ROOT / 'example-data.json').read_text(encoding='utf-8'))['rows']
    values = [r['price'] for r in rows]
    other = [r['price'] for r in rows if r['id'] != 7]
    groups = {name: [r['price'] for r in rows if r['group'] == name] for name in ('주거', '상업')}
    assert len(values) == 30 and sum(values) == 4390 and min(values) == 62 and max(values) == 480
    assert next(r['price'] for r in rows if r['id'] == 7) == 480
    assert next(r['price'] for r in rows if r['id'] == 24) == 268
    assert next(r['group'] for r in rows if r['id'] == 7) == '상업'
    q1, q2, q3, whisker_lo, whisker_hi, outliers = summary(values)
    assert (q1, q2, q3, whisker_lo, whisker_hi, outliers) == (98, 122, 168, 62, 268, [480])
    assert [v for v in values if v < -7 or v > 273] == [480]
    assert not (273 < -7 or 273 > 273)
    for k, lo, hi in ((1.5, -7, 273), (2, -42, 308), (3, -112, 378)):
        assert 98 - k * 70 == lo and 168 + k * 70 == hi
        assert [v for v in values if v < lo or v > hi] == [480]
    assert [type7(values, p) for p in (.25, .5, .75)] == [99, 122, 166]
    assert sorted(v for v in values if v < -1.5 or v > 266.5) == [268, 480]
    assert summary(groups['주거'])[:3] == (88, 105, 120)
    assert summary(groups['상업'])[:3] == (124, 168, 235)
    assert [v for v in groups['주거'] if v < 40 or v > 168] == []
    assert [v for v in groups['상업'] if v < -42.5 or v > 401.5] == [480]
    assert summary([100] * 6 + [120])[:3] == (100, 100, 100)
    assert [v for v in [100] * 6 + [120] if v < 100 or v > 100] == [120]
    assert sum(other) == 3910 and round(mean(other), 2) == 134.83 and median(other) == 120
    assert round(pstdev(other), 2) == 51.72 and round(pstdev(values), 2) == 80.16
    assert round(mean(values) - mean(other), 2) == 11.51
    assert round(pstdev(values) - pstdev(other), 2) == 28.43
    winsor = [273 if r['id'] == 7 else r['price'] for r in rows]
    assert sum(winsor) == 4183 and round(mean(winsor), 2) == 139.43
    assert len(groups['주거']) == 15 and len(groups['상업']) == 15

    def t(x, y, text, extra=''):
        return f'<text x="{x}" y="{y}" {extra}>{escape(str(text))}</text>'
    def line(x1, y1, x2, y2, extra=''):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#64748b" {extra}/>'
    def fig(svg_id, title, desc, body, caption, height):
        return (
            f'<figure class="learn-chart learn-chart--wide iq-chart"><svg id="{svg_id}" viewBox="0 0 640 {height}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc">'
            f'<title id="{svg_id}-title">{title}</title><desc id="{svg_id}-desc">{desc}</desc>{body}</svg>'
            f'<figcaption id="{svg_id}-caption" class="learn-chart__caption">{caption}</figcaption></figure>'
        )

    x = lambda v: 110 + v * 0.95
    body = t(24, 28, '점선은 울타리, 수염 끝은 울타리 안의 실제 관측입니다')
    body += f'<line id="iq-whisker-span" data-part="whisker" x1="{x(62)}" y1="90" x2="{x(268)}" y2="90" stroke="#64748b" stroke-width="1.5"/>'
    body += f'<rect id="iq-box" data-part="iqr" x="{x(98)}" y="70" width="{x(168) - x(98)}" height="40" fill="#bfdbfe" stroke="#64748b"/>'
    body += f'<line id="iq-q1" data-part="q1" x1="{x(98)}" y1="70" x2="{x(98)}" y2="110" stroke="#64748b" stroke-width="1.5"/>'
    body += f'<line id="iq-median" data-part="median" x1="{x(122)}" y1="70" x2="{x(122)}" y2="110" stroke="#64748b" stroke-width="1.5"/>'
    body += f'<line id="iq-q3" data-part="q3" x1="{x(168)}" y1="70" x2="{x(168)}" y2="110" stroke="#64748b" stroke-width="1.5"/>'
    body += f'<line id="iq-fence-lo" data-part="fence" x1="{x(-7)}" y1="58" x2="{x(-7)}" y2="122" stroke="#64748b" stroke-width="1.5" stroke-dasharray="4 3"/>'
    body += f'<line id="iq-fence-hi" data-part="fence" x1="{x(273)}" y1="58" x2="{x(273)}" y2="122" stroke="#64748b" stroke-width="1.5" stroke-dasharray="4 3"/>'
    body += f'<line id="iq-whisker-lo" data-part="whisker" x1="{x(62)}" y1="80" x2="{x(62)}" y2="100" stroke="#64748b" stroke-width="1.5"/>'
    body += f'<line id="iq-whisker-hi" data-part="whisker" x1="{x(268)}" y1="80" x2="{x(268)}" y2="100" stroke="#64748b" stroke-width="1.5"/>'
    body += f'<text id="iq-label-lo" x="{x(-7)}" y="48" text-anchor="middle">하한 −7</text>'
    body += f'<text id="iq-label-hi" x="{x(273)}" y="48" text-anchor="middle">상한 273</text>'
    body += f'<text id="iq-label-wlo" x="{x(62)}" y="150" text-anchor="middle">수염 62</text>'
    body += f'<text id="iq-label-whi" x="{x(268)}" y="150" text-anchor="middle">수염 268</text>'
    body += f'<circle id="iq-p268" data-part="p268" cx="{x(268)}" cy="90" r="5" fill="#2563eb" stroke="#1e3a8a"/>'
    body += f'<circle id="iq-p480" data-part="p480" cx="{x(480)}" cy="90" r="6" fill="#d97706" stroke="#1e3a8a"/>'
    body += t(x(480), 78, '7번 480', 'text-anchor="middle"')
    body += line(x(0), 190, x(500), 190)
    for value in (0, 100, 200, 300, 400, 500):
        body += t(x(value), 212, value, 'text-anchor="middle"')
    body += t(400, 240, '단가(만원/㎡) · 공통 30건')
    figure1 = fig('fences', 'IQR 울타리와 수염', '그림 1. 1.5배 울타리는 −7과 273이고, 수염은 62와 268입니다. 480만 후보입니다.', body, '그림 1. 공통 30건, 두 절반 방식, k=1.5. 울타리 −7·273, 수염 62·268, 후보 7번 480. −7은 관측된 음수 단가가 아닙니다.', 268)

    body = t(24, 28, '같은 Q1·Q3에서 배수만 바꿉니다')
    halves = ''
    typed = ''
    for i, k in enumerate((1.5, 2, 3)):
        y = 85 + i * 75
        lo, hi = 98 - k * 70, 168 + k * 70
        halves += t(24, y + 5, f'k={k}', 'data-rule="halves"')
        halves += line(105, y, 600, y, 'data-rule="halves"')
        halves += f'<rect x="{105 + (lo + 120) * .75}" y="{y - 10}" width="{(hi - lo) * .75}" height="20" fill="#dbeafe" stroke="#64748b" data-k="{k}" data-low="{lo}" data-high="{hi}" data-rule="halves"/>'
        halves += t(105 + (lo + 120) * .75, y - 18, f'{lo:g}', 'text-anchor="middle" data-rule="halves"')
        halves += t(105 + (hi + 120) * .75, y - 18, f'{hi:g}', 'text-anchor="middle" data-rule="halves"')
        tq1, tq3 = type7(values, .25), type7(values, .75)
        tlo, thi = tq1 - k * (tq3 - tq1), tq3 + k * (tq3 - tq1)
        typed += f'<rect x="{105 + (tlo + 120) * .75}" y="{y - 10}" width="{(thi - tlo) * .75}" height="20" fill="#dbeafe" stroke="#64748b" data-rule="type7" data-multiple="{k}"/>'
        typed += t(105 + (tlo + 120) * .75, y - 18, f'{tlo:g}', 'text-anchor="middle" data-rule="type7" data-multiple="' + str(k) + '"')
        typed += t(105 + (thi + 120) * .75, y - 18, f'{thi:g}', 'text-anchor="middle" data-rule="type7" data-multiple="' + str(k) + '"')
        body += f'<circle cx="555" cy="{y}" r="5" fill="#d97706"/>' + t(568, y + 4, '480')
    typed += f'<circle cx="{105 + (268 + 120) * .75}" cy="85" r="5" fill="#d97706" data-rule="type7" data-multiple="1.5"/>'
    body += f'<g data-rule="halves">{halves}</g><g data-rule="type7" visibility="hidden">{typed}</g>'
    body += t(24, 300, '색 구간: 하한~상한 / 주황 점: 후보') + t(360, 326, '단가(만원/㎡), 같은 축척')
    figure2 = fig('multipliers', '배수별 IQR 울타리', '그림 2. 두 절반 방식에서 k=1.5·2·3의 후보는 모두 480 한 건입니다.', body, '그림 2. 자료와 Q1·Q3는 고정입니다. 배수가 커지면 울타리는 넓어지고, 이 자료의 두 절반 방식에서는 480만 후보로 남습니다.', 348)

    body = t(24, 28, '집단마다 사분위수를 다시 계산합니다')
    for i, label in enumerate(('전체', '주거', '상업')):
        group = values if label == '전체' else groups[label]
        gq1, gq2, gq3 = summary(group)[:3]
        upper = gq3 + 1.5 * (gq3 - gq1)
        y = 90 + i * 100
        body += f'<text id="iq-scope-{label}" x="24" y="{y - 28}">{label} {len(group)}건 · Q1 {gq1:g}, Q3 {gq3:g}, 상한 {upper:g}</text>'
        body += line(90, y, 590, y)
        body += f'<rect x="{90 + gq1}" y="{y - 10}" width="{gq3 - gq1}" height="20" fill="#bfdbfe" stroke="#64748b" data-group="{label}" data-upper="{upper}"/>'
        body += line(90 + gq2, y - 10, 90 + gq2, y + 10)
        body += f'<line id="iq-fence-{label}" x1="{90 + upper}" y1="{y - 17}" x2="{90 + upper}" y2="{y + 17}" stroke="#64748b" stroke-dasharray="4 3"/>'
        outside = [v for v in group if v < gq1 - 1.5 * (gq3 - gq1) or v > upper]
        for value in group:
            body += f'<circle cx="{90 + value}" cy="{y + 28}" r="3.5" fill="{"#d97706" if value in outside else "#2563eb"}" stroke="#1e3a8a" data-scope="{label}" data-price="{value}"/>'
    for value in (0, 100, 200, 300, 400, 500):
        body += t(90 + value, 372, value, 'text-anchor="middle"')
    body += t(400, 398, '단가(만원/㎡) · 점이 겹치면 여러 건일 수 있습니다')
    figure3 = fig('group-fences', '집단별 상한 비교', '그림 3. 주거 상한 168에는 후보가 없고, 전체 273과 상업 401.5에서는 480이 후보입니다.', body, '그림 3. 두 절반 방식, k=1.5. 주거 15건의 상한은 168, 상업 15건의 상한은 401.5입니다. 전체 울타리를 하위 집단에 그대로 쓰지 않습니다.', 420)

    body = t(24, 28, '포함·제외는 민감도입니다. 정확해졌다는 뜻은 아닙니다')
    for i, (label, fn) in enumerate((('평균', mean), ('중앙값', median), ('표준편차', pstdev))):
        y = 78 + i * 90
        body += t(24, y + 8, label)
        for offset, series, color, key in ((0, values, '#2563eb', 'all'), (31, other, '#d97706', 'without')):
            value = fn(series)
            body += f'<rect x="150" y="{y + offset - 10}" width="{value * 2.5}" height="18" fill="{color}" stroke="#64748b" data-metric="{label}" data-series="{key}" data-value="{value}"/>'
            body += t(158 + value * 2.5, y + offset + 4, f'{value:.2f}')
    body += t(24, 348, '파랑: 30건 / 주황: 7번을 뺀 29건') + t(24, 372, '표준편차는 각 자료의 건수 n으로 나눕니다 · 만원/㎡')
    figure4 = fig('iq-sensitivity', '제외 전후 통계량', '그림 4. 7번을 빼면 평균과 표준편차를 남은 29건으로 다시 계산합니다.', body, '그림 4. 포함 평균 146.33·표준편차 80.16, 제외 평균 134.83·표준편차 51.72. 줄어든 숫자가 더 정확한 통계라는 뜻은 아닙니다.', 398)

    controls_part = '<div class="iq-controls" hidden><div class="iq-shortcuts"><button type="button" data-part-choice="q1">Q1</button><button type="button" data-part-choice="median">중앙값</button><button type="button" data-part-choice="q3">Q3</button><button type="button" data-part-choice="iqr">IQR</button><button type="button" data-part-choice="fence" aria-pressed="true">울타리</button><button type="button" data-part-choice="whisker">수염</button><button type="button" data-part-choice="p268">24번 268</button><button type="button" data-part-choice="p480">7번 480</button></div><p role="status" id="iq-part-status"></p></div>'
    controls_k = '<div class="iq-controls" hidden><div class="iq-shortcuts"><button type="button" data-method-choice="halves" aria-pressed="true">두 절반</button><button type="button" data-method-choice="type7">Type 7</button><button type="button" data-k-choice="1.5" aria-pressed="true">1.5배</button><button type="button" data-k-choice="2">2배</button><button type="button" data-k-choice="3">3배</button></div><p role="status" id="iq-k-status"></p></div>'
    controls_scope = '<div class="iq-controls" hidden><div class="iq-shortcuts"><button type="button" data-scope-choice="전체" aria-pressed="true">전체</button><button type="button" data-scope-choice="주거">주거</button><button type="button" data-scope-choice="상업">상업</button></div><p role="status" id="iq-group-status"></p></div>'
    controls_drop = '<div class="iq-controls" hidden><div class="iq-shortcuts"><button type="button" data-inclusion="all" aria-pressed="true">7번 포함</button><button type="button" data-inclusion="drop">7번 제외</button></div><p role="status" id="iq-drop-status"></p></div>'
    controls_adjust = '<div class="iq-controls" hidden><div class="iq-shortcuts"><button type="button" data-adjustment="raw" aria-pressed="true">원자료 480</button><button type="button" data-adjustment="drop">절사 예제</button><button type="button" data-adjustment="winsor">273으로 대체</button></div><p role="status" id="iq-adjust-status"></p></div>'

    parts = []
    def sec(sec_id, label, title, content):
        parts.append(f'<section class="learn-chapter__step" id="{sec_id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{content}</section>')

    sec('quick-start', '서두 · 학습목표', '다른 거래보다 비싸다는 이유로 제외해도 될까요?',
        '<p>대부분의 거래가 100만원/㎡ 안팎인데 한 건이 480이라면, 입력이 잘못된 거래일 수도 있고 실제로 드문 고가 거래일 수도 있습니다. 면적이 작거나 입지가 다른 토지가 한 목록에 섞여 멀리 떨어져 보일 수도 있습니다. 단가만 보고는 어느 쪽인지 알 수 없습니다.</p>'
        '<p><strong>이상치</strong>는 다른 관측과 비교적 멀리 떨어진 값입니다. 이상치 후보는 확인할 대상으로 표시한 것이지, 그 자체로 잘못된 값은 아닙니다.</p>'
        '<ul class="learn-objectives"><li>이상치 후보와 입력 오류를 구별합니다.</li><li>IQR 울타리와 배수, 분위수 계산법을 확인합니다.</li><li>전체와 유형별 기준, 한 번의 판정과 반복 제거를 구별합니다.</li><li>포함·제외가 평균과 표준편차를 어떻게 바꾸는지 계산합니다.</li></ul>'
        '<p>앞 장의 <a href="/learn/stats/quantiles/#iqr">IQR</a>과 <a href="/learn/stats/spread/#extremes">큰 값이 표준편차에 미치는 영향</a>을 이어서 봅니다. 계산은 <a href="/learn/stats/graphs/#data">공통 학습자료 30건</a>입니다. 출처가 확인된 시장 자료는 아닙니다.</p>'
        + controls_part + figure1)
    sec('iqr-multiplier', 'IQR 경계 계산', '가운데 부분의 퍼짐으로 울타리를 정합니다',
        '<p><strong>IQR=Q3−Q1</strong>입니다. 배수 k를 정하면 하한은 Q1−k×IQR, 상한은 Q3+k×IQR입니다. 이번 장은 하한보다 작거나 상한보다 큰 값만 후보로 봅니다. 울타리와 같은 값은 후보가 아닙니다.</p>'
        '<p>두 절반 방식의 Q1은 98, Q3는 168, IQR은 70입니다. k=1.5이면 1.5×70=105이므로 하한은 98−105=−7, 상한은 168+105=273입니다. 최솟값 62와 24번 268은 울타리 안이고, 7번 480만 밖입니다. 수염은 −7과 273까지가 아니라 그 안의 실제 값 62와 268까지입니다.</p>'
        '<div class="learn-data learn-data--full iq-table"><table><caption>같은 30건, 두 절반 방식. 단위는 만원/㎡</caption><thead><tr><th scope="col">k</th><th scope="col">하한</th><th scope="col">상한</th><th scope="col">후보</th></tr></thead><tbody><tr><th scope="row">1.5</th><td>−7</td><td>273</td><td>480</td></tr><tr><th scope="row">2</th><td>−42</td><td>308</td><td>480</td></tr><tr><th scope="row">3</th><td>−112</td><td>378</td><td>480</td></tr></tbody></table></div>'
        + controls_k + figure2 +
        '<p>1.5배는 널리 쓰는 탐색 기준입니다. 모든 자료에 그 배수를 써야 하는 것은 아닙니다. 배수는 후보를 얼마나 넓게 표시할지의 선택이고, 95% 신뢰구간이나 오류 확률이 아닙니다. 배수를 키운다고 잘못된 거래를 더 정확히 찾는 것도 아닙니다.</p>'
        '<p>자료와 분위수를 고정하면 배수가 커질수록 후보는 줄거나 그대로입니다. 이번 30건은 273과 378 사이에 값이 없어 세 배수 모두 480 한 건입니다. 후보를 뺀 뒤 분위수를 다시 구하는 절차와는 다릅니다.</p>')
    sec('conventions', '계산법과 예외', '같은 30건도 계산법에 따라 후보가 달라집니다',
        '<p>두 절반 방식의 1.5배 상한은 273이라 268은 안이고 480만 후보입니다. <a href="/learn/stats/quantiles/#methods">Type 7</a>로 같은 30건을 계산하면 Q1=99, Q3=166, IQR=67이고 상한은 166+1.5×67=266.5입니다. 268과 480이 모두 후보가 되어 2건입니다. 어느 한쪽이 계산 오류인 것은 아닙니다. 배수, 분위수 산식, 관측 단위, 비교 집단, 경계 포함 규칙을 같이 확인합니다.</p>'
        '<div class="learn-data learn-data--full iq-table"><table><caption>k=1.5, 같은 30건</caption><thead><tr><th scope="col">항목</th><th scope="col">두 절반</th><th scope="col">Type 7</th></tr></thead><tbody><tr><th scope="row">Q1</th><td>98</td><td>99</td></tr><tr><th scope="row">Q3</th><td>168</td><td>166</td></tr><tr><th scope="row">상한</th><td>273</td><td>266.5</td></tr><tr><th scope="row">후보</th><td>480</td><td>268, 480</td></tr></tbody></table></div>'
        '<p>100이 여섯 번이고 120이 한 번인 가상 단가는 두 절반 방식에서 Q1과 Q3가 모두 100입니다. IQR은 0이고 울타리도 100에 겹쳐 120이 후보가 됩니다. IQR이 0이라고 계산이 잘못된 것은 아니고, 120을 자동으로 지울 이유도 되지 않습니다. 같은 가격이 반복되거나 반올림된 기록에서 이런 일이 생깁니다.</p>'
        '<p>거래가 다섯 건뿐이라면 한두 건이 사분위수 위치를 바꿀 수 있습니다. 5건의 후보와 500건의 후보를 같은 확신으로 읽지 않습니다. 비교할 거래가 충분한지, 한 건이 기준을 바꾸는지, 집단을 더 나누면 건수가 너무 줄어드는지를 봅니다.</p>'
        '<details class="learn-more"><summary>한 번 판정과 반복 제거</summary><div class="learn-more__body"><p>한 번 판정은 처음 구한 울타리로 후보를 표시하고 그 경계를 유지합니다. 반복 제거는 후보를 뺀 뒤 남은 자료에서 사분위수와 울타리를 다시 구합니다. 처음에 안에 있던 값이 다음 울타리 밖으로 나갈 수 있습니다. 이번 장의 기본 계산은 한 번 판정입니다. 언제까지 반복할지와 최종 분석 대상을 미리 정하지 않은 채, 결과가 원하는 모양이 될 때까지 배수를 바꾸지는 않습니다.</p></div></details>')
    sec('groups', '집단과 분포', '누구와 비교하는지에 따라 후보가 달라집니다',
        '<p>공통 30건에는 주거와 상업이 15건씩 있습니다. 전체의 Q1·Q3를 두 유형에 그대로 쓰지 않고, 각 유형의 단가로 다시 계산합니다.</p>'
        + controls_scope + figure3 +
        '<div class="learn-data learn-data--full iq-table"><table><caption>두 절반 방식, k=1.5 · 만원/㎡</caption><thead><tr><th scope="col">항목</th><th scope="col">주거</th><th scope="col">상업</th></tr></thead><tbody><tr><th scope="row">건수</th><td>15</td><td>15</td></tr><tr><th scope="row">Q1</th><td>88</td><td>124</td></tr><tr><th scope="row">Q3</th><td>120</td><td>235</td></tr><tr><th scope="row">IQR</th><td>32</td><td>111</td></tr><tr><th scope="row">상한</th><td>168</td><td>401.5</td></tr><tr><th scope="row">후보</th><td>없음</td><td>7번 480</td></tr></tbody></table></div>'
        '<p>주거 하한은 40, 상업 하한은 −42.5입니다. 주거 15건은 모두 울타리 안입니다. 상업에서는 480이 상한 401.5 밖입니다. 이번 자료에서는 전체와 상업이 모두 480을 후보로 표시했지만, 상한은 273과 401.5로 다릅니다. 항상 같은 결과가 되는 것은 아닙니다.</p>'
        '<p>용도나 지목이 다른 거래를 한 울타리로 묶으면 성격이 다른 가격이 섞입니다. 반대로 조건을 잘게 나누면 건수가 부족해 울타리가 불안정해집니다. 비슷한 조건끼리 비교하는지, 그 집단에 계산할 자료가 있는지를 같이 봅니다. IQR은 그 집단의 퍼짐을 요약한 도구이고, 가격의 상한 제도는 아닙니다.</p>'
        '<details class="learn-more"><summary>단가 하나와 여러 조건을 같이 보는 경우</summary><div class="learn-more__body"><p>이번 장의 IQR은 단가 하나의 분포를 봅니다. 단가 자체는 흔한 수준이어도 면적, 입지, 용도를 같이 보면 특이한 거래일 수 있습니다. 반대로 전체에서는 높아 보여도 비슷한 조건 안에서는 자연스러울 수 있습니다. 회귀분석의 잔차가 크다는 것과 원자료 단가가 높다는 것도 다른 질문입니다.</p></div></details>')
    sec('sensitivity', '포함·제외 비교', '통계량이 변한 것과 오류인지를 구별합니다',
        '<p>7번 480을 빼면 건수는 29, 단가 합계는 3,910입니다. 남은 자료의 평균을 다시 구한 뒤 제곱편차도 다시 계산합니다. 원래 표준편차에서 480의 기여만 빼는 계산이 아닙니다. 표준편차는 6장과 같이 각 자료의 건수 n으로 나눕니다.</p>'
        + controls_drop + figure4 +
        '<div class="learn-data learn-data--full iq-table"><table><caption>7번 포함과 제외 · 만원/㎡</caption><thead><tr><th scope="col">항목</th><th scope="col">포함</th><th scope="col">제외</th></tr></thead><tbody><tr><th scope="row">건수</th><td>30</td><td>29</td></tr><tr><th scope="row">단가 합계</th><td>4,390</td><td>3,910</td></tr><tr><th scope="row">평균</th><td>146.33</td><td>134.83</td></tr><tr><th scope="row">중앙값</th><td>122</td><td>120</td></tr><tr><th scope="row">표준편차, n</th><td>80.16</td><td>51.72</td></tr></tbody></table></div>'
        '<p>평균은 146.33에서 134.83으로 약 11.51 낮아지고, 표준편차는 80.16에서 51.72로 약 28.43 낮아집니다. 표의 두 표준편차는 각각 소수 둘째 자리에서 반올림한 값입니다. 그 거래가 유효했다면 빼기 전의 통계에 있던 거래가 빠진 것입니다. 입력 오류라면 원천을 확인하거나 바른 값으로 고쳐야 할 수 있습니다. 숫자가 작아졌다는 사실만으로 제외가 더 정확하다고 말하지 않습니다.</p>'
        '<h3>절사는 빼고, 윈저화는 값을 바꿉니다</h3><p>절사는 정한 규칙의 관측을 분석 건수에서 제외합니다. 윈저화는 그 값을 경계값으로 바꿉니다. 교육용으로 480을 상한 273에 두면 건수는 30이고 합계는 4,390−480+273=4,183, 평균은 약 139.43입니다. 273은 새로 관측된 단가가 아닙니다. 어느 방법도 오류를 자동으로 고치지 않습니다. 이 대체는 학습 예제이며 서비스 기능이 아닙니다.</p>'
        + controls_adjust)
    sec('model-care', '회귀와 예측', '높은 단가와 모형의 영향은 다른 질문입니다',
        '<p>이상치 처리는 평균만이 아니라 변수 사이 관계도 바꿀 수 있습니다. 확인할 관측을 찾는 일, 예측값과 실제값의 잔차를 보는 일, 그 관측이 회귀계수를 얼마나 움직이는지 보는 일은 서로 다릅니다. 단가가 가장 높은 거래가 잔차도 가장 크거나 계수에 가장 큰 영향을 주는 것은 아닙니다.</p>'
        '<p>예측에서는 학습에 쓰지 않을 자료의 분포로 학습 자료의 제외 기준을 정하지 않습니다. 검증 점수를 낮추려고 유효한 거래를 빼지도 않습니다. 무엇을 예측하는지, 적용할 거래의 범위, 입력 오류와 통계적 후보를 어떻게 나눌지를 미리 정합니다. 이 구분은 <a href="/learn/stats/train-validation-test/">23장 「학습·검증·시험 자료와 데이터 누수」</a>와 이어집니다.</p>')
    sec('practice', '확인 문제', '후보 판정과 제외 결정을 구별해 보세요',
        '<ol class="learn-exercises">'
        '<li>Q1=98, Q3=168, k=1.5일 때 273은 후보일까요?<details><summary>답과 해설</summary><p>아닙니다. 상한은 273이고 울타리와 같은 값은 후보가 아닙니다. 273보다 큰 값만 위쪽 후보입니다. 공통 자료에는 단가 273이 없습니다.</p></details></li>'
        '<li>배수를 1.5에서 3으로 바꾸면 후보는 반드시 줄어들까요?<details><summary>답과 해설</summary><p>반드시 줄어들지는 않습니다. 같은 자료와 분위수라면 줄거나 그대로입니다. 이번 두 절반 방식에서는 세 배수 모두 480 한 건입니다.</p></details></li>'
        '<li>어떤 계산은 480만, 다른 계산은 268과 480을 후보로 봅니다. 오류일까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 두 절반 방식의 상한은 273이고 Type 7의 상한은 266.5입니다. 분위수 계산법이 다르면 후보도 달라집니다.</p></details></li>'
        '<li>7번을 빼서 평균이 146.33에서 134.83이 되면 더 정확할까요?<details><summary>답과 해설</summary><p>아닙니다. 계산에 넣은 관측이 달라져 평균이 바뀐 것입니다. 그 거래가 유효한지, 분석 목적에 넣는지를 확인하지 않고 정확하다고 말할 수 없습니다.</p></details></li>'
        '<li>480이 후보지만 정상적인 고가 거래라면 무조건 제외할까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 유효한 거래도 후보일 수 있습니다. 포함과 제외는 분석 목적, 비교 집단, 민감도 비교에 따라 정합니다.</p></details></li>'
        '</ol>')
    sec('macro', 'CH2 Macro에서 읽기', '이상치 제외를 켜기 전에 기준을 확인합니다',
        '<p>아래는 토지 필터의 IQR 설정 위치입니다. 캡처에서는 체크가 해제되어 있습니다. 공통 30건에 필터를 적용한 결과가 아니고, 현재 화면과 다를 수 있습니다.</p>'
        '<figure class="learn-capture learn-capture--detail"><a href="../assets/captures/land-iqr-filter-options.png" target="_blank" rel="noopener"><img src="../assets/captures/land-iqr-filter-options.png" width="436" height="181" loading="lazy" alt="토지 필터의 이상치 제외 IQR. 체크는 해제되어 있고 배수 1.5, 2, 3은 흐리게 표시됩니다."/></a><figcaption class="learn-capture__caption">이상치 제외(IQR)가 꺼져 있어 배수 선택이 비활성화된 화면입니다. 후보 건수를 보여 주는 화면은 아닙니다. <a href="../assets/captures/land-iqr-filter-options.png" target="_blank" rel="noopener">원본 크게 보기 ↗</a></figcaption></figure>'
        '<ol class="learn-screen-reading">'
        '<li><strong>변수:</strong> 확인한 토지 필터와 토지 회귀는 거래단가에 울타리를 적용합니다. 거래금액 합계가 아닙니다.</li>'
        '<li><strong>비교 집단:</strong> 필터를 켠 집계는 전체, 읍면동, 용도×지목 칸, 연도 목록마다 그 목록의 단가로 울타리를 다시 구합니다. 기본통계 매트릭스 조회는 이 필터를 켜지 않습니다.</li>'
        '<li><strong>배수:</strong> 1.5, 2, 3 중 하나이고 기본값은 3입니다. 큰 배수가 더 정확한 것은 아닙니다.</li>'
        '<li><strong>분위수:</strong> 서비스의 Q1·Q3는 선형 보간입니다. 이 장의 Type 7과 같은 계열이고, 학습 페이지의 두 절반 방식과는 다릅니다. 울타리와 같은 단가는 남깁니다.</li>'
        '<li><strong>건수:</strong> 설정 화면만으로는 몇 건이 빠졌는지 알 수 없습니다. 결과의 건수를 함께 봅니다. 4건 미만이면 기본통계 필터는 울타리를 적용하지 않습니다.</li>'
        '<li><strong>원장:</strong> 제외는 그 분석 목록에서 빼는 처리입니다. 거래 원장의 행을 지우거나 가격을 고치지 않습니다. 값을 273 같은 경계로 바꾸는 기능도 아닙니다.</li>'
        '<li><strong>회귀:</strong> 토지 회귀는 그 분석에 들어온 단가 전체로 울타리를 한 번 계산합니다. 용도×지목 칸마다 따로 구하는 필터와 범위가 같다고 보지 않습니다.</li>'
        '</ol>'
        '<p>IQR이 0이면 계산을 멈추는 특별한 분기는 없습니다. 울타리가 한 값으로 겹치면 그 값과 다른 단가가 후보가 될 수 있습니다. 기간을 3년·5년·7년으로 넓혀도 후보가 반드시 늘어나지는 않습니다. 비교에 들어가는 거래 구성이 달라지기 때문입니다.</p>'
        '<p>이 옵션은 거래를 정답과 오답으로 나누는 기능이 아닙니다. 정한 규칙으로 특이한 단가를 찾아 이번 분석의 범위를 조정하는 도구입니다.</p>'
        '<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p>')
    sec('recap', '결론 · 학습 요약', '이상치 탐지는 삭제가 아니라 확인의 출발점입니다',
        '<ul class="learn-recap-list">'
        '<li><strong>후보:</strong> 다른 값과 멀리 떨어진 관측을 표시한 것입니다. 입력 오류와 같지 않습니다.</li>'
        '<li><strong>울타리:</strong> Q1−k×IQR과 Q3+k×IQR입니다. 경계와 같은 값은 이번 규칙에서 후보가 아닙니다.</li>'
        '<li><strong>수염:</strong> 울타리 안의 실제 최솟값과 최댓값까지입니다.</li>'
        '<li><strong>계산법과 집단:</strong> 분위수 산식과 비교 집단이 바뀌면 후보도 바뀔 수 있습니다.</li>'
        '<li><strong>민감도:</strong> 제외하면 평균과 표준편차를 남은 자료로 다시 계산합니다. 숫자가 줄었다고 더 정확하지는 않습니다.</li>'
        '<li><strong>처리:</strong> 절사는 관측을 빼고, 값을 경계로 바꾸는 것과 다릅니다. 원자료는 근거 없이 지우거나 고치지 않습니다.</li>'
        '</ul>'
        '<p>다음 <a href="/learn/stats/probability/">8장 「확률의 기초와 조건부확률」</a>에서는 조건에 따라 달라지는 비율을 살펴봅니다.</p>'
        '<p>표시하고, 원자료를 확인하고, 포함과 제외를 비교한 뒤 근거를 남깁니다. 표준편차나 평균이 작아졌다는 이유로 유효한 거래를 빼지는 않습니다.</p>'
        '<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul>'
        '<li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm">NIST/SEMATECH e-Handbook: Box Plot</a></li>'
        '<li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm">NIST/SEMATECH e-Handbook: Detection of Outliers</a></li>'
        '</ul><p class="learn-source-note">참고자료 확인일: 2026-10-07. 그림 1~4는 공통 학습자료 30건입니다. 필터 화면은 설정 위치를 보여 주는 캡처입니다.</p></div></details>')

    page = ROOT / 'iqr-outliers' / 'index.html'
    html = page.read_text(encoding='utf-8')
    article = '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="이상치와 IQR">\n' + '\n'.join(parts) + '\n</article>'
    html = re.sub(r'<article.*?</article>', article, html, count=1, flags=re.S)
    html = re.sub(r'(name="description"\s+content=").*?("\s*/>)', r'\1IQR 울타리, 배수와 분위수 계산법, 집단별 후보와 포함·제외의 차이를 공통 30건으로 설명합니다.\2', html, count=1, flags=re.S)
    if 'iqr-outliers/chapter.css' not in html:
        html = html.replace(
            'learn-reader.css?v=20261026-toc" />',
            'learn-reader.css?v=20261026-toc" />\n    <link rel="stylesheet" href="/learn/stats/iqr-outliers/chapter.css?v=20261026-13" />',
        )
    html = re.sub(r'\n\s*<script type="application/json" id="iq-data">.*?</script>', '', html, flags=re.S)
    html = re.sub(r'\n\s*<script type="module" src="/learn/stats/iqr-outliers/experiment\.js[^"]*"></script>', '', html)
    payload = json.dumps({'rows': [{'id': r['id'], 'group': r['group'], 'price': r['price']} for r in rows]}, ensure_ascii=False)
    html = html.replace('</body>', f'    <script type="application/json" id="iq-data">{payload}</script>\n    <script type="module" src="/learn/stats/iqr-outliers/experiment.js?v=20261026-14"></script>\n  </body>')
    page.write_text(html, encoding='utf-8')

    written = page.read_text(encoding='utf-8')
    charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', written, re.S)]
    assert len(charts) == 4
    assert [v for v in values if v < -7 or v > 273] == [480]
    assert sorted(v for v in values if v < -1.5 or v > 266.5) == [268, 480]
    for svg in charts:
        for bar in svg.findall('.//rect'):
            attrs = bar.attrib
            if 'data-k' in attrs:
                k = float(attrs['data-k'])
                lo, hi = 98 - k * 70, 168 + k * 70
                assert float(attrs['data-low']) == lo and float(attrs['data-high']) == hi
                assert abs(float(attrs['x']) - (105 + (lo + 120) * .75)) < 1e-8
                assert float(attrs['width']) == (hi - lo) * .75
                assert [v for v in values if v < lo or v > hi] == [480]
            if 'data-group' in attrs:
                assert float(attrs['data-upper']) == {'전체': 273, '주거': 168, '상업': 401.5}[attrs['data-group']]
            if 'data-metric' in attrs:
                fn = {'평균': mean, '중앙값': median, '표준편차': pstdev}[attrs['data-metric']]
                expected = fn(values if attrs['data-series'] == 'all' else other)
                assert abs(float(attrs['data-value']) - expected) < 1e-8
                assert abs(float(attrs['width']) - 2.5 * expected) < 1e-8
    ids = re.findall(r'\bid="([^"]+)"', written)
    assert len(ids) == len(set(ids))
    assert 'id="iqr-multiplier"' in written and 'id="fences"' in written
    assert '3단계, 핵심' in written and '★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화' in written
    assert 'land-iqr-filter-options.png' in written
    assert not re.search(r'<details\b[^>]*\bopen', re.search(r'<section[^>]*id="practice".*?</section>', written, re.S)[0])
    assert '[그림 ' not in written and written.count('<svg ') == 4
    print('chapter 07 fences', q1, q3, 'drop-sd', round(pstdev(other), 2), 'winsor-mean', round(mean(winsor), 2))

if __name__ == '__main__':
    build()
