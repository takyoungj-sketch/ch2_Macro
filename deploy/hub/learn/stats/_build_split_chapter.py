"""Chapter 23: splitting, selection and leakage."""
from pathlib import Path
from statistics import mean,median,pstdev
from html import escape
import json,re
ROOT=Path(__file__).resolve().parent

def build():
 train=[10,10,10,10,20,60];valid=[11,12,13];test=[9,11,16]
 candidates={name:dict(value=fn(train),validation_MAE=mean(abs(y-fn(train)) for y in valid)) for name,fn in [('mean',mean),('median',median)]}
 selected=min(candidates,key=lambda k:candidates[k]['validation_MAE']);final=median(train+valid);test_mae=mean(abs(y-final) for y in test)
 scale_train=[40,60,80];held=140;mu=mean(scale_train);sd=pstdev(scale_train);all_mu=mean(scale_train+[held]);all_sd=pstdev(scale_train+[held])
 d=dict(description='별도 가상 자료. 공통 거래 자료나 운영 성능 추정이 아님.',train=train,validation=valid,test=test,candidates=candidates,selected=selected,refit_value=final,test_MAE=test_mae,scaling=dict(train=scale_train,held_out=held,train_mean=mu,train_sd=sd,train_z=(held-mu)/sd,all_mean=all_mu,all_sd=all_sd,leaked_z=(held-all_mu)/all_sd))
 (ROOT/'split-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def box(x,y,w,h,c):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{c}"/>'
 def line(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap,h=410):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'자료의 역할: 학습 → 선택 → 마지막 평가')
 for y,title,desc in [(70,'학습','전처리와 계수를 학습'),(165,'검증','후보·설정·임계값을 선택'),(260,'시험','선택한 절차의 성능을 마지막에 평가')]:b+=box(90,y,455,65,'#eaf2ff')+tx(112,y+25,title)+tx(112,y+49,desc)
 b+=tx(305,154,'↓')+tx(305,249,'↓')+tx(24,380,'시험 성적에 맞춰 다시 선택하면 독립 평가의 역할을 잃습니다')
 g1=fig('roles','세 자료의 역할',b,'그림 1. 역할을 구분한 개념도입니다. 세 개의 고정 파일만이 유일한 구현은 아니며 교차검증으로 학습·검증 역할을 반복할 수 있습니다.')
 b=tx(24,28,'활용 상황에 맞춘 분할: 두 가지 별도 예시')+tx(24,80,'미래 거래 예측: 시간 순서')
 for x,w,label,c in [(65,230,'과거 학습','#dbeafe'),(305,115,'검증','#dcfce7'),(430,140,'미래 시험','#ffedd5')]:b+=box(x,100,w,55,c)+tx(x+14,133,label)
 b+=tx(65,190,'시간 → · 신고 지연과 결과 확정 시점도 고려')+tx(24,245,'새 단지 적용: 단지 전체를 한쪽에 배정')
 for i,(label,c) in enumerate([('단지 A','#dbeafe'),('단지 B','#dbeafe'),('단지 C','#dcfce7'),('단지 D','#ffedd5')]):b+=box(65+i*130,267,115,55,c)+tx(80+i*130,300,label)
 b+=tx(24,370,'시간과 새 집단이 모두 중요하면 두 조건을 함께 설계합니다')
 g2=fig('design','시간과 집단을 반영한 분할',b,'그림 2. 가상 시간·단지 개념도입니다. 위는 시간 순서, 아래는 집단 격리의 원리이며 특정 배정 비율을 권장하는 그림이 아닙니다.')
 b=tx(24,28,'표준화 기준을 어디서 계산했는가')
 for y,title,desc,c in [(80,'학습만: 40·60·80',f'평균 {mu:.0f}, 표준편차 {sd:.2f} → 140의 z={d["scaling"]["train_z"]:.2f}','#dbeafe'),(220,'평가값 140까지 포함',f'평균 {all_mu:.0f}, 표준편차 {all_sd:.2f} → z={d["scaling"]["leaked_z"]:.2f}','#ffedd5')]:b+=box(65,y,510,90,c)+tx(85,y+30,title)+tx(85,y+62,desc)
 b+=tx(24,370,'평가 자료의 Y를 보지 않아도 X의 분포가 학습에 섞일 수 있습니다')
 g3=fig('scaling','전처리 누수의 계산 예제',b,'그림 3. 별도 가상 면적값이며 표준편차는 해당 자료 수로 나눠 계산했습니다. 좌표가 달라지는 예제이지, 모든 모형의 성능이 반드시 좋아진다는 주장은 아닙니다.')
 b=tx(24,28,'가상 목표값: 검증 MAE로 상수 예측 규칙 선택')+line(110,320,560,320)
 for i,(label,v,c) in enumerate([('학습 평균',candidates['mean']['validation_MAE'],'#94a3b8'),('학습 중앙값',candidates['median']['validation_MAE'],'#2563eb')]):
  xx=210+i*210;b+=box(xx-40,320-v*25,80,v*25,c)+tx(xx-10,305-v*25,f'{v:.1f}')+tx(xx-40,350,label)
 for v in [0,2,4,6,8]:b+=tx(65,325-v*25,v)
 b+=tx(24,390,f'중앙값 규칙 선택 → 학습+검증 재적합 → 시험 MAE {test_mae:.2f}')
 g4=fig('selection','선택과 최종 평가의 분리',b,'그림 4. 막대는 검증 오차만 비교합니다. 시험 오차는 선택과 재적합을 끝낸 뒤 한 번 계산했습니다. 작은 가상 예제로 성능 우열의 일반적 근거가 아닙니다.',420)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('roles','역할 구분','배우는 자료와 평가하는 자료를 구별합니다','<p>모형은 학습 자료에서 규칙을 배웁니다. 같은 자료로 평가하면 이미 본 관측을 얼마나 잘 맞추었는지 알 수 있지만, 새로운 대상에서의 성능은 낙관적으로 보일 수 있습니다. 평가 자료는 실제 활용 시 마주할 새 대상과 비슷한 역할을 하도록 설계합니다.</p>'+g1+'<p><strong>학습 자료</strong>는 계수·전처리 기준을 정하고, <strong>검증 자료</strong>는 후보 모형·설정·특징·조기 종료·분류 임계값을 선택하는 데 씁니다. <strong>시험 자료</strong>는 그 선택이 끝난 절차를 평가합니다. 이름보다 실제로 어느 결정에 사용했는지가 중요합니다.</p><p>검증도 선택에 쓰이므로 그 최저 오차는 최종 성능의 중립적 추정이 아닙니다. 시험 결과를 보고 반복 수정했다면 그 자료도 사실상 검증 역할을 했다는 점을 기록해야 합니다.</p>')
 sec('target','평가 대상 정하기','무엇이 새로운 대상인지 먼저 정합니다','<p>같은 단지의 새 거래, 처음 보는 단지, 다음 달 거래, 처음 보는 지역은 서로 다른 일반화 문제입니다. 분석 단위와 예측 시점, 입력의 이용 가능 시점, 목표가 확정되는 시점을 먼저 적으세요.</p><p>행 단위 무작위 분할은 관측들이 대체로 독립적이고 활용 대상과 같은 분포에서 나온다는 상황에 적합할 수 있습니다. 무작위라는 이유만으로 모든 의존성이나 시간 변화가 해결되지는 않습니다. 공통 학습 자료의 번호는 실제 거래일이 아니므로 번호 분할을 시간 검증이라고 부르지 않습니다.</p>')
 sec('design','시간·집단 분할','자료의 의존성을 경계에 반영합니다','<p>미래 예측은 과거로 학습하고 이후 시점에서 평가하는 순서가 기본입니다. 거래일만이 아니라 신고·공개 시점도 확인하세요. 예측 당시 아직 신고되지 않은 거래를 과거 정보로 넣으면 실제보다 많은 정보를 이용하게 됩니다.</p>'+g2+'<p>새 단지·새 지역에 적용하려면 같은 집단이 학습과 평가에 동시에 나타나지 않도록 묶어서 나눕니다. 반대로 기존 단지의 미래가 목표라면 동일 단지가 양쪽에 있다는 사실만으로 누수라고 단정하지 않고, 시간과 정보의 가용성을 확인합니다.</p><p>기간이 겹치는 목표나 지연된 결과가 있다면 필요에 따라 경계에서 간격을 두거나 겹치는 관측을 제외합니다. 격리 간격은 관측 주기와 목표 기간에 근거해야 하며 고정된 만능 값은 없습니다.</p>')
 sec('ratio','표본 수와 비율','80 대 20은 법칙이 아닙니다','<p>학습 자료가 너무 작으면 모형이 불안정하고, 평가 자료가 너무 작으면 점수의 변동이 큽니다. 전체 건수뿐 아니라 독립적인 단지·지역 수와 분류의 희소 범주 건수도 고려해야 합니다.</p><p>독립 관측의 분류 문제에서는 계층화로 범주 비율을 비슷하게 유지할 수 있지만, 이를 위해 시간 순서를 깨거나 같은 집단을 나누면 원래 평가 목적을 훼손할 수 있습니다. 독립성·시간 제약을 우선하며 표본 구성과 한계를 함께 보고합니다.</p><p>교차검증은 자료 활용을 높이는 방법입니다. 각 반복에서 학습과 검증 역할을 바꾸더라도 전처리·특징 선택을 그 반복의 학습 부분 안에서 수행해야 합니다. 자세한 비교와 중첩 교차검증은 26장에서 다룹니다.</p>')
 sec('leakage','누수의 종류','예측할 때 알 수 없는 정보가 섞이면 평가가 달라집니다','<p><strong>목표 누수</strong>는 예측하려는 답이나 그 답을 직접 복원하는 입력을 쓰는 경우입니다. 단가를 예측하면서 같은 거래의 거래금액과 면적으로 단가를 복원해 넣는 예가 있습니다.</p><p><strong>미래 정보 누수</strong>는 예측 이후 확정된 통계·상태·신고 내용을 미리 안 것처럼 쓰는 경우입니다. 지역 평균을 만들 때 예측 시점 이후 거래까지 포함하지 않았는지 확인합니다.</p><p><strong>평가 오염</strong>은 시험 자료를 이용한 전처리·변수 선택·설정 조정·반복 비교입니다. 중복 행이나 같은 사건에서 파생된 관측이 양쪽에 나뉘면 기억에 가까운 평가가 될 수도 있습니다. 새 지역으로 분포가 바뀌어 성능이 나빠지는 현상은 누수가 없어도 생길 수 있으므로 둘을 구별합니다.</p>')
 sec('scaling','전처리 누수','변환을 적용하는 것과 기준을 배우는 것은 다릅니다',f'<p>학습 면적을 40·60·80㎡, 평가 면적을 140㎡라고 가정합니다. 학습 자료의 평균 {mu:.0f}, 표준편차 {sd:.2f}로 계산한 z는 {d["scaling"]["train_z"]:.2f}입니다. 평가값까지 포함하면 평균 {all_mu:.0f}, 표준편차 {all_sd:.2f}가 되어 z={d["scaling"]["leaked_z"]:.2f}로 달라집니다.</p>'+g3+'<p>평가 자료에는 학습에서 정한 변환을 적용합니다. 결측 대체·표준화·PCA·특징 선택처럼 자료에서 기준을 추정하는 단계는 학습 안에 둡니다. 교차검증이라면 매 폴드 안에서 다시 추정합니다. 파이프라인은 이 경계를 일관되게 지키는 구현 방법입니다.</p><p>단위 환산이나 사전에 정한 고정 공식처럼 자료에서 아무것도 추정하지 않는 변환은 같은 규칙으로 적용할 수 있습니다. 전체 평균을 썼다고 모든 알고리즘의 예측이 반드시 바뀌는 것은 아니지만, 독립 평가를 위한 정보 경계는 지켜야 합니다.</p>')
 sec('selection','선택과 재적합 예제','규칙을 고른 뒤 시험 자료를 엽니다',f'<p>별도 가상 목표값을 학습 [10,10,10,10,20,60], 검증 [11,12,13], 시험 [9,11,16]으로 미리 나눕니다. 후보는 ‘학습 평균을 항상 예측’과 ‘학습 중앙값을 항상 예측’ 두 상수 기준모형뿐이며 비교 지표는 MAE로 정합니다.</p><p>학습 평균은 20, 중앙값은 10입니다. 검증 MAE는 각각 8과 2이므로 중앙값 규칙을 고릅니다. 시험값은 이 선택에 쓰지 않았습니다.</p>'+g4+f'<p>선택한 규칙을 학습+검증 9개 값에 다시 적합하면 중앙값은 {final:.0f}입니다. 고정된 예측값 {final:.0f}로 시험 [9,11,16]을 평가하면 절대오차는 2·0·5이고 MAE=7/3≈{test_mae:.2f}입니다. 선택된 것은 상수 10 자체가 아니라 ‘중앙값을 추정하는 규칙’이라는 점을 구별합니다.</p><p>재적합에는 전처리도 포함하며 시험 자료는 계속 제외합니다. 이 예제는 절차를 보여 주는 작은 가상 사례로, 검증 3건·시험 3건이 충분하다는 뜻이 아닙니다.</p>')
 sec('test-use','시험 자료의 사용','한 번의 점수보다 절차와 기록이 중요합니다','<p>시험은 평가·보고에 사용하도록 남겨 둔 자료입니다. 결과를 본 뒤 문제를 발견해 수정하는 것은 가능하지만, 같은 시험에서 개선됐다고 독립 성능 확인이 끝났다고 주장하면 안 됩니다. 새 평가 자료를 확보하거나 사용 이력을 명시해야 합니다.</p><p>평가 후 배포용 모형을 더 많은 자료로 재학습할 수도 있습니다. 그 모형은 시험에서 직접 평가한 모형과 다르므로 기존 시험 점수를 새 모형의 직접 측정 성능처럼 제시하지 않습니다. 배포 후에도 시간 변화와 새 지역의 성능을 모니터링합니다.</p>')
 sec('audit','부동산 분석 점검','행의 분리뿐 아니라 정보의 경로를 확인합니다','<ol><li>예측 시점과 목표 기간, 관측·신고·공개 시점을 구분합니다.</li><li>같은 물건·단지·거래의 중복 및 파생 행을 식별합니다.</li><li>지역 집계·인코딩·결측 대체가 어느 자료로 계산됐는지 확인합니다.</li><li>분할 규칙·기간·집단·난수 시드와 제외 규칙을 기록합니다.</li><li>후보·지표·시험 사용 이력과 집단별 오차를 함께 보고합니다.</li></ol><p>난수 시드를 고정하면 재현에는 도움이 되지만 특정 분할의 대표성을 보장하지는 않습니다. 누수가 없더라도 작은 평가 표본의 오차는 불확실하므로 건수와 적용 범위를 함께 읽습니다.</p>')
 sec('practice','확인 문제','정보가 어느 단계에 쓰였는지 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('전체 자료로 표준화한 뒤 나누면 Y를 안 봤으니 괜찮나요?','평가 X의 분포도 학습 기준에 섞입니다. 학습에서 기준을 정하고 평가에는 적용합니다.'),('미래 예측에 무작위 분할이면 충분한가요?','시간 순서와 정보 공개 시점, 목표 기간의 겹침을 반영해야 합니다.'),('검증에서 고른 모형을 학습+검증으로 다시 학습해도 되나요?','선택이 끝났다면 가능합니다. 전처리도 다시 학습하되 시험 자료는 제외합니다.'),('시험 점수를 보고 후보를 바꾸면 같은 시험은 여전히 독립적인가요?','아니요. 선택에 영향을 주었으므로 평가 사용 이력을 밝히고 새로운 독립 평가를 고려해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','성능 숫자와 분할 설계를 함께 봅니다','<p>성능 지표를 읽을 때 학습·검증·시험 중 어디서 계산했는지, 대상 기간과 단지·지역 분리 기준, 전처리 학습 범위를 확인하세요. 이 장의 분할 예제가 서비스의 실제 평가 설계라고 전제하지 않습니다.</p><p>같은 지역의 과거 자료 성능을 새 지역·미래 시점에 그대로 옮겨 읽지 않습니다. 성능은 자료와 절차에 조건부이며 개별 적정가나 결과 보장이 아닙니다.</p>')
 sec('recap','정리와 참고자료','새로운 정보를 모르는 상태를 평가에서 재현합니다','<p>자료 이름보다 역할과 정보 경계가 중요합니다. 활용 상황에 맞춰 분할하고, 학습 안에서 전처리·선택을 수행하며, 마지막 평가의 사용 이력을 남기세요.</p><p>다음 <a href="/learn/stats/overfitting/">24장 「과적합과 편향–분산의 균형」</a>으로 이어집니다.</p><ul><li><a href="https://scikit-learn.org/stable/common_pitfalls.html">scikit-learn: 전처리와 데이터 누수</a></li><li><a href="../split-example.json">가상 분할·선택·재적합·표준화 예제</a></li></ul><p class="learn-source-note">본문과 그림은 별도 가상 자료와 직접 작성한 개념도입니다. 실제 거래 자료의 성능 추정이 아닙니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'train-validation-test/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'supervised-unsupervised/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/supervised-unsupervised/','https://ch2data.com/learn/stats/train-validation-test/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="학습·검증·시험 자료와 데이터 누수">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1학습·검증·시험 역할, 시간·집단 분할과 전처리·변수 선택의 데이터 누수를 예제로 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
