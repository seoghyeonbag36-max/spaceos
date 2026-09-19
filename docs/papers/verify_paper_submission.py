"""제출 원고의 근거·링크와 Word 패키지 무결성을 검수한다."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import math
import re
from lxml import etree

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
idx=(BASE/'evidence-index.md').read_text(encoding='utf-8-sig')
idx=idx.replace('pp','%p')
results=[]
for track in ('Platform','Page','Posting','Program'):
    src=(BASE/f'paper-{track.lower()}.md').read_text(encoding='utf-8-sig')
    assert '<!-- FILL' not in src and '<!-- TODO' not in src,track
    assert all(x in src for x in ('초록','서론','결론','참고문헌')),track
    assert '연구질문 RQ와 가설' in src and '가설 검증 결과' in src,track
    expected=3 if track in ('Platform','Program') else 4
    for number in range(1,expected+1):
        assert f'**RQ{number}.' in src and f'**H{number}:' in src,(track,number)
        assert f'| H{number} ' in src,(track,number,'판정 누락')
    for target in re.findall(r'\]\(([^)]+)\)',src):
        if not target.startswith('http'):
            assert (BASE/target.split('#')[0]).exists(),(track,target)
    body=re.sub(r'^#+\s+\d+(?:\.\d+)*\.?\s+','',src,flags=re.M)
    absent=sorted(x for x in set(re.findall(r'[0-9]+\.[0-9]+%?|[0-9]{3,}',body)) if x not in idx)
    assert not absent,(track,absent)
    path=BASE/'output'/f'PlaceOS_{track}_논문_20260919.docx'
    with ZipFile(path) as z:
        assert z.testzip() is None
        root=etree.fromstring(z.read('word/document.xml'))
        text=''.join(root.xpath('//w:t/text()',namespaces=NS))
        assert all(x in text for x in ('초록','서론','결론','참고문헌')),track
        assert '연구질문 RQ와 가설' in text and '가설 검증 결과' in text,track
        for number in range(1,expected+1):
            assert f'RQ{number}.' in text and f'H{number}:' in text,(track,number,'Word 누락')
        assert '\ufffd' not in text
        assert len([n for n in z.namelist() if n.endswith('.odttf')])==2
        assert not root.xpath('//w:trHeight[@w:hRule="exact"]',namespaces=NS)
        headings=root.xpath('//w:p[w:pPr/w:pStyle[@w:val="Heading1" or @w:val="Heading2"]]',namespaces=NS)
        assert len(headings)>6
        for n in z.namelist():
            if n.endswith('.xml'): etree.fromstring(z.read(n))
    results.append({'track':track,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'structure_verified'})

# 학습을 재실행하지 않고 보존된 대응표의 집계만 검산한다.
report=json.loads((ROOT/'reports/gnn_category2_mcnemar_2026-08-27.json').read_text(encoding='utf-8'))
for pair in report['mcnemar']:
    a,b=pair['a_only_hit'],pair['b_only_hit']
    assert pair['both_hit']+pair['both_miss']+a+b==pair['n']
    assert a+b==pair['discordant']
    chi=((abs(a-b)-1)**2/(a+b)) if a+b else 0
    assert round(chi,3)==pair['chi2']
    assert round(math.erfc(math.sqrt(chi/2)),4)==pair['p_value']
    assert round((b-a)/pair['n']*100,2)==pair['delta_pp']
out=BASE/'page-study/private/submission-structural-checks.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'documents':results,'mcnemar_summary_check':'passed','visual_qa':'separate'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'documents':len(results),'status':'passed','mcnemar_summary':'passed'},ensure_ascii=False))
