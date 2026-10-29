"""Conservative title relevance; preserve raw data, reject weak search recommendations."""
import re,unicodedata,json
from collections import Counter

def clean_query(value):
    value=unicodedata.normalize('NFKC',str(value or '')).strip()
    return re.sub(r'^\s*(?:\d+[.、)）]|[-*•])\s*','',value).strip()

def keywords(raw):
    try: values=json.loads(raw) if isinstance(raw,str) else raw
    except (ValueError,TypeError): return []
    return [clean_query(v) for v in (values or []) if clean_query(v)]

def compact(s):return re.sub(r'[^\w\u4e00-\u9fff]','',clean_query(s).lower())

GENERIC={'多少钱','怎么样','怎么选','有没有','好不好','在哪里','为什么','工作室','有限公司','关键词','哪个好','价格低','如何做'}
def task_anchor(values):
    qs=keywords(values);counts=Counter()
    for q in qs:
        q=compact(q);counts.update({q[i:i+3] for i in range(len(q)-2) if q[i:i+3] not in GENERIC})
    candidates=[(n,k) for k,n in counts.items() if n>=max(2,len(qs)*.25)]
    if candidates:return max(candidates)[1]
    pairs=Counter()
    for q in qs:
        q=compact(q);pairs.update({q[i:i+2] for i in range(len(q)-1) if q[i:i+2] not in {'工程','项目','价格','多少','怎么','公司','可以','使用','定制','厂房'}})
    return max(((n,k) for k,n in pairs.items() if n>=max(2,len(qs)*.5)),default=(0,''))[1]

def relevant(title,query,values):
    if not query:return any(relevant(title,k,values) for k in keywords(values))
    title=compact(title);q=compact(query)
    if not title or not q:return False
    anchor=task_anchor(values)
    if anchor and anchor not in title:return False
    if q in title or (anchor and anchor in title):return True
    for filler in ['多少钱一米','多少钱','怎么选','有没有','好不好','哪里','如何','为什么','是不是','怎么样','比较','可以','需要','本地','厂家','价格','选择']:
        q=q.replace(filler,'')
    terms=set(re.findall(r'[a-z0-9]+',q))
    chinese=''.join(re.findall(r'[\u4e00-\u9fff]',q));terms.update(chinese[i:i+2] for i in range(len(chinese)-1))
    return bool(terms) and sum(t in title for t in terms)/len(terms)>=.6
