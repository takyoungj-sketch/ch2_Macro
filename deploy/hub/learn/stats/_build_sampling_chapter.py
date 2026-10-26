"""Chapter 2 body. Reuses sampling-example.json; does not regenerate it."""
from pathlib import Path
from html import escape
import json
import math
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
BLOCK = '''        "slug": "population-and-sampling",
        "title": "모집단과 표본, 자료 수집과 편향",
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
    return f'{value:.8f}'.rstrip('0').rstrip('.') or '0'


def tx(x, y, text, extra=''):
    return f'<text x="{num(x) if isinstance(x, float) else x}" y="{y}"{extra}>{escape(str(text))}</text>'


def theory_sd(sigma2, n, total):
    return math.sqrt(sigma2 / n * (total - n) / (total - 1))


def build():
    sampling = json.loads((ROOT / 'sampling-example.json').read_text(encoding='utf-8'))
    population = sampling['population']
    by_id = {row['id']: row for row in population}
    frame = [by_id[item] for item in sampling['frame_ids']]
    selected = [by_id[item] for item in sampling['selected_ids']]
    assert sampling['seed'] == 20261007
    assert len(population) == 100 and len(frame) == 40 and len(selected) == 20
    assert sum(row['group'] == 'A' for row in population) == 80
    assert sum(row['group'] == 'B' for row in population) == 20
    assert sum(row['group'] == 'A' for row in frame) == 20
    assert sum(row['group'] == 'B' for row in frame) == 20
    assert sum(row['group'] == 'A' for row in selected) == 10
    assert sum(row['group'] == 'B' for row in selected) == 10
    assert sum(row['group'] == 'A' and row['id'] not in sampling['frame_ids'] for row in population) == 60
    assert all(row['price'] == (100 if row['group'] == 'A' else 200) for row in population)
    assert sampling['population_mean'] == 120
    assert sampling['frame_mean'] == 150
    assert sampling['sample_mean'] == 150
    assert (150 - 120) ** 2 == 900
    trials = sampling['trials']
    assert [ (t['source'], t['n'], t['repetitions']) for t in trials ] == [
        ('population', 5, 500), ('population', 20, 500), ('frame', 5, 500), ('frame', 20, 500)
    ]
    expected_sd = [
        round(theory_sd(1600, 5, 100), 2),
        round(theory_sd(1600, 20, 100), 2),
        round(theory_sd(2500, 5, 40), 2),
        round(theory_sd(2500, 20, 40), 2),
    ]
    assert expected_sd == [17.52, 8.04, 21.18, 8.01]
    page_data = {
        'trials': [
            {'source': t['source'], 'n': t['n'], 'mean': t['mean'], 'sd': t['sd']}
            for t in trials
        ]
    }

    def fig1():
        body = tx(16, 24, '같은 눈금: 1건 = 2.2px · 빈칸은 목록 밖 A 60건')
        rows = [
            ('population', 36, '모집단 100건 · 평균 120', [(16, 44, '#93c5fd'), (60, 132, '#cbd5e1'), (192, 44, '#e2e8f0')], 'A 20 · 밖 60 · B 20'),
            ('frame', 124, '표집틀 40건 · 평균 150', [(16, 44, '#93c5fd'), (192, 44, '#e2e8f0')], 'A 20 · B 20'),
            ('sample', 212, '예시 표본 20건 · 평균 150', [(16, 22, '#93c5fd'), (192, 22, '#e2e8f0')], 'A 10 · B 10'),
        ]
        for stage, y, label, bars, detail in rows:
            body += f'<rect data-stage="{stage}" data-role="hit" x="8" y="{y}" width="320" height="80" rx="6" fill="#ffffff" stroke="#94a3b8"/>'
            body += tx(16, y + 22, label)
            body += tx(16, y + 40, detail)
            for x, w, fill in bars:
                body += f'<rect data-stage="{stage}" x="{x}" y="{y + 48}" width="{w}" height="22" fill="{fill}" stroke="#64748b"/>'
        return (
            '<figure class="learn-chart learn-chart--wide smp-chart"><svg id="smp-flow" viewBox="0 0 640 310" role="img" '
            'aria-labelledby="population-flow-title population-flow-desc"><title id="population-flow-title">모집단, 표집틀, 표본</title>'
            '<desc id="population-flow-desc">그림 1. 모집단 100건, 표집틀 40건, 예시 표본 20건. 목록 밖 A 60건은 빈칸입니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 1. 파랑은 A, 회색은 표집틀 밖 A, 연회색은 B입니다. 예시 표본의 10대10은 고정한 교육용 결과입니다.</figcaption></figure>'
        )

    def fig2():
        body = tx(16, 24, '구성비와 평균단가')
        specs = [
            ('population', 44, 160, 40, '모집단', 'A 80%', 'B 20%'),
            ('frame', 104, 100, 100, '표집틀', 'A 50%', 'B 50%'),
            ('sample', 164, 100, 100, '예시 표본', 'A 50%', 'B 50%'),
        ]
        for stage, y, aw, bw, name, a_label, b_label in specs:
            body += f'<rect data-stage="{stage}" data-role="hit" x="8" y="{y - 8}" width="330" height="52" rx="6" fill="#ffffff" stroke="#94a3b8"/>'
            body += tx(16, y + 18, name)
            body += f'<rect data-stage="{stage}" x="108" y="{y}" width="{aw}" height="28" fill="#93c5fd" stroke="#64748b"/>'
            body += f'<rect data-stage="{stage}" x="{108 + aw}" y="{y}" width="{bw}" height="28" fill="#e2e8f0" stroke="#64748b"/>'
            body += tx(116, y + 19, a_label)
            body += tx(108 + aw + 8, y + 19, b_label)
        body += '<line x1="108" y1="214" x2="308" y2="214" stroke="#64748b"/>'
        for label, x in (('0%', 108), ('50%', 208), ('100%', 308)):
            body += tx(x, 232, label, ' text-anchor="middle"')
        return (
            '<figure class="learn-chart learn-chart--wide smp-chart"><svg id="smp-composition" viewBox="0 0 640 250" role="img" '
            'aria-labelledby="composition-title composition-desc"><title id="composition-title">유형 구성비</title>'
            '<desc id="composition-desc">그림 2. 모집단은 A 80% B 20%, 표집틀과 예시 표본은 각각 50%입니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 2. 막대 길이는 그 집단 안의 비율입니다. A는 100만원/㎡, B는 200만원/㎡로 고정한 가상 단가입니다.</figcaption></figure>'
        )

    def fig3():
        body = tx(24, 22, '500회 표본평균 · 점선은 120과 150')
        labels = {('population', 5): '모집단 5건', ('population', 20): '모집단 20건', ('frame', 5): '표집틀 5건', ('frame', 20): '표집틀 20건'}
        for idx, trial in enumerate(trials):
            baseline = 137 + idx * 110
            body += tx(24, baseline - 70, labels[(trial['source'], trial['n'])])
            body += f'<line x1="80" y1="{baseline}" x2="400" y2="{baseline}" stroke="#cbd5e1"/>'
            for value in (120, 150):
                x = 80 + (value - 100) * 5.15
                body += f'<line x1="{num(x)}" y1="{baseline - 62}" x2="{num(x)}" y2="{baseline}" stroke="#64748b" stroke-dasharray="3 3"/>'
            for tick, dy in ((0, 0), (100, 25), (200, 50)):
                y = baseline - dy
                body += f'<line x1="74" y1="{y}" x2="80" y2="{y}" stroke="#64748b"/>'
                body += tx(68, y + 4, tick, ' text-anchor="end"')
            fill = '#2563eb' if trial['source'] == 'population' else '#d97706'
            for value, count in trial['frequencies'].items():
                height = float(count) * 0.25
                x = 80 + (float(value) - 100) * 5.15 - 3
                y = 75 + idx * 110 + 62 - height
                stroke = '#d97706' if idx == 0 else '#1e3a8a'
                width = 3 if idx == 0 else 1
                body += (
                    f'<rect data-source="{trial["source"]}" data-n="{trial["n"]}" x="{num(x)}" y="{num(y)}" '
                    f'width="6" height="{num(height)}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
                )
        for label, value in (('100', 100), ('120', 120), ('150', 150), ('180', 180), ('200', 200)):
            body += tx(80 + (value - 100) * 5.15, 500, label, ' text-anchor="middle"')
        body += tx(24, 522, '표본평균(만원/㎡) · 세로축은 출현 횟수')
        return (
            '<figure class="learn-chart learn-chart--wide smp-chart"><svg id="smp-repeat" viewBox="0 0 640 540" role="img" '
            'aria-labelledby="sampling-repeat-title sampling-repeat-desc"><title id="sampling-repeat-title">표본수와 표집틀별 반복표집</title>'
            '<desc id="sampling-repeat-desc">그림 3. 네 조건을 각각 500회 비복원 추출했습니다. 시드는 20261007입니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 3. 위 두 줄은 모집단 100건, 아래 두 줄은 표집틀 40건입니다. 각 회가 끝나면 같은 목록에서 다시 뽑습니다. 500회는 표본 크기 n이 아닙니다.</figcaption></figure>'
        )

    def fig4():
        body = tx(16, 24, '추출과 배정은 다른 질문입니다')
        cards = [
            ('draw', 40, '무작위 추출', '누구를 조사할까?', '모집단에서 대상을 고릅니다', '대표성과 일반화에 관련됩니다'),
            ('assign', 168, '무작위 배정', '어떤 처치를 둘까?', '참여 대상을 집단으로 나눕니다', '처치 비교에 관련됩니다'),
        ]
        for key, y, title, line2, line3, line4 in cards:
            fill = '#fff7ed' if key == 'draw' else '#eff6ff'
            stroke = '#d97706' if key == 'draw' else '#94a3b8'
            width = 3 if key == 'draw' else 1
            body += f'<rect data-design="{key}" x="16" y="{y}" width="320" height="112" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
            body += tx(28, y + 28, title)
            body += tx(28, y + 52, line2)
            body += tx(28, y + 74, line3)
            body += tx(28, y + 96, line4)
        return (
            '<figure class="learn-chart learn-chart--wide smp-chart"><svg id="smp-design" viewBox="0 0 640 300" role="img" '
            'aria-labelledby="random-selection-assignment-title random-selection-assignment-desc">'
            '<title id="random-selection-assignment-title">무작위 추출과 무작위 배정</title>'
            '<desc id="random-selection-assignment-desc">그림 4. 추출은 조사 대상을 고르고, 배정은 참여 대상의 처치를 나눕니다.</desc>'
            f'{body}</svg><figcaption class="learn-chart__caption">그림 4. 자발적으로 참여한 건물 20채를 두 안내 방식에 나누는 개념도입니다. 효과의 수치는 두지 않았습니다.</figcaption></figure>'
        )

    def sec(sid, label, title, inner):
        return (
            f'<section class="learn-chapter__step" id="{sid}" data-toc-label="{escape(label)}">'
            f'<p class="learn-chapter__label">{escape(label)}</p><h2>{escape(title)}</h2>{inner}</section>'
        )

    controls_stage = (
        '<div class="smp-controls" hidden><div class="smp-shortcuts">'
        '<button type="button" data-stage-button="population" aria-pressed="true">모집단</button>'
        '<button type="button" data-stage-button="frame">표집틀</button>'
        '<button type="button" data-stage-button="sample">예시 표본</button>'
        '</div><p role="status" id="smp-stage-status">모집단 100건을 표시합니다.</p></div>'
    )
    controls_mix = (
        '<div class="smp-controls" hidden><p><label for="smp-mix">A 비율 실험 <output id="smp-mix-label"></output></label></p>'
        '<input id="smp-mix" type="range" min="0" max="100" step="1" value="80">'
        '<div class="smp-shortcuts">'
        '<button type="button" data-mix="0">A 0%</button>'
        '<button type="button" data-mix="50">A 50%</button>'
        '<button type="button" data-mix="80" aria-pressed="true">A 80%</button>'
        '<button type="button" data-mix="100">A 100%</button>'
        '</div><p role="status" id="smp-mix-status"></p></div>'
    )
    controls_repeat = (
        '<div class="smp-controls" hidden><div class="smp-shortcuts">'
        '<button type="button" data-source-button="population" aria-pressed="true">모집단 100건</button>'
        '<button type="button" data-source-button="frame">표집틀 40건</button>'
        '<button type="button" data-n-button="5" aria-pressed="true">5건</button>'
        '<button type="button" data-n-button="20">20건</button>'
        '</div><p role="status" id="smp-repeat-status"></p></div>'
    )
    controls_design = (
        '<div class="smp-controls" hidden><div class="smp-shortcuts">'
        '<button type="button" data-design-button="draw" aria-pressed="true">무작위 추출</button>'
        '<button type="button" data-design-button="assign">무작위 배정</button>'
        '</div><p role="status" id="smp-design-status"></p></div>'
    )
    trial_rows = []
    for trial in trials:
        where = '모집단 100건' if trial['source'] == 'population' else '표집틀 40건'
        trial_rows.append(
            f'<tr><th scope="row">{where}</th><td>{trial["n"]}</td><td>500</td>'
            f'<td>{trial["mean"]:.1f}</td><td>{trial["sd"]:.2f}</td></tr>'
        )
    theory_text = ' · '.join(
        f'{"모집단" if source == "population" else "표집틀"} n={n} 약 {sd:.2f}'
        for (source, n), sd in zip([(t['source'], t['n']) for t in trials], expected_sd)
    )

    parts = [
        sec('quick-start', '서두 · 학습목표', '거래자료 1만 건은 100건보다 언제나 믿을 만할까요?',
            '<p>어느 지역의 부동산 거래자료를 분석한다고 가정하겠습니다. 한 자료는 100건이고 다른 자료는 1만 건입니다. 건수만으로는 어느 쪽이 더 믿을 만한지 답하기 어렵습니다. 100건이 여러 유형을 고르게 담았을 수 있고, 1만 건이 거래가 활발한 일부 유형에 몰려 있을 수도 있습니다.</p>'
            '<p>그 지역에 있는 부동산 전체와 실제로 거래된 부동산은 다른 집단입니다. 거래자료가 많다고 해서 거래되지 않은 부동산의 특성까지 알게 되는 것은 아닙니다. <strong>자료가 얼마나 많은지와 함께, 어떤 전체를 어떤 과정으로 모았는지</strong> 확인합니다.</p>'
            '<ul class="learn-objectives"><li>모집단·표집틀·표본·최종 분석자료를 구별합니다.</li><li>모수와 통계량의 차이를 이해합니다.</li><li>확률표집과 비확률표집, 단순무작위·층화·군집·계통표집을 구별합니다.</li><li>표본수와 대표성, 표집 변동과 편향을 구별합니다.</li><li>무작위 추출과 무작위 배정의 목적을 이해합니다.</li><li>공개 실거래 자료가 어느 범위의 시장을 설명하는지 판단합니다.</li></ul>'),
        sec('population-definition', '모집단', '알고 싶은 대상 전체를 먼저 정의합니다',
            '<p><strong>모집단</strong>은 분석을 통해 알고 싶은 대상의 전체입니다. 2025년 청주시에서 체결된 아파트 매매의 평균 거래단가를 묻는 질문과, 2025년 말 청주시에 있는 모든 아파트의 가격 수준을 묻는 질문은 지역이 같아도 모집단이 다릅니다. 앞의 대상은 그 기간의 거래이고, 뒤의 대상은 그 시점의 아파트입니다.</p>'
            '<p>같은 아파트가 두 번 거래되면 거래 모집단에는 두 기록이 남을 수 있습니다. 거래되지 않은 아파트는 거래 목록에 없고, 아파트 전체에는 들어갑니다. 모집단을 정할 때는 지역, 기간 또는 기준시점, 대상 유형, 관측 단위, 포함·제외 조건을 확인합니다.</p>'
            '<p><strong>첫 질문은 표본이 몇 건인가가 아니라, 어떤 전체를 알고 싶은가입니다.</strong></p>'),
        sec('population-frame', '모집단·표집틀·표본', '전체에 속한 대상이 모두 수집 목록에 들어오지는 않습니다',
            '<p><strong>표집틀</strong>은 표본을 고를 때 쓸 수 있는 목록이나 접근 가능한 범위입니다. <strong>표본</strong>은 그 절차로 실제로 고른 대상입니다. 이번 가상 자료의 모집단은 거래 100건이고 A 80건, B 20건입니다. 접근 가능한 목록은 40건이며 A 20건, B 20건입니다. 그림에 표시하는 예시 표본은 20건이며 A 10건, B 10건입니다.</p>'
            + controls_stage + fig1() +
            '<p>모집단에서 A는 80%이고 표집틀에서는 A와 B가 각각 50%입니다. 목록에서 빠진 A 60건은 그 목록 안에서 아무리 무작위로 뽑혀도 선택되지 않습니다. 이 문제를 <strong>포괄 부족</strong>이라고 합니다. 예시 표본의 10대10은 교육용으로 고정한 결과입니다. 20건을 무작위로 뽑을 때마다 반드시 10건씩 나온다는 뜻은 아닙니다.</p>'
            '<details class="learn-more"><summary>표본과 최종 분석자료는 같을까요?</summary><div class="learn-more__body"><p>20건을 조사해도 그중 5건의 필요한 값이 없으면, 그 분석의 계산에는 15건이 쓰일 수 있습니다. 고른 건수, 자료를 확보한 건수, 결측이나 제외 뒤의 유효 건수는 서로 다를 수 있습니다.</p></div></details>'),
        sec('census', '전수조사와 표본조사', '전부 조사했다는 말에도 대상의 범위가 필요합니다',
            '<p><strong>전수조사</strong>는 정의한 대상 전체를 조사하는 것이고, <strong>표본조사</strong>는 그중 일부를 조사하는 것입니다. 목록 40건을 모두 조사하면 그 표집틀에 대한 전수조사입니다. 모집단 100건 중 60건이 목록에 없으므로, 모집단 100건에 대한 전수조사는 아닙니다.</p>'
            '<p>공개 거래 기록을 모두 분석해도, 그 지역의 모든 부동산을 조사한 것은 아닙니다. 알고 싶은 대상이 거래인지 존재하는 부동산인지에 따라 목표가 다릅니다. 전수조사에서도 면적의 종류나 금액 단위를 잘못 기록하면 통계값에 오류가 생깁니다.</p>'),
        sec('parameters', '모수와 통계량', '전체의 평균과 일부의 평균은 구별합니다',
            '<p>모집단의 특성을 나타내는 수를 <strong>모수</strong>, 표본에서 계산한 값을 <strong>통계량</strong>이라고 합니다. 모집단 평균은 μ = (1/N) Σ Yᵢ, 표본평균은 Ȳ = (1/n) Σ Yᵢ입니다. N은 모집단의 크기이고 n은 표본의 크기입니다.</p>'
            '<p>실제 분석에서는 모집단 전체를 몰라 표본으로 모수를 추정하는 경우가 많습니다. 이번 예제는 학습을 위해 모집단의 값을 정해 두었으므로 모집단 평균을 직접 계산할 수 있습니다.</p>'),
        sec('composition', '구성비와 평균', '표본평균이 맞아도 모집단 평균과 다를 수 있습니다',
            '<p>A 유형은 모두 100만원/㎡, B 유형은 모두 200만원/㎡로 정했습니다. 실제 가격이 이렇게 일정하다는 뜻이 아니라, 구성비가 평균에 미치는 영향을 보여 주는 가정입니다.</p>'
            '<p>모집단 평균은 (80×100 + 20×200) / 100 = <strong>120만원/㎡</strong>입니다. 표집틀 평균은 (20×100 + 20×200) / 40 = <strong>150만원/㎡</strong>입니다. 예시 표본도 (10×100 + 10×200) / 20 = <strong>150만원/㎡</strong>입니다.</p>'
            + fig2() +
            '<div class="learn-data learn-data--full smp-table"><table><caption>같은 단가에서 구성비만 바뀌어도 평균이 달라집니다</caption><thead><tr><th scope="col">대상</th><th scope="col">A</th><th scope="col">B</th><th scope="col">평균단가</th></tr></thead><tbody>'
            '<tr><th scope="row">모집단 100건</th><td>80%</td><td>20%</td><td>120만원/㎡</td></tr>'
            '<tr><th scope="row">표집틀 40건</th><td>50%</td><td>50%</td><td>150만원/㎡</td></tr>'
            '<tr><th scope="row">예시 표본 20건</th><td>50%</td><td>50%</td><td>150만원/㎡</td></tr>'
            '</tbody></table></div>'
            '<p>150은 그 20건의 평균으로 맞습니다. 표집틀의 구성과도 맞습니다. 원래 모집단 평균은 120입니다. 단가가 바뀌어서가 아니라 <strong>두 유형의 비율이 달라져서</strong> 생긴 차이입니다.</p>'),
        sec('weighting', '구성비를 알 때', '가중치는 확인된 구성 차이를 조정합니다',
            '<p>모집단 구성비 A 80%, B 20%를 알고 각 유형의 평균도 맞다고 가정하면 0.8×100 + 0.2×200 = 120입니다. 사후층화 가중의 이해를 위한 예제입니다. 모집단 구성비를 알고, 각 유형 안에서 모은 자료가 그 유형의 가격을 나타내야 합니다. A 안에서 저가 거래만 모였다면 전체 비율을 맞춰도 그 문제가 사라지지는 않습니다.</p>'
            '<p><strong>가중치는 모든 수집 편향을 없애는 방법이 아닙니다.</strong> 선택확률, 무응답, 모집단 구성에 따라 가중 방법이 달라질 수 있습니다.</p>'
            + controls_mix +
            '<p>슬라이더는 A 비율을 바꿉니다. B 비율은 100%에서 A 비율을 뺀 값이고, 평균은 100×A비율 + 200×B비율입니다. A 80%는 120, A 50%는 150, A 100%는 100, A 0%는 200입니다.</p>'),
        sec('sampling-methods', '자료 수집 방법', '확률표집과 비확률표집을 구별합니다',
            '<p><strong>확률표집</strong>은 대상이 선택될 확률을 설계에 따라 아는 방식입니다. 모든 대상의 확률이 같아야 하는 것은 아닙니다. 목표 모집단의 대상이 포함될 기회를 갖고, 필요할 때 그 확률을 추정에 반영합니다.</p>'
            '<p><strong>비확률표집</strong>은 미리 정한 확률 설계가 아니라 접근성, 판단, 자발적 참여 등으로 모으는 방식입니다. 시장을 탐색하거나 접근이 어려운 대상을 살펴볼 때 쓸 수 있습니다. 그 결과를 모집단 전체로 넓힐 때는 추가 확인이 필요합니다.</p>'),
        sec('methods-table', '대표적인 표집 방법', '자료를 어떻게 묶고 고르는지를 확인합니다',
            '<div class="learn-data learn-data--full smp-table"><table><caption>표집 방법과 확인할 점</caption><thead><tr><th scope="col">방법</th><th scope="col">수집 방식</th><th scope="col">확인할 점</th></tr></thead><tbody>'
            '<tr><th scope="row">단순무작위</th><td>정해진 크기의 가능한 표본에 같은 추출확률</td><td>표집틀에 누가 들어 있는가</td></tr>'
            '<tr><th scope="row">층화</th><td>층을 나누고 각 층에서 추출</td><td>층별 표본수와 가중치</td></tr>'
            '<tr><th scope="row">군집</th><td>구역·단지 같은 묶음을 먼저 추출</td><td>같은 군집 안의 유사성</td></tr>'
            '<tr><th scope="row">계통</th><td>무작위 시작점 뒤 일정 간격</td><td>목록의 정렬과 주기</td></tr>'
            '<tr><th scope="row">편의·자발적</th><td>접근하기 쉽거나 스스로 참여한 대상</td><td>선택되기 어려운 대상의 특성</td></tr>'
            '</tbody></table></div>'
            '<p>목록에 없는 거래는 단순무작위 추출로도 뽑히지 않습니다. 층별 표본 비율이 모집단 구성과 다르면 전체 평균에 가중치가 필요할 수 있습니다. 최근 거래 순으로 정렬된 조회 결과의 첫 100건은 무작위 표본이 아닙니다. <strong>방법의 이름보다 실제로 어떤 규칙으로 골라졌는지</strong>를 확인합니다.</p>'),
        sec('stratified-cluster', '층화표집과 군집표집', '둘 다 집단으로 나누지만 선택 절차가 다릅니다',
            '<p>층화표집은 아파트, 단독주택, 토지처럼 층을 만든 뒤 각 층에서 표본을 뽑습니다. 군집표집은 단지처럼 묶음 자체를 먼저 고르고, 선택된 단지 안의 거래를 조사합니다. 같은 단지의 거래는 조건을 공유할 수 있으므로, 거래 100건을 서로 독립적인 100건과 같은 정보량으로 보지 않습니다.</p>'
            '<p><strong>층화표집은 각 층을 어떻게 대표할지의 문제이고, 군집표집은 어떤 묶음을 조사할지의 문제입니다.</strong></p>'),
        sec('variability', '표집 변동', '같은 모집단에서 다시 뽑으면 평균도 달라질 수 있습니다',
            '<p>모집단 100건에서 5건을 무작위로 뽑는다고 가정하겠습니다. A 4건과 B 1건이면 평균은 (4×100 + 1×200) / 5 = 120입니다. A 3건과 B 2건이면 (3×100 + 2×200) / 5 = 140입니다. 같은 방법인데 표본평균이 달라집니다. 이 현상이 <strong>표집 변동</strong>입니다. 정상적인 무작위 표집에서도 나타나며, 적절한 조건에서는 표본수가 늘면 표본평균의 변동이 줄어드는 경향이 있습니다.</p>'),
        sec('sample-size', '표본수와 수집 범위', '변동은 줄어도 목록 밖의 대상은 들어오지 않습니다',
            '<p>모집단 100건과 표집틀 40건에서, 5건과 20건을 각각 비복원으로 뽑고 500회 반복합니다. 한 번이 끝나면 같은 모집단 또는 같은 표집틀에서 다시 시작합니다. 난수 시드는 20261007입니다.</p>'
            + controls_repeat + fig3() +
            '<div class="learn-data learn-data--full smp-table"><table><caption>시드 20261007의 500회 결과</caption><thead><tr><th scope="col">추출 대상</th><th scope="col">n</th><th scope="col">반복</th><th scope="col">반복평균</th><th scope="col">반복 표준편차</th></tr></thead><tbody>'
            + ''.join(trial_rows) + '</tbody></table></div>'
            '<p>모집단에서 뽑은 표본평균은 120 주변에 모입니다. 표집틀에서 뽑은 표본평균은 150 주변에 모입니다. 목록의 표본수를 5건에서 20건으로 늘려도 중심이 120으로 이동하지는 않고, 150 주변에 더 모일 수 있습니다. <strong>표본수가 커지면 그 표집틀의 특성을 더 정밀하게 재지만, 빠진 대상을 자동으로 되돌리지는 않습니다.</strong></p>'
            '<p>표집틀 40건을 모두 조사하면 목록 평균은 150이고 그 목록 안에서의 표집 변동은 없습니다. 모집단 평균 120과의 차이 30은 목록 밖 A 60건과 함께 남습니다.</p>'
            f'<details class="learn-more"><summary>반복표집과 이론 표준편차</summary><div class="learn-more__body"><p>각 회는 중복 없이 뽑고, 다음 회는 원래 목록으로 돌아갑니다. 반복이 500회로 유한하므로 반복평균이 정확히 120 또는 150이 되지는 않습니다. <a href="../sampling-example.json">가상 원자료와 반복표집 결과(JSON)</a>에 시드 20261007의 값을 두었습니다.</p>'
            f'<p>유한모집단의 비복원 표본평균은 Var(Ȳ)=σ²/n×(N−n)/(N−1)로 분산을 계산할 수 있습니다. 모집단 단가분산을 N으로 나눈 값은 1600이고 표집틀은 2500입니다. 이론 표준편차는 {theory_text}입니다. 위 표의 반복 표준편차는 500회 모의실험의 값이며 이론값과 같을 필요는 없습니다.</p></div></details>'),
        sec('bias', '편향', '우연한 오차와 체계적으로 어긋나는 중심을 구별합니다',
            '<p><strong>편향</strong>은 같은 추정 절차를 반복했을 때 추정량의 기대값이 목표값에서 얼마나 벗어나는지를 나타냅니다. Bias(Ȳ) = E(Ȳ) − μ입니다.</p>'
            '<p>표집틀 40건에서 단순무작위로 뽑으면 표본평균의 기대값은 목록 평균 150입니다. 목표를 모집단 평균 120으로 두면 편향은 150−120 = <strong>30</strong>입니다. 모집단 100건에서 직접 단순무작위로 뽑으면 기대값은 120이고, 이 표본평균은 그 모집단 평균에 대해 불편추정량입니다. 한 번의 평균이 140이라고 해서 그 절차에 편향이 있다고 판단하지는 않습니다.</p>'
            '<p><strong>표집 변동은 뽑을 때마다 달라지는 현상이고, 편향은 반복 추정의 중심이 목표에서 벗어나는 현상입니다.</strong></p>'),
        sec('mse', '표본수와 평균제곱오차', '변동이 작아도 목표값에서 멀리 있을 수 있습니다',
            '<p>평균제곱오차는 MSE = Var + Bias²로 나눌 수 있습니다. 표집틀 안에서 표본수를 늘리면 표본평균의 분산은 줄어들 수 있지만, 모집단 평균에 대한 편향 30은 남습니다. 그 제곱은 900입니다. 목록과 모집단의 구성 차이가 남는 한 이 편향의 영향은 표본수만으로 사라지지 않습니다.</p>'
            '<p>24장의 예측모형 편향과 이번 장의 표집틀 편향은 생기는 원인이 다를 수 있습니다. 정밀도와 대표성은 함께 봅니다.</p>'),
        sec('collection-errors', '수집 과정의 문제', '누가 빠졌고 무엇이 잘못 기록되었는지 확인합니다',
            '<ul><li><strong>포괄 부족:</strong> 모집단의 일부가 수집 목록에 없는 경우입니다.</li>'
            '<li><strong>선택편향:</strong> 자료에 포함되는 과정이 가격이나 위치 같은 특성과 관련되어 결과가 한쪽으로 기울어지는 경우입니다.</li>'
            '<li><strong>무응답 편향:</strong> 응답하지 않은 대상의 특성이 응답자와 다른데 응답자만으로 전체를 설명하는 경우입니다.</li>'
            '<li><strong>측정·기록 오류:</strong> 호가와 계약가격, 전용면적과 연면적, 면적 단위, 거래 시점과 공개 시점, 같은 거래의 중복 수집을 혼동하는 경우입니다.</li></ul>'
            '<p>측정·기록 오류는 전수조사에서도 생깁니다. 한 방향으로만 어긋나지는 않지만, 특정 유형에 몰리면 체계적인 왜곡이 될 수 있습니다.</p>'),
        sec('filtering', '필터와 모집단', '대상을 정하는 필터와 일부를 빼 버리는 처리를 구별합니다',
            '<p>청주시 아파트 거래를 알고 싶어서 아파트 거래를 고르는 것은 모집단을 정의하는 과정입니다. 그 사실만으로 선택편향이 생겼다고 보지 않습니다. 그 결과를 모든 부동산에 넓혀 말할 때 범위가 어긋납니다.</p>'
            '<p>오류 거래를 분석에서 빼는 경우와, 가격이 높다는 이유만으로 고가 거래를 빼는 경우는 다릅니다. 뒤의 경우 남은 자료의 평균은 원래 거래 전체의 평균과 달라질 수 있습니다. 확인할 질문은 <strong>이 필터가 알고 싶은 대상을 정한 것인지, 알고 싶던 대상의 일부를 결과적으로 뺀 것인지</strong>입니다.</p>'),
        sec('stock', '거래와 재고', '거래가 활발한 자산의 특성이 더 많이 나타날 수 있습니다',
            '<p>아파트 1,000세대 가운데 일정 기간에 100건이 거래되었다면, 그 100건의 평균 거래단가를 계산할 수 있습니다. 그 값이 1,000세대 전체의 현재 평균 가격과 같다고 단정하지는 않습니다. 거래가 소형 면적에 몰려 있거나, 같은 세대가 반복 거래되면 거래 건수 기준 통계에서 그 비중이 커집니다.</p>'
            '<p><strong>거래 기준 통계</strong>는 그 기간에 일어난 거래의 가격과 특성을 요약합니다. <strong>보유 재고 기준 통계</strong>는 특정 시점에 존재하는 부동산 전체를 알고자 합니다. 어느 시장을 설명하려는가에 따라 거래자료만으로 충분할 수도 있고 추가 정보가 필요할 수도 있습니다.</p>'),
        sec('observational', '관측자료와 실험자료', '두 집단의 차이가 곧 원인은 아닙니다',
            '<p><strong>관측연구</strong>는 이미 있는 조건과 결과를 관찰합니다. 역에서 가까운 건물의 거래단가가 더 높더라도, 건축연도, 상업시설, 용도지역, 규모가 함께 다를 수 있습니다. 원인으로 보는 변수와 결과에 모두 관련되어 해석을 어렵게 하는 요인을 <strong>교란요인</strong>이라고 합니다. 실험에서는 연구자가 처치를 배정하고 결과를 비교할 수 있지만, 실험이라는 이름만으로 모든 문제가 해결되지는 않습니다.</p>'),
        sec('assignment', '무작위 추출과 무작위 배정', '둘 다 무작위지만 해결하려는 문제가 다릅니다',
            '<p><strong>무작위 추출</strong>은 누구를 조사할지의 문제입니다. <strong>무작위 배정</strong>은 조사하거나 참여한 대상에게 어떤 처치를 적용할지의 문제입니다.</p>'
            + controls_design + fig4() +
            '<p>자발적으로 참여한 건물 20채를 절전 안내 A와 B에 무작위로 나누면, 참여한 건물 안에서 두 방식을 비교하는 데 도움이 됩니다. 그 20채가 전체 건물에서 무작위로 뽑힌 것은 아닐 수 있으므로, 모든 건물에 같은 효과가 있다고 보장하지는 않습니다. 반대로 표본을 무작위로 뽑았더라도 처치를 무작위로 나누지 않은 관측자료에서는 인과 해석에 추가 가정이 필요합니다.</p>'
            '<details class="learn-more"><summary>무작위 배정하면 교란요인이 사라질까요?</summary><div class="learn-more__body"><p>무작위 배정은 처치 전 특성을 확률적으로 균형 있게 만드는 데 도움이 됩니다. 작은 표본에서는 집단 차이가 우연히 남을 수 있습니다. 처치 도중 이탈하거나 집단끼리 영향을 주고받으면 별도 문제가 생깁니다.</p></div></details>'),
        sec('causal', '관측연구와 인과관계', '추가 설계와 가정이 필요합니다',
            '<p>관측자료로 인과효과를 연구하지 못한다는 뜻은 아닙니다. 자연실험, 차이의 차이, 회귀불연속 같은 설계가 쓰입니다. 그런 방법에는 상황에 맞는 가정이 필요합니다. 도시철도 개통 뒤 가격이 올랐다고 해서 상승분 전체가 도시철도의 효과는 아닙니다. 같은 기간의 금리, 주변 개발, 경기 변화가 함께 영향을 줄 수 있습니다.</p>'
            '<p>회귀식에 설명변수를 많이 넣었다는 사실만으로 교란이 모두 해결된 것도 아닙니다. <strong>관측된 관계와 원인으로 생긴 효과는 구별합니다.</strong></p>'),
        sec('prediction', '대표성과 예측', '어떤 자료에 적용할 것인지도 먼저 정합니다',
            '<p>대도시 아파트 거래만으로 학습한 모형을 농촌 단독주택에 적용하면, 학습자료와 적용 대상이 크게 다를 수 있습니다. 학습 건수가 많아도 그 적용이 보장되지는 않습니다. 같은 지역에서도 시점, 단지, 거래 구성이 바뀔 수 있습니다.</p>'
            '<p>검증 전에 적용 대상을 정합니다. 기존 지역의 미래 거래인지, 처음 보는 지역인지, 기존 단지의 새 거래인지, 처음 보는 단지인지를 구분하면 시간 기준 검증이나 지역·단지 단위 검증을 검토할 수 있습니다. 대표성이 부족한 학습자료에서는 계산이 정교해도 적용 성능이 나쁠 수 있습니다.</p>'),
        sec('practice', '확인 문제', '어느 전체에 대해 말할 수 있는지 살펴보세요',
            '<ol class="learn-exercises">'
            '<li>표집틀 40건을 모두 조사했습니다. 모집단 100건의 평균을 정확하게 알게 된 것일까요?<details><summary>답과 해설</summary><p>아닙니다. 표집틀의 평균 150은 계산할 수 있습니다. 모집단에는 목록에 없는 A 60건이 있고 평균은 120입니다. 표집틀의 전수조사와 모집단의 전수조사는 다릅니다.</p></details></li>'
            '<li>같은 모집단에서 무작위로 두 번 뽑았더니 평균이 달랐습니다. 수집 방법에 편향이 있다는 증거일까요?<details><summary>답과 해설</summary><p>그 사실만으로는 알 수 없습니다. 정상적인 무작위 표집에서도 표집 변동이 생깁니다. 편향은 절차를 반복했을 때 목표값에서 체계적으로 벗어나는 성질입니다.</p></details></li>'
            '<li>아파트 거래의 특징을 알아보려고 아파트 거래만 골랐습니다. 반드시 선택편향이 발생했다고 볼 수 있을까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 알고 싶은 대상이 아파트 거래라면 분석 범위를 정한 것입니다. 그 결과를 토지나 단독주택까지 넓히려면 별도의 근거가 필요합니다.</p></details></li>'
            '<li>자발적으로 참여한 건물에 실험 처치를 무작위로 배정했습니다. 전체 건물에도 같은 효과가 있다고 볼 수 있을까요?<details><summary>답과 해설</summary><p>자동으로 그렇게 볼 수는 없습니다. 무작위 배정은 참여한 대상 사이의 처치 비교를 돕습니다. 참여 건물이 전체 건물을 나타내는지는 다른 문제입니다.</p></details></li>'
            '<li>표본수를 늘리면 수집 단계의 포괄 부족도 해결될까요?<details><summary>답과 해설</summary><p>아닙니다. 같은 표집틀에서의 무작위 변동은 줄어들 수 있습니다. 목록 밖 대상은 여전히 표본에 들어오지 않습니다.</p></details></li>'
            '</ol>'),
        sec('macro', 'CH2 Macro에서 읽기', '공개된 거래의 전체와 존재하는 부동산 전체는 다릅니다',
            '<p>CH2 Macro는 공개 실거래 자료로 지역과 유형별 거래를 살펴봅니다. 아래 화면은 토지 단가 분포의 과거 캡처입니다. 용도 자녹, 지목 답, 표본 범위는 필터 구간 전체, 건수는 394건이고 이상치는 제외하지 않은 상태입니다.</p>'
            '<figure class="learn-capture"><a href="../assets/captures/land-filtered-price-distribution.png" target="_blank" rel="noopener"><img src="../assets/captures/land-filtered-price-distribution.png" width="1227" height="562" loading="lazy" alt="CH2 Macro 토지 단가 분포. 용도 자녹·지목 답, 표본 범위 필터 구간 전체, 표본 수 394건, 이상치 제외 안 함. 가로축은 단가 구간, 세로축은 빈도이며 낮은 단가 구간에 거래가 많이 모여 있습니다."/></a>'
            '<figcaption class="learn-capture__caption">394건은 캡처 당시 선택 조건의 거래 수입니다. 이번 장의 가상 모집단 100건이 아니며, 그 지역에 있는 토지 전체의 수도 아닙니다.</figcaption></figure>'
            '<ol class="learn-screen-reading">'
            '<li><strong>거래 모집단을 정합니다.</strong> 최근 몇 년의 아파트 매매를 분석한 결과는 그 조건의 거래에 대한 통계입니다. 같은 지역에 존재하는 아파트 전체의 현재 가격이라고 바로 읽지 않습니다.</li>'
            '<li><strong>원천 기록과 분석에 쓴 기록을 구별합니다.</strong> 정제, 중복, 거래 유형, 결측, 이상치 제외에 따라 유효 건수가 달라질 수 있습니다. 캡처의 394건은 그때의 필터 구간 건수입니다.</li>'
            '<li><strong>용도지역·지목 통계는 그 조건의 요약입니다.</strong> 다른 용도지역과 지목의 거래를 대표하지는 않습니다.</li>'
            '<li><strong>기간을 늘리면 구성도 바뀔 수 있습니다.</strong> 토지 기본통계의 롤링 구간은 계약일 기준 3년·5년·7년입니다. 건수가 늘어도 그 기간의 시장 구성이 같다는 뜻은 아닙니다.</li>'
            '<li><strong>같은 단지나 필지의 거래는 관련될 수 있습니다.</strong> 1,000건 중 800건이 한 단지에 있으면 그 단지의 특성이 결과를 크게 좌우할 수 있습니다. 거래 건수와 서로 다른 부동산의 수를 구별합니다.</li>'
            '<li><strong>거래 DB와 대장 DB는 대상과 기준시점이 다릅니다.</strong> 어떤 기준으로 연결했는지, 속성의 기준일이 언제인지를 확인합니다.</li>'
            '<li><strong>설명형과 예측형 모두 적용 범위를 확인합니다.</strong> 높은 R²나 낮은 MAE만으로 대표성이나 다른 지역·시점으로의 적용이 보장되지는 않습니다.</li>'
            '</ol>'
            '<p>확인한 토지 기본통계에서 용도×지목 매트릭스는 유효하고 해제되지 않았으며 단가가 있는 거래를 롤링 기간에서 모아, 그 단가의 산술평균을 계산합니다. 연도별 표의 단가는 거래금액 합을 면적 합으로 나눈 값이고, 그 집계는 해제 거래를 매트릭스와 같은 조건으로 빼지 않습니다. 두 칸의 건수와 단가를 같은 계산으로 읽지 않습니다. 이 구분은 토지 기본통계에서 확인한 경로이며, 모든 화면이 같다고 확대하지 않습니다.</p>'
            '<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p>'),
        sec('recap', '결론 · 학습 요약', '어떤 전체를 대표하는지 확인하는 일이 먼저입니다',
            '<ul class="learn-recap-list">'
            '<li><strong>모집단:</strong> 알고 싶은 대상 전체입니다.</li>'
            '<li><strong>표집틀:</strong> 표본을 고를 수 있는 목록 또는 접근 범위입니다.</li>'
            '<li><strong>표본:</strong> 수집 절차로 고른 대상입니다.</li>'
            '<li><strong>최종 분석자료:</strong> 결측과 제외를 반영해 계산에 쓴 자료입니다.</li>'
            '<li><strong>모수와 통계량:</strong> 전체의 특성과 표본에서 계산한 값입니다.</li>'
            '<li><strong>포괄 부족:</strong> 모집단의 일부가 표집틀에 없는 문제입니다.</li>'
            '<li><strong>확률표집:</strong> 선택확률을 알고 설계에 반영하는 방식입니다.</li>'
            '<li><strong>표집 변동:</strong> 같은 절차를 반복해도 통계량이 달라지는 현상입니다.</li>'
            '<li><strong>편향:</strong> 반복 추정의 중심이 목표값에서 벗어나는 현상입니다.</li>'
            '<li><strong>표본수:</strong> 무작위 변동을 줄일 수 있지만 대표성을 대신하지는 않습니다.</li>'
            '<li><strong>무작위 추출과 배정:</strong> 누구를 조사할지와, 참여 대상에 어떤 처치를 둘지입니다.</li>'
            '</ul>'
            '<p>다음 <a href="/learn/stats/graphs/">3장 「그래프로 보는 데이터와 분포」</a>에서는 히스토그램, 막대그래프, 산점도로 분포의 모양을 읽습니다. 그래프를 볼 때도 어떤 자료를 그렸는지를 먼저 확인합니다.</p>'
            '<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul>'
            '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/1-1-definitions-of-statistics-probability-and-key-terms">OpenStax, Introductory Statistics 2e §1.1</a> — 모집단·표본·모수·통계량.</li>'
            '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/1-2-data-sampling-and-variation-in-data-and-sampling">같은 교재 §1.2</a> — 표집 방법과 자료의 변동.</li>'
            '<li><a href="https://openstax.org/books/introductory-statistics-2e/pages/1-4-experimental-design-and-ethics">같은 교재 §1.4</a> — 관측연구와 실험, 무작위 배정.</li>'
            '</ul><p class="learn-source-note">참고자료 확인일: 2026-10-07. A 80건·B 20건과 반복표집은 난수 시드 20261007의 가상 자료입니다. 실제 부동산 시장의 분포나 수집 편향을 측정한 결과가 아닙니다.</p></div></details>'),
    ]

    html = f'''<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>02. 모집단과 표본, 자료 수집과 편향 | 통계학 &amp; 데이터 분석</title>
    <meta name="description" content="모집단·표집틀·표본, 표집 변동과 편향, 무작위 추출과 배정을 구별하고 공개 거래자료의 해석 범위를 살펴봅니다." />
    <link rel="canonical" href="https://ch2data.com/learn/stats/population-and-sampling/" />
    <script src="/learn/stats/learn-stats-theme.js?v=20261023-1"></script>
    <link rel="stylesheet" href="/style.css" />
    <link rel="stylesheet" href="/learn/stats/learn-stats.css?v=20261023-1" />
    <link rel="stylesheet" href="/learn/stats/learn-reader.css?v=20261026-toc" />
    <link rel="stylesheet" href="/learn/stats/population-and-sampling/chapter.css?v=20261026-3" />
  </head>
  <body>
    <div class="page">
      <header class="hero hero--document">
        <p class="learn-breadcrumb">
          <a href="https://ch2data.com/">CH2 DATA</a> ·
          <a href="/learn/stats/">통계학 &amp; 데이터 분석</a>
        </p>
        <p class="hero__eyebrow">I. 데이터와 기술통계</p>
        <h1 class="hero__title">02. 모집단과 표본, 자료 수집과 편향</h1>
        <p class="learn-chapter-relevance">Macro 활용도 <span class="learn-relevance" aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span></span></p>
        <p class="learn-relevance-guide">Macro 활용도: ★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화<br>별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.</p>
      </header>
      <article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="모집단과 표본, 자료 수집과 편향">
        {''.join(parts)}
      </article>
      <nav class="learn-chapter-nav" aria-label="장 이동">
        <a href="/learn/stats/data-and-variables/">← 01. 데이터와 변수</a>
        <a href="/learn/stats/graphs/">03. 그래프로 보는 데이터와 분포 →</a>
      </nav>
      <footer class="footer">
        <nav class="footer__links">
          <a href="https://ch2data.com/">홈</a>
          <a href="/learn/stats/">통계학 &amp; 데이터 분석</a>
        </nav>
        <p>© CH2 DATA</p>
      </footer>
    </div>
    <script src="/learn/stats/learn-stats-toc.js?v=20261026-3" defer></script>
    <script type="application/json" id="smp-data">{json.dumps(page_data, ensure_ascii=False)}</script>
    <script type="module" src="/learn/stats/population-and-sampling/experiment.js?v=20261026-3"></script>
  </body>
</html>
'''
    charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', html, re.S)]
    assert len(charts) == 4
    composition = next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('composition'))
    labels = [node.text for node in composition.findall('text')]
    assert 'A 80%' in labels and 'B 20%' in labels and labels.count('B 50%') == 2
    repeat = next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('sampling-repeat'))
    bars = [node for node in repeat.findall('rect')]
    expected = []
    for idx, trial in enumerate(trials):
        for value, count in trial['frequencies'].items():
            height = float(count) * 0.25
            expected.append((80 + (float(value) - 100) * 5.15 - 3, 75 + idx * 110 + 62 - height, height))
    assert len(bars) == len(expected)
    for bar, (x, y, height) in zip(bars, expected):
        assert abs(float(bar.attrib['x']) - x) < 1e-8
        assert abs(float(bar.attrib['y']) - y) < 1e-8
        assert abs(float(bar.attrib['height']) - height) < 1e-8
    assert html.count('<summary>답과 해설</summary>') == 5
    assert ' open' not in html.split('<ol class="learn-exercises">')[1].split('</ol>')[0]
    assert '[그림 ' not in html and '★☆☆ 심화' in html and '3단계, 핵심' in html
    assert 'land-filtered-price-distribution.png' in html
    assert '/learn/stats/data-and-variables/' in html and '/learn/stats/graphs/' in html
    page = ROOT / 'population-and-sampling' / 'index.html'
    page.write_text(html, encoding='utf-8')
    promote(ROOT / 'course.json')
    promote(ROOT / 'learn-stats-toc.js')
    listing = ROOT / 'index.html'
    listing_text = listing.read_text(encoding='utf-8')
    old_link = 'data-macro-relevance="2"><a href="/learn/stats/population-and-sampling/">02. 모집단과 표본, 자료 수집과 편향 <span class="learn-relevance" aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>'
    new_link = old_link.replace('data-macro-relevance="2"', 'data-macro-relevance="3"').replace('2단계, 권장', '3단계, 핵심').replace('★★☆', '★★★')
    if old_link not in listing_text and new_link not in listing_text:
        raise SystemExit('course listing relevance missing')
    if old_link in listing_text:
        listing.write_text(listing_text.replace(old_link, new_link, 1), encoding='utf-8')
    print('chapter 2 rebuilt')
    for trial in trials:
        print(trial['source'], trial['n'], round(trial['mean'], 2), round(trial['sd'], 2))


if __name__ == '__main__':
    build()
