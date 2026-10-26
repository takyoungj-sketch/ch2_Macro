"""Generate chapter 08 from the fixed 100-trade table and 1,000-trade screen."""
from pathlib import Path
from html import escape
from collections import Counter
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DESCRIPTION = (
    '08장 전용 가상 학습 자료. 거래 100건의 분할표와 오류 탐지 1,000건이며 '
    '실제 조사나 서비스 성능이 아님.'
)


def screen(percent):
    total = 1000
    errors = total * percent // 100
    normal = total - errors
    tp = errors * 9 // 10
    fp = normal // 10
    fn = errors - tp
    tn = normal - fp
    flagged = tp + fp
    return {
        'total': total, 'errors': errors, 'normal': normal,
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'flagged': flagged, 'ppv': tp / flagged,
    }


def build():
    raw = (ROOT / 'probability-example.json').read_text(encoding='utf-8')
    example = json.loads(raw)
    table = example['table']
    assert table == {'A_B': 18, 'A_notB': 22, 'notA_B': 12, 'notA_notB': 48}
    assert sum(table.values()) == 100
    screening = example['screening']
    assert screening == {
        'total': 1000, 'errors': 20, 'true_positive': 18, 'false_positive': 98,
    }
    if example['description'] != DESCRIPTION:
        assert raw.count(example['description']) == 1
        raw = raw.replace(example['description'], DESCRIPTION, 1)
        (ROOT / 'probability-example.json').write_text(raw, encoding='utf-8')
        example = json.loads(raw)
    assert example['table'] == table and example['screening'] == screening

    residential = table['A_B'] + table['A_notB']
    large = table['A_B'] + table['notA_B']
    union = residential + large - table['A_B']
    neither = table['notA_notB']
    assert (residential, large, union, neither) == (40, 30, 52, 48)
    assert table['A_B'] / large == .6 and table['A_B'] / residential == .45
    assert abs(.4 * .3 - .12) < 1e-12 and table['A_B'] / 100 != .12
    assert abs(.4 * .45 + .6 * .20 - .30) < 1e-12
    assert abs(.45 * .40 / .30 - .60) < 1e-12
    assert round(40 / 100 * 39 / 99 * 100, 2) == 15.76
    joints = (.4 * .45, .4 * .55, .6 * .20, .6 * .80)
    assert abs(sum(joints) - 1) < 1e-12
    base = screen(2)
    assert (base['tp'], base['fp'], base['fn'], base['tn']) == (18, 98, 2, 882)
    assert round(base['ppv'] * 100, 2) == 15.52
    expected_ppv = {1: 8.33, 2: 15.52, 5: 32.14, 10: 50.0, 20: 69.23}
    for percent, shown in expected_ppv.items():
        result = screen(percent)
        assert result['total'] == 1000
        assert result['tp'] + result['fn'] == result['errors']
        assert result['fp'] + result['tn'] == result['normal']
        assert result['tp'] / result['errors'] == .9
        assert result['fp'] / result['normal'] == .1
        assert round(result['ppv'] * 100, 2) == shown
        assert all(isinstance(result[key], int) for key in ('errors', 'tp', 'fp', 'fn', 'tn'))

    def t(x, y, text, extra=''):
        return f'<text x="{x}" y="{y}" {extra}>{escape(str(text))}</text>'

    def line(x1, y1, x2, y2):
        return (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#94a3b8" pointer-events="none"/>'
        )

    def box(x, y, w, h, color, extra=''):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" {extra}/>'

    def fig(svg_id, title, desc, body, caption, height):
        return (
            f'<figure class="learn-chart learn-chart--wide pr-chart">'
            f'<svg viewBox="0 0 640 {height}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc">'
            f'<title id="{svg_id}-title">{escape(title)}</title>'
            f'<desc id="{svg_id}-desc">{escape(desc)}</desc>{body}</svg>'
            f'<figcaption id="{svg_id}-caption" class="learn-chart__caption">{escape(caption)}</figcaption>'
            f'</figure>'
        )

    body = t(24, 27, '100건을 겹치지 않는 네 칸으로 나눕니다')
    legend = (
        ('A_B', 18, '#2563eb', '둘 다 18'),
        ('A_notB', 22, '#93c5fd', '주거만 22'),
        ('notA_B', 12, '#f59e0b', '큰 면적만 12'),
        ('notA_notB', 48, '#cbd5e1', '둘 다 아님 48'),
    )
    for i, (key, count, color, label) in enumerate(legend):
        start = sum(list(table.values())[:i])
        for j in range(start, start + count):
            body += box(
                40 + (j % 10) * 26, 55 + (j // 10) * 26, 22, 22, color,
                f'data-cell="{key}" stroke="#64748b" stroke-width="1"',
            )
        body += box(335, 70 + i * 58, 18, 18, color)
        body += t(365, 85 + i * 58, label)
    body += t(24, 340, '한 칸 = 거래 1건. 위치는 지역이나 단가가 아닙니다.')
    figure1 = fig(
        'events', '사건과 분할표',
        '그림 1. 가상 거래 100건. 주거 40건, 면적 100㎡ 이상 30건, 둘 다 18건입니다.',
        body,
        '그림 1. 가상 거래 100건. 교집합은 둘 다, 합집합은 적어도 하나입니다. 칸의 위치는 지역이나 단가가 아닙니다.',
        365,
    )

    body = t(24, 28, '같은 18건도 분모가 달라지면 비율이 달라집니다')
    for i, (label, num, den) in enumerate((('P(A)', 40, 100), ('P(A|B)', 18, 30), ('P(B|A)', 18, 40))):
        y = 75 + i * 78
        value = num / den
        body += t(24, y + 18, label)
        body += box(160, y, 340, 26, '#e2e8f0')
        body += box(160, y, 340 * value, 26, '#2563eb', f'data-numerator="{num}" data-denominator="{den}"')
        body += t(510, y + 19, f'{value:.0%}')
        body += t(160, y + 49, f'{num} / {den}건')
    body += t(24, 334, '각 막대의 전체 길이 = 그 분모의 100%')
    figure2 = fig(
        'conditioning', '조건부확률의 분모',
        '그림 2. 전체 중 주거 40%, 큰 면적 중 주거 60%, 주거 중 큰 면적 45%입니다.',
        body,
        '그림 2. 같은 교집합 18건도 분모가 100·30·40이면 18%·60%·45%가 됩니다. P(A|B)와 P(B|A)는 다른 확률입니다.',
        361,
    )

    body = t(24, 28, '경로 안에서는 곱하고, 서로 배반인 경로는 더합니다')
    for coords in (
        (60, 175, 250, 100), (60, 175, 250, 265),
        (285, 100, 490, 65), (285, 100, 490, 150),
        (285, 265, 490, 230), (285, 265, 490, 315),
    ):
        body += line(*coords)
    for x, y, text in (
        (24, 160, '전체'), (105, 100, 'P(A)=0.40'), (95, 270, 'P(Aᶜ)=0.60'),
        (225, 83, 'A'), (222, 290, 'Aᶜ'),
        (330, 59, 'P(B|A)=0.45'), (310, 155, 'P(Bᶜ|A)=0.55'),
        (320, 215, 'P(B|Aᶜ)=0.20'), (310, 340, 'P(Bᶜ|Aᶜ)=0.80'),
        (505, 70, 'B: 0.18'), (505, 155, 'Bᶜ: 0.22'),
        (505, 235, 'B: 0.12'), (505, 320, 'Bᶜ: 0.48'),
    ):
        body += t(x, y, text)
    for cx, cy, path in ((490, 65, 'AB'), (490, 150, 'AnotB'), (490, 230, 'notAB'), (490, 315, 'neither')):
        body += (
            f'<circle cx="{cx}" cy="{cy}" r="16" fill="none" stroke="#64748b" '
            f'stroke-width="1" pointer-events="all" data-path="{path}"/>'
        )
    body += t(24, 383, 'P(B) = 0.40×0.45 + 0.60×0.20 = 0.30')
    figure3 = fig(
        'tree', '곱셈법칙과 확률나무',
        '그림 3. 네 말단 확률 0.18, 0.22, 0.12, 0.48의 합은 1입니다.',
        body,
        '그림 3. 가상 거래 100건의 확률나무. 끝의 값은 전체에 대한 결합확률입니다. 선의 길이는 확률 크기가 아닙니다.',
        410,
    )

    body = t(24, 28, '탐지율과 표시된 거래의 실제 오류 비율은 다릅니다')
    for y, note, flag, color, bar_id in (
        (58, '실제 오류 20건 중 18건 표시', 18, '#2563eb', 'pr-flag-error'),
        (150, '정상 980건 중 98건 표시', 98, '#f59e0b', 'pr-flag-normal'),
    ):
        body += t(24, y - 10, note, f'id="{bar_id}-note"')
        body += box(24, y, flag * 2.6, 28, color, f'id="{bar_id}" data-flagged="{flag}"')
        body += t(32 + flag * 2.6, y + 20, f'{flag}건', f'id="{bar_id}-label"')
    body += t(24, 250, '표시 116건 = 참양성 18 + 거짓양성 98', 'id="pr-flag-summary"')
    body += t(24, 286, '정밀도 18/116 ≈ 15.52%. 탐지율 90%와 다릅니다.', 'id="pr-flag-precision"')
    body += t(24, 322, '막대 길이는 표시 건수에 비례합니다. 서비스 성능이 아닙니다.')
    figure4 = fig(
        'base-rate', '오류 탐지와 기초 발생률',
        '그림 4. 가상 거래 1,000건. 실제 오류 2%, 탐지율 90%, 오탐률 10%입니다.',
        body,
        '그림 4. 기본 예제는 실제 오류율 2%입니다. 탐지율 90%와 정밀도 약 15.52%는 다른 분모입니다. 서비스 성능이 아닙니다.',
        348,
    )

    def controls(label, buttons, status_id, note):
        return (
            f'<div class="pr-controls" hidden><p>{note}</p>'
            f'<div class="pr-shortcuts" role="group" aria-label="{escape(label)}">{buttons}</div>'
            f'<p id="{status_id}" role="status"></p></div>'
        )

    def button(attr, value, label):
        return f'<button type="button" {attr}="{escape(value)}" aria-pressed="false">{escape(label)}</button>'

    event_buttons = ''.join(button('data-event', value, label) for value, label in (
        ('A', 'A 주거'), ('B', 'B 큰 면적'), ('both', 'A∩B'),
        ('either', 'A∪B'), ('notA', 'Aᶜ 비주거'), ('neither', '둘 다 아님'),
    ))
    condition_buttons = ''.join(button('data-condition', value, label) for value, label in (
        ('A', '전체 중 주거'), ('A|B', '큰 면적 중 주거'), ('B|A', '주거 중 큰 면적'),
    )) + '<button type="button" data-empty="yes" aria-pressed="false">분모 0건</button>'
    path_buttons = ''.join(button('data-path-choice', value, label) for value, label in (
        ('AB', '주거·큰 면적'), ('AnotB', '주거·작은 면적'),
        ('notAB', '비주거·큰 면적'), ('neither', '비주거·작은 면적'),
    ))
    rate_buttons = ''.join(
        button('data-rate', str(percent), f'오류율 {percent}%')
        for percent in (1, 2, 5, 10, 20)
    )

    parts = []

    def sec(section_id, label, title, body_html):
        parts.append(
            f'<section class="learn-chapter__step" id="{section_id}" data-toc-label="{escape(label)}">'
            f'<p class="learn-chapter__label">{escape(label)}</p><h2>{title}</h2>{body_html}</section>'
        )

    sec(
        'quick-start', '서두 · 학습목표',
        '같은 18건인데 왜 확률은 18%·45%·60%로 달라질까요?',
        '<p>어느 지역의 거래 100건을 가정해 보겠습니다. 주거 거래는 40건, 면적 100㎡ 이상인 거래는 30건, 둘 다 해당하는 거래는 18건입니다.</p>'
        '<ul><li><strong>전체 중 주거이면서 큰 면적:</strong> 18/100=18%입니다.</li>'
        '<li><strong>주거 중 큰 면적:</strong> 18/40=45%입니다.</li>'
        '<li><strong>큰 면적 중 주거:</strong> 18/30=60%입니다.</li></ul>'
        '<p>세 질문은 같은 18건을 쓰지만 분모, 곧 기준 집단이 다릅니다. 식을 쓰기 전에 어떤 사건을 묻고 무엇을 조건으로 삼는지 확인하는 것이 첫 단계입니다.</p>'
        '<ul class="learn-objectives">'
        '<li>표본공간과 사건, 교집합·합집합·여사건을 구별합니다.</li>'
        '<li>덧셈법칙과 곱셈법칙, 조건부확률의 분모 변화를 계산합니다.</li>'
        '<li>P(A|B)와 P(B|A), 독립과 배반을 구별합니다.</li>'
        '<li>전확률법칙과 베이즈 정리, 탐지율·오탐률·정밀도를 계산합니다.</li>'
        '<li>CH2 Macro의 조건별 거래 비율에서 분모를 확인합니다.</li></ul>'
        '<p>확률은 정한 실험에서 사건이 발생할 가능성을 0부터 1로 나타낸 값입니다. 이번 장은 <strong>고정된 가상 목록에서 거래 한 건을 같은 확률로 뽑는 실험</strong>을 사용합니다. 100건이면 각 거래의 확률은 1/100입니다. 거래금액이 큰 거래를 더 자주 뽑는 절차라면 건수 비율과 선택확률은 달라질 수 있습니다. 관측한 거래 비율을 지역의 모든 부동산 구성비로 넓혀 읽지도 않습니다. <a href="/learn/stats/population-and-sampling/">2장 모집단과 표본</a>의 구분이 여기에도 적용됩니다.</p>'
        '<p>이 100건은 1~7장의 공통 30건과 다른 자료입니다. 뒤의 오류 탐지는 또 다른 1,000건입니다. 둘 다 교육용 가정이므로 실제 거래 통계나 서비스 성능이 아닙니다.</p>',
    )
    sec(
        'events', '표본공간과 사건',
        '가능한 결과 전체와 관심 있는 결과를 구별합니다',
        '<p><strong>표본공간</strong>은 한 실험에서 가능한 결과를 모두 모은 집합이고, 보통 Ω로 적습니다. 이번 실험의 표본공간은 거래 100건의 ID입니다. 관심 있는 결과의 묶음이 <strong>사건</strong>입니다.</p>'
        '<ul><li><strong>사건 A:</strong> 선택된 거래가 주거입니다. 40건입니다.</li>'
        '<li><strong>사건 B:</strong> 면적이 100㎡ 이상입니다. 30건입니다.</li>'
        '<li><strong>A∩B:</strong> 둘 다 해당합니다. 18건입니다.</li>'
        '<li><strong>A∪B:</strong> 적어도 하나입니다. 둘 다 해당하는 경우도 포함합니다.</li>'
        '<li><strong>Aᶜ:</strong> 주거가 아닙니다. 60건입니다.</li></ul>'
        + controls('사건 선택', event_buttons, 'pr-event-status', '사건을 고르면 그림과 분할표에서 같은 칸을 강조합니다. 합집합은 교집합을 한 번만 셉니다.')
        + figure1
        + '<div class="learn-data learn-data--full pr-table"><table id="pr-split"><caption>가상 거래 100건 · 유형과 면적이 모두 있는 교육용 분할표</caption>'
        '<thead><tr><th scope="col">구분</th><th scope="col">B: 100㎡ 이상</th><th scope="col">Bᶜ: 100㎡ 미만</th><th scope="col">합계</th></tr></thead>'
        '<tbody><tr><th scope="row">A: 주거</th><td data-cell="A_B">18</td><td data-cell="A_notB">22</td><td>40</td></tr>'
        '<tr><th scope="row">Aᶜ: 비주거</th><td data-cell="notA_B">12</td><td data-cell="notA_notB">48</td><td>60</td></tr>'
        '<tr><th scope="row">합계</th><td>30</td><td>70</td><td>100</td></tr></tbody></table></div>'
        '<p>18+22+12+48=100입니다. 각 거래는 네 칸 중 정확히 하나에 들어갑니다. 이 예제는 유형과 면적이 모두 있다고 가정합니다. 실제 자료에서 값이 빠지면, 미상을 따로 둘지 계산에서 뺄지에 따라 분모가 달라집니다. <a href="../probability-example.json">가상 집계값(JSON)</a>의 칸 수는 위 표와 같습니다.</p>',
    )
    sec(
        'rules', '확률의 덧셈법칙',
        '겹치는 거래를 두 번 세지 않습니다',
        '<p>임의의 사건 A에 대해 0≤P(A)≤1이고 P(Ω)=1입니다. P(Aᶜ)=1−P(A)입니다. 이번 실험에서 P(A)=40/100=0.40이므로 P(Aᶜ)=0.60입니다. 0.40은 40%와 같은 수치이고, 해석은 고정된 100건에서 한 건을 같은 확률로 뽑는 실험에 한정됩니다.</p>'
        '<p>주거이거나 면적이 100㎡ 이상일 확률은 40과 30을 그대로 더하면 안 됩니다. 둘 다 해당하는 18건이 두 번 들어갑니다.</p>'
        '<p><strong>P(A∪B)=P(A)+P(B)−P(A∩B)=0.40+0.30−0.18=0.52</strong></p>'
        '<p>따라서 52건, 52%입니다. 둘 다 해당하지 않을 확률은 1−0.52=0.48이고, 분할표의 48건과 같습니다. 덧셈법칙은 사건들이 겹치는지 먼저 확인한 뒤 사용합니다.</p>',
    )
    sec(
        'conditional', '조건부확률',
        '조건이 달라지면 분모도 달라집니다',
        '<p><strong>P(A|B)</strong>는 B가 일어났다는 조건에서 A일 확률입니다. 세로선 오른쪽이 조건입니다. 조건이 시간상 먼저라는 뜻은 아니고, 면적과 주거처럼 함께 관측한 특성에도 쓸 수 있습니다.</p>'
        '<p><strong>P(A|B)=P(A∩B)/P(B)</strong>이며 P(B)&gt;0이어야 합니다. 큰 면적 30건 중 주거 18건이므로 P(A|B)=18/30=0.60입니다. 주거 40건 중 큰 면적 18건은 P(B|A)=18/40=0.45입니다.</p>'
        + controls(
            '조건부확률 선택', condition_buttons, 'pr-condition-status',
            '전체 중 주거, 큰 면적 중 주거, 주거 중 큰 면적을 바꾸면 분모와 계산식이 함께 바뀝니다. 화면에서 누른 순서가 조건의 방향을 정하지는 않습니다.',
        )
        + figure2
        + '<div class="learn-data learn-data--full pr-table"><table><caption>같은 교집합과 서로 다른 분모</caption>'
        '<thead><tr><th scope="col">질문</th><th scope="col">계산</th><th scope="col">결과</th></tr></thead><tbody>'
        '<tr><th scope="row">전체 중 주거</th><td>40/100</td><td>40%</td></tr>'
        '<tr><th scope="row">큰 면적 중 주거</th><td>18/30</td><td>60%</td></tr>'
        '<tr><th scope="row">주거 중 큰 면적</th><td>18/40</td><td>45%</td></tr>'
        '</tbody></table></div>'
        '<p>면적 1,000㎡ 이상인 주거 거래가 0건이라면, 그 조건 안의 비율은 0/0이라 정의되지 않습니다. <strong>0%는 분모가 있고 사건이 0건일 때</strong> 씁니다. 20건 중 0건은 0%이고, 분모가 없거나 결측으로 분모를 모르면 계산할 수 없음입니다. 위 버튼의 「분모 0건」은 이 구분을 보여 주며 0%로 표시하지 않습니다.</p>',
    )
    sec(
        'independence', '독립과 배반',
        '함께 일어나지 않는 것과 서로 관계없는 것은 다릅니다',
        '<p>A와 B가 <strong>독립</strong>이면 P(A∩B)=P(A)P(B)입니다. P(B)&gt;0이면 P(A|B)=P(A)라고 말할 수도 있습니다. B를 알아도 A의 확률이 그대로라는 뜻입니다.</p>'
        '<p>이번 목록에서 P(A)P(B)=0.40×0.30=0.12입니다. 실제 교집합은 0.18이므로 이 무작위 추출에서는 독립이 아닙니다. 주거와 면적 사이에 확률적 관련이 있다는 뜻이지, 면적이 주거 여부의 원인이라는 뜻은 아닙니다.</p>'
        '<p><strong>배반</strong>은 두 사건이 동시에 일어날 수 없다는 뜻입니다. 한 거래를 주거와 비주거 중 하나로 나누면 P(A∩Aᶜ)=0입니다. 확률이 모두 양수인 두 사건이 배반이면 독립일 수 없습니다. 교집합은 0인데 두 확률의 곱은 양수이기 때문입니다. 예를 들어 30%와 40%인 배반 사건의 곱은 0.12입니다.</p>'
        '<div class="learn-data learn-data--full pr-table"><table><caption>독립과 배반</caption>'
        '<thead><tr><th scope="col">개념</th><th scope="col">핵심 질문</th></tr></thead><tbody>'
        '<tr><th scope="row">독립</th><td>한 사건을 알아도 다른 사건의 확률이 같은가</td></tr>'
        '<tr><th scope="row">배반</th><td>두 사건이 동시에 일어날 수 없는가</td></tr>'
        '</tbody></table></div>'
        '<p>같은 100건에서 주거 두 건을 뽑는 경우를 보겠습니다. 뽑은 거래를 다시 넣으면 매번 100건이므로 0.40×0.40=0.16, 곧 16%입니다. 다시 넣지 않으면 첫 거래가 주거일 때 남은 거래는 99건, 주거는 39건입니다.</p>'
        '<p><strong>(40/100)×(39/99)≈0.1576, 약 15.76%</strong></p>'
        '<p>비복원 추출은 앞의 결과가 다음 확률을 바꾸므로 독립 시행으로 설명하지 않습니다.</p>',
    )
    sec(
        'tree', '곱셈법칙과 전확률',
        '집단별 비율은 집단의 비중을 반영해 합칩니다',
        '<p>P(B|A)=P(A∩B)/P(A)의 양변에 P(A)를 곱하면 <strong>P(A∩B)=P(A)P(B|A)</strong>입니다. 독립이 아니어도 사용할 수 있습니다. 주거 40%와 주거 중 큰 면적 45%를 곱하면 0.40×0.45=0.18입니다. 독립일 때만 P(A∩B)=P(A)P(B)로 바꿉니다. 확인되지 않았다면 조건부확률을 일반 확률로 바꾸지 않습니다.</p>'
        + controls('확률나무 경로', path_buttons, 'pr-path-status', '네 말단 중 하나를 고르면 첫 가지, 조건부확률, 곱셈식, 결합확률, 분할표 건수를 함께 보여 줍니다. 그림의 끝점도 고를 수 있습니다.')
        + figure3
        + '<div class="learn-data learn-data--full pr-table"><table><caption>확률나무의 네 경로</caption>'
        '<thead><tr><th scope="col">경로</th><th scope="col">계산</th><th scope="col">확률</th></tr></thead><tbody>'
        '<tr><th scope="row">주거·100㎡ 이상</th><td>0.40×0.45</td><td>18%</td></tr>'
        '<tr><th scope="row">주거·100㎡ 미만</th><td>0.40×0.55</td><td>22%</td></tr>'
        '<tr><th scope="row">비주거·100㎡ 이상</th><td>0.60×0.20</td><td>12%</td></tr>'
        '<tr><th scope="row">비주거·100㎡ 미만</th><td>0.60×0.80</td><td>48%</td></tr>'
        '</tbody></table></div>'
        '<p>첫 가지는 0.40과 0.60, 주거 안의 가지는 18/40=0.45와 22/40=0.55, 비주거 안의 가지는 12/60=0.20과 48/60=0.80입니다. 각 부모 아래의 가지 합은 1이고, 네 말단의 합도 0.18+0.22+0.12+0.48=1입니다.</p>'
        '<p>큰 면적 비율의 단순평균 (0.45+0.20)/2=0.325는 전체 비율이 아닙니다. 주거 40건과 비주거 60건의 비중이 다르기 때문입니다.</p>'
        '<p><strong>P(B)=0.40×0.45+0.60×0.20=0.18+0.12=0.30</strong></p>'
        '<p>이것이 전확률법칙입니다. 4장의 가중평균처럼, 집단별 비율을 합칠 때는 각 집단의 비중을 반영합니다.</p>',
    )
    sec(
        'bayes', '베이즈 정리',
        '조건의 방향을 바꿀 때 기초 발생률을 반영합니다',
        '<p>P(B|A)=0.45와 P(A|B)=0.60은 다릅니다. 곱셈법칙을 양쪽으로 쓰면 P(A∩B)=P(A)P(B|A)=P(B)P(A|B)이므로 다음과 같습니다.</p>'
        '<p><strong>P(A|B)=P(B|A)P(A)/P(B)=0.45×0.40/0.30=0.60</strong></p>'
        '<p>P(B)=0이면 이 조건부확률은 계산하지 않습니다. 여기서 P(A)=40%는 증거 B를 보기 전의 <strong>사전확률</strong>입니다. 개인적 추측이라는 뜻이 아니라, 이번 실험에서 B를 확인하기 전의 확률입니다. P(B|A)=45%는 A일 때 B가 얼마나 나타나는지를 보는 <strong>우도</strong>입니다. 우도를 사후확률로 읽지 않습니다. B를 확인한 뒤의 P(A|B)=60%가 <strong>사후확률</strong>입니다.</p>'
        '<p>이제 자료가 바뀝니다. 앞의 100건이 아니라 별도의 가상 거래 1,000건입니다. 실제 오류는 20건(2%), 정상은 980건입니다. 탐지율은 90%, 정상 거래의 오탐률은 10%라고 가정합니다. 이 숫자는 교육용 가정이고 CH2 Macro의 탐지 성능이 아닙니다. <a href="/learn/stats/iqr-outliers/">7장의 IQR 필터</a>는 이상치 후보를 표시하는 절차라서, 오류 여부가 확인된 이 탐지기와 같지 않습니다. 정답 자료가 없으면 IQR 필터의 민감도·오탐률·정밀도를 계산할 수 없습니다.</p>'
        '<p>실제 오류 20건 중 18건이 표시되고 2건은 빠집니다. 정상 980건 중 98건이 잘못 표시됩니다. 표시된 116건 중 실제 오류는 18건이므로 P(오류|표시)=18/116≈15.52%입니다. 탐지율이 90%라는 사실과 다릅니다. 정상 거래가 훨씬 많아서 오탐률 10%도 많은 건수를 만들기 때문입니다.</p>'
        + controls(
            '교육용 오류율', rate_buttons, 'pr-screen-status',
            '탐지율 90%와 오탐률 10%는 고정입니다. 실제 오류율만 1%·2%·5%·10%·20%로 바꿉니다. 기본값 2%가 원문의 예제이고, 전체는 1,000건을 유지합니다. 앞의 거래 100건 확률은 바뀌지 않습니다.',
        )
        + figure4
        + '<div class="learn-data learn-data--full pr-table"><table><caption>기본 예제 1,000건의 탐지표. 숫자를 바꾸면 이 표도 함께 바뀝니다.</caption>'
        '<thead><tr><th scope="col">실제 상태</th><th scope="col">오류로 표시</th><th scope="col">표시되지 않음</th><th scope="col">합계</th></tr></thead><tbody>'
        '<tr><th scope="row">실제 오류</th><td id="pr-tp">18</td><td id="pr-fn">2</td><td id="pr-err">20</td></tr>'
        '<tr><th scope="row">실제 정상</th><td id="pr-fp">98</td><td id="pr-tn">882</td><td id="pr-ok">980</td></tr>'
        '<tr><th scope="row">합계</th><td id="pr-flagged">116</td><td id="pr-clear">884</td><td>1,000</td></tr>'
        '</tbody></table></div>'
        '<ul><li><strong>탐지율 또는 민감도:</strong> <span id="pr-metric-sens">18/20=90%. 실제 오류 중 표시된 비율입니다.</span></li>'
        '<li><strong>오탐률:</strong> <span id="pr-metric-fpr">98/980=10%. 실제 정상 중 잘못 표시된 비율입니다.</span></li>'
        '<li><strong>특이도:</strong> <span id="pr-metric-spec">882/980=90%. 실제 정상 중 정상으로 판정한 비율입니다.</span></li>'
        '<li><strong>양성예측도 또는 정밀도:</strong> <span id="pr-metric-ppv">18/116≈15.52%. 표시된 거래 중 실제 오류 비율입니다.</span></li></ul>'
        '<p>베이즈 정리로 다시 쓰면 P(E|D)=(0.90×0.02)/(0.90×0.02+0.10×0.98)=0.018/0.116≈0.1552입니다. E는 실제 오류, D는 오류로 표시입니다. 기초 발생률 2%를 빼면 탐지율을 사후확률로 착각하기 쉽습니다.</p>'
        '<div class="learn-data learn-data--full pr-table"><table><caption>탐지율 90%, 오탐률 10%를 고정하고 실제 오류율만 바꾼 교육용 계산</caption>'
        '<thead><tr><th scope="col">실제 오류 비율</th><th scope="col">탐지율</th><th scope="col">오탐률</th><th scope="col">표시된 거래 중 실제 오류</th></tr></thead><tbody>'
        '<tr><th scope="row">1%</th><td>90%</td><td>10%</td><td>8.33%</td></tr>'
        '<tr><th scope="row">2% · 기본 예제</th><td>90%</td><td>10%</td><td>15.52%</td></tr>'
        '<tr><th scope="row">5%</th><td>90%</td><td>10%</td><td>32.14%</td></tr>'
        '<tr><th scope="row">10%</th><td>90%</td><td>10%</td><td>50.00%</td></tr>'
        '<tr><th scope="row">20%</th><td>90%</td><td>10%</td><td>69.23%</td></tr>'
        '</tbody></table></div>'
        '<p>오류율이 10%이면 0.90×0.10/(0.90×0.10+0.10×0.90)=0.09/0.18=0.50입니다. 탐지 규칙이 같아도 적용하는 집단의 기초 발생률이 달라지면 정밀도가 달라집니다. 정밀도와 민감도는 이름이 다릅니다.</p>'
        '<p>목록에서 주거가 40%였다고 다음 달의 새 거래가 주거일 확률이 40%인 것은 아닙니다. 시점, 수요와 공급, 거래 유형, 경기, 수집 범위, 성사 과정에 따라 달라질 수 있습니다. 관측 비율을 미래 확률로 쓰려면 별도의 가정과 검증이 필요합니다. 거래된 구성비와 그 지역에 있는 전체 부동산의 구성비도 별개입니다.</p>'
        '<p>큰 면적 중 주거가 60%이고 전체 중 주거가 40%라는 차이는 확률적 관련을 보여줄 뿐입니다. 면적 조건이 주거 거래를 일으킨다고 읽지는 않습니다. 이 구분은 <a href="/learn/stats/correlation/">16장 상관관계와 인과관계</a>에서 이어집니다.</p>',
    )
    sec(
        'practice', '확인 문제',
        '조건의 방향과 분모를 먼저 확인해 보세요',
        '<ol class="learn-exercises">'
        '<li>주거 A가 40건, 면적 100㎡ 이상 B가 30건, 둘 다 해당하는 거래가 18건입니다. A 또는 B에 해당하는 거래는 몇 건일까요?'
        '<details><summary>답과 해설</summary><p>합집합에서는 교집합을 한 번 뺍니다. 40+30−18=52건이며 전체 100건 중 52%입니다.</p></details></li>'
        '<li>P(A|B)와 P(B|A)는 각각 얼마일까요?'
        '<details><summary>답과 해설</summary><p>P(A|B)는 30건 중 18건이라 60%입니다. P(B|A)는 40건 중 18건이라 45%입니다. 분모가 달라 일반적으로 같지 않습니다.</p></details></li>'
        '<li>배반인 두 사건의 확률이 각각 30%와 40%라면 두 사건은 독립일까요?'
        '<details><summary>답과 해설</summary><p>독립이 아닙니다. 배반이므로 교집합 확률은 0입니다. 독립이라면 0.3×0.4=0.12여야 합니다.</p></details></li>'
        '<li>오류 탐지율이 90%라면 오류로 표시된 거래의 90%가 실제 오류일까요?'
        '<details><summary>답과 해설</summary><p>그렇지 않습니다. 탐지율은 실제 오류 중 표시된 비율입니다. 기본 예제에서는 표시된 116건 중 실제 오류 18건이므로 약 15.52%입니다.</p></details></li>'
        '<li>과거 거래 중 주거 비율이 40%였습니다. 다음 달 거래가 주거일 확률도 반드시 40%일까요?'
        '<details><summary>답과 해설</summary><p>그렇게 단정할 수 없습니다. 과거 자료의 관측 구성비와 미래 거래의 발생 확률은 다릅니다. 시장의 변화와 표집 과정에 대한 별도의 가정과 검증이 필요합니다.</p></details></li>'
        '</ol>',
    )
    sec(
        'macro', 'CH2 Macro에서 읽기',
        '필터를 적용하면 계산의 기준 집단도 달라집니다',
        '<p>CH2 Macro에서 지역, 기간, 부동산 유형, 면적, 용도지역, 지목을 고르면 화면에 남는 자료가 달라집니다. 건수와 비율은 그 조건에 들어온 자료를 기준으로 읽습니다. 이 서비스가 모든 화면에서 거래 확률이나 가격 상승 확률을 보여 주지는 않습니다. 베이즈 분류기나 오류 탐지 확률을 제공한다는 뜻도 아닙니다.</p>'
        '<ul>'
        '<li><strong>전체 거래 중 특정 유형:</strong> 선택한 거래 1,000건 중 아파트 400건이면 관측 비율은 40%입니다. 그 지역에 있는 모든 부동산 중 아파트가 40%라는 뜻은 아닙니다.</li>'
        '<li><strong>면적 조건을 더하면:</strong> 분모는 더 이상 1,000건이 아니라 면적 조건을 충족한 거래입니다. 필터 전의 40%와 필터 후의 60%를 같은 모집단의 확률로 직접 비교하지 않습니다.</li>'
        '<li><strong>조건의 방향:</strong> 대지 거래 중 자연녹지지역의 비율과 자연녹지지역 거래 중 대지의 비율은 교집합 목록이 같아도 분모가 다를 수 있습니다. 지역을 먼저 누르고 면적을 나중에 누른 조작 순서가 확률식의 조건을 정하지는 않습니다.</li>'
        '<li><strong>결측과 정정:</strong> 확인한 토지 통계·목록의 공통 포함 조건은 유효하고, 취소되지 않았으며, 거래단가가 있는 자료입니다. 면적이 빠져 단가를 만들 수 없는 거래는 그 집계의 분모에 들어가지 않습니다. 집계에 쓰인 건수를 확인합니다.</li>'
        '<li><strong>0건:</strong> 확인한 거래 교차표는 칸의 건수가 0이면 0%가 아니라 「—」로 표시합니다. 분모가 없는 비율과, 분모는 있는데 해당 사건이 0건인 경우를 같은 표시로 읽지 않습니다.</li>'
        '<li><strong>집단별 비율:</strong> 읍면동 주거 비율이 20%와 80%여도 거래 건수가 다르면 시군구 비율은 50%가 아닙니다. 각 지역의 거래를 모아 다시 집계합니다. 이번 장의 전확률법칙과 같은 원칙입니다.</li>'
        '<li><strong>IQR 후보:</strong> 7장의 후보는 오류가 확인된 탐지기의 성능이 아닙니다. 이 장의 90%, 10%, 약 15.52%를 서비스 수치로 설명하지 않습니다.</li>'
        '<li><strong>예측확률:</strong> 이후 분류모형이 계산하는 확률은 과거 목록의 관측 비율과 다릅니다. 검증자료의 성능과 확률 보정을 따로 봅니다. 관련 구분은 <a href="/learn/stats/train-validation-test/">23장 학습·검증·시험</a>에서 이어집니다.</li>'
        '</ul>'
        '<p>필터별 비율은 몇 건이 해당하는지만이 아니라, 전체 몇 건 중에서 계산했는지를 함께 확인합니다.</p>'
        '<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 기본통계 열기 →</a></p>',
    )
    sec(
        'recap', '결론 · 학습 요약',
        '확률을 계산할 때는 먼저 사건과 분모를 정해야 합니다',
        '<p>같은 거래 건수도 어떤 조건을 분모로 삼는지에 따라 확률이 달라집니다. 탐지 규칙이 실제 오류를 찾아내는 비율과, 표시된 대상이 실제 오류일 확률도 다릅니다.</p>'
        '<ul class="learn-recap-list">'
        '<li><strong>표본공간과 사건:</strong> 가능한 결과 전체와 관심 있는 결과의 집합입니다.</li>'
        '<li><strong>교집합·합집합·여사건:</strong> 둘 다, 적어도 하나, 일어나지 않은 경우입니다. 합집합은 겹치는 부분을 한 번 뺍니다.</li>'
        '<li><strong>조건부확률:</strong> 조건에 해당하는 집단이 새 분모입니다. P(A|B)와 P(B|A)는 일반적으로 다릅니다.</li>'
        '<li><strong>독립과 배반:</strong> 독립은 정보를 알아도 확률이 그대로인 관계이고, 배반은 동시에 발생할 수 없는 관계입니다.</li>'
        '<li><strong>곱셈과 전확률:</strong> 경로 안에서는 곱하고, 집단별 확률은 그 집단의 비중으로 합칩니다.</li>'
        '<li><strong>베이즈 정리:</strong> 사전확률과 우도로 조건의 방향을 바꿉니다. 기초 발생률이 달라지면 사후확률도 달라집니다.</li>'
        '<li><strong>시장 해석:</strong> 과거 거래 비율을 전체 부동산 구성비나 미래 발생 확률로 자동 해석하지 않습니다.</li>'
        '</ul>'
        '<p>다음 <a href="/learn/stats/probability-distributions/">9장 「확률변수와 확률분포」</a>에서는 우연한 결과를 숫자로 나타내고, 각 값이 어떤 확률로 나오는지를 살펴봅니다.</p>'
        '<p>조건부확률을 읽을 때는 세로선 오른쪽, 곧 조건이 무엇인지 먼저 확인합니다.</p>'
        '<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/3-1-terminology">OpenStax, Introductory Statistics 2e §3.1</a> — 표본공간과 사건, 조건부확률.</li>'
        '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/3-3-two-basic-rules-of-probability">OpenStax, Introductory Statistics 2e §3.3</a> — 덧셈법칙과 곱셈법칙.</li>'
        '</ul><p class="learn-source-note">참고자료 확인일: 2026-10-07. 이 장의 100건과 1,000건은 서로 다른 교육용 가상자료입니다. 실제 거래 통계나 CH2 Macro의 오류 탐지 성능을 나타내지 않습니다.</p></div></details>',
    )

    page = ROOT / 'probability' / 'index.html'
    html = page.read_text(encoding='utf-8')
    article = (
        '<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" '
        'aria-label="확률의 기초와 조건부확률">\n' + '\n'.join(parts) + '\n</article>'
    )
    html = re.sub(r'<article.*?</article>', article, html, count=1, flags=re.S)
    html = re.sub(
        r'(name="description"\s+content=").*?("\s*/>)',
        r'\1같은 건수도 분모에 따라 달라지는 확률, 조건부확률, 베이즈 정리를 가상 거래로 살펴봅니다.\2',
        html, count=1, flags=re.S,
    )
    html = html.replace(
        'aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span>',
        'aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>',
    )
    if 'probability/chapter.css' not in html:
        html = html.replace(
            'learn-reader.css?v=20261026-toc" />',
            'learn-reader.css?v=20261026-toc" />\n    <link rel="stylesheet" href="/learn/stats/probability/chapter.css?v=20261026-15" />',
        )
    html = re.sub(r'\n\s*<script type="application/json" id="pr-data">.*?</script>', '', html, flags=re.S)
    html = re.sub(r'\n\s*<script type="module" src="/learn/stats/probability/experiment\.js[^"]*"></script>', '', html)
    payload = json.dumps(example, ensure_ascii=False)
    html = html.replace(
        '</body>',
        f'    <script type="application/json" id="pr-data">{payload}</script>\n'
        '    <script type="module" src="/learn/stats/probability/experiment.js?v=20261026-17"></script>\n  </body>',
    )
    page.write_text(html, encoding='utf-8')

    promote = (
        '        "slug": "probability",\n'
        '        "title": "확률의 기초와 조건부확률",\n'
        '        "soon": false,\n'
        '        "macro_relevance": 1'
    )
    promoted = promote.replace('"macro_relevance": 1', '"macro_relevance": 2')
    for path in (ROOT / 'course.json', ROOT / 'learn-stats-toc.js'):
        text = path.read_text(encoding='utf-8')
        if promote in text:
            assert text.count(promote) == 1
            path.write_text(text.replace(promote, promoted, 1), encoding='utf-8')
        else:
            assert promoted in text
    index = ROOT / 'index.html'
    index_text = index.read_text(encoding='utf-8')
    old_item = (
        'data-macro-relevance="1"><a href="/learn/stats/probability/">08. 확률의 기초와 조건부확률 '
        '<span class="learn-relevance" aria-label="Macro 활용도 1단계, 심화"><span aria-hidden="true">★☆☆</span></span>'
    )
    new_item = (
        'data-macro-relevance="2"><a href="/learn/stats/probability/">08. 확률의 기초와 조건부확률 '
        '<span class="learn-relevance" aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span></span>'
    )
    if old_item in index_text:
        assert index_text.count(old_item) == 1
        index.write_text(index_text.replace(old_item, new_item, 1), encoding='utf-8')
    else:
        assert new_item in index_text

    written = page.read_text(encoding='utf-8')
    charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', written, re.S)]
    assert len(charts) == 4
    assert dict(Counter(node.attrib['data-cell'] for node in charts[0].findall('rect') if 'data-cell' in node.attrib)) == table
    for bar in charts[1].findall('rect'):
        if 'data-numerator' in bar.attrib:
            attrs = bar.attrib
            assert abs(float(attrs['width']) - 340 * int(attrs['data-numerator']) / int(attrs['data-denominator'])) < 1e-8
    for bar in charts[3].findall('rect'):
        assert abs(float(bar.attrib['width']) - int(bar.attrib['data-flagged']) * 2.6) < 1e-8
        assert float(bar.attrib['x']) == 24
    ids = re.findall(r'\bid="([^"]+)"', written)
    assert len(ids) == len(set(ids))
    assert written.count('<svg ') == 4
    assert written.count('<summary>답과 해설</summary>') == 5
    assert '2단계, 권장' in written and '★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화' in written
    assert '1단계, 심화' not in written
    assert '08. 확률의 기초와 조건부확률' in written
    assert '[그림 ' not in written
    practice = re.search(r'<section[^>]*id="practice".*?</section>', written, re.S).group(0)
    assert not re.search(r'<details\b[^>]*\bopen', practice)
    assert 'data-flagged="18"' in written and 'data-flagged="98"' in written
    course = json.loads((ROOT / 'course.json').read_text(encoding='utf-8'))
    items = [item for group in course for item in group['items']]
    assert next(item['macro_relevance'] for item in items if item['slug'] == 'probability') == 2
    assert next(item['macro_relevance'] for item in items if item['slug'] == 'probability-distributions') == 1
    print('chapter 08 union', union, 'ppv', round(base['ppv'] * 100, 2), 'rates', expected_ppv)


if __name__ == '__main__':
    build()
