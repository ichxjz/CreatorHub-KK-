"""Local collection insights; reads collection data, keeps annotations separately."""
from pathlib import Path
from contextlib import contextmanager
import csv, io, json, os, shutil, sqlite3, subprocess, threading, sys
from urllib.parse import urlencode, quote
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import select
from .relevance import relevant
from .db import get_session
from .models import KeywordCollectionJob, KeywordCollectionContent, KeywordCollectionComment

router = APIRouter(prefix='/api/insights')
ROOT = Path(__file__).resolve().parents[1]
DATA = (Path.cwd() if getattr(sys, 'frozen', False) else ROOT) / 'data' / 'insights'
FEISHU_LOCK = threading.Lock()

@contextmanager
def annotation_db():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'annotations.sqlite', timeout=10)
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS annotations(job INTEGER, comment INTEGER, favorite INTEGER DEFAULT 0, note TEXT DEFAULT "", PRIMARY KEY(job,comment))')
            yield db
    finally:
        db.close()

def options(request):
    o = dict(request.query_params)
    for key in ['includeNoise','all','favorite','needs']:
        o[key] = o.get(key) == '1'
    try: o['page'] = max(1, int(o.get('page', 1)))
    except ValueError: raise HTTPException(422, '页码必须为整数')
    return o

def source_url(c):
    aid = quote(c.aweme_id, safe='')
    if c.platform == 'xhs':
        return 'https://www.xiaohongshu.com/explore/' + aid + ('?' + urlencode({'xsec_token':c.xsec_token,'xsec_source':c.xsec_source or 'pc_search'}) if c.xsec_token else '')
    if c.platform == 'douyin': return 'https://www.douyin.com/video/' + aid
    if c.platform == 'kuaishou': return 'https://www.kuaishou.com/short-video/' + aid
    return ''  # Do not invent WeChat share links.

def snapshot(job_id):
    with get_session() as s:
        job = s.get(KeywordCollectionJob, job_id)
        if not job: raise HTTPException(404, '采集任务不存在')
        contents = {c.id:c for c in s.exec(select(KeywordCollectionContent).where(KeywordCollectionContent.job_id == job_id)).all()}
        comments = s.exec(select(KeywordCollectionComment).where(KeywordCollectionComment.job_id == job_id).order_by(KeywordCollectionComment.id)).all()
        task = {'id':f'creatorhub:{job_id}', 'name':f'任务 {job_id} · '+(job.source_name or str(job.keywords)), 'mode':'collection','platform':job.platform,'status':job.status}
        with annotation_db() as db:
            marks = {r[0]:r[1:] for r in db.execute('SELECT comment,favorite,note FROM annotations WHERE job=?',(job_id,))}
        by_id = {(c.aweme_id,c.comment_id):c.text for c in comments}
        rows=[]
        for c in comments:
            content=contents.get(c.content_id);mark=marks.get(c.id,(0,''))
            rows.append({'id':c.id,'comment_id':c.comment_id,'text':c.text,'platform':{'xhs':'xiaohongshu','shipinhao':'wechat'}.get(c.platform,c.platform),'post_id':c.aweme_id,'source_url':source_url(content) if content else '', 'title':content.desc if content else '', 'keyword':content.keyword if content else '', 'created_at':c.create_time or '', 'likes':c.like_count,'parent_id':c.reply_to,'parent_text':by_id.get((c.aweme_id,c.reply_to),''),'author':c.user_nickname,'author_url':('https://www.douyin.com/user/' if c.platform=='douyin' else 'https://www.xiaohongshu.com/user/profile/' if c.platform=='xhs' else '')+quote(c.user_sec_uid,safe='') if c.user_sec_uid and c.platform in ['douyin','xhs'] else '', 'off_topic':bool(job.source_type=='keyword' and content and not relevant(content.desc,content.keyword,job.keywords)),'favorite':bool(mark[0]),'note':mark[1]})
        return task, rows

def worker(payload, timeout=40):
    bundled_node = ROOT / 'runtime' / 'node.exe'
    node = os.environ.get('CREATORHUB_NODE') or (str(bundled_node) if bundled_node.is_file() else shutil.which('node'))
    if not node: raise HTTPException(503, '洞察引擎需要 Node.js 24+，安装后重新启动工作台')
    try:
        r=subprocess.run([node, str(ROOT/'app/insight_engine/worker.mjs')], input=json.dumps(payload,ensure_ascii=False), capture_output=True,text=True,encoding="utf-8",timeout=timeout,cwd=ROOT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        result=json.loads(r.stdout)
    except subprocess.TimeoutExpired: raise HTTPException(504,'处理超时，请缩小筛选范围后重试；已保存数据不受影响')
    except (OSError,ValueError): raise HTTPException(503,'洞察引擎启动失败，请检查 Node.js 版本及运行日志')
    if not result.get('ok'): raise HTTPException(400,result.get('error','洞察处理失败'))
    return result['result']

@router.get('/{job_id}/analysis')
def analysis(job_id:int,request:Request):
    task,rows=snapshot(job_id)
    return {'task':task,**worker({'rows':rows,'options':options(request)})}

class Annotation(BaseModel):
    favorite: bool
    note: str = Field(default='',max_length=2000)

@router.put('/{job_id}/comments/{comment_id}')
def annotate(job_id:int,comment_id:int,body:Annotation):
    with get_session() as s:
        c=s.get(KeywordCollectionComment,comment_id)
        if not c or c.job_id!=job_id: raise HTTPException(404,'该任务中没有这条评论')
    with annotation_db() as db:
        db.execute('INSERT INTO annotations VALUES(?,?,?,?) ON CONFLICT(job,comment) DO UPDATE SET favorite=excluded.favorite,note=excluded.note',(job_id,comment_id,int(body.favorite),body.note))
    return {'ok':True}

COLS=[('platform','平台'),('text','评论内容'),('author','作者'),('likes','点赞'),('created_at','评论时间'),('title','作品标题'),('source_url','源链接'),('keyword','采集关键词'),('category','需求分类'),('sentiment','情绪参考'),('favorite','已收藏'),('note','备注'),('parent_text','上级评论')]
def safe_cell(v):
    if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')): return "'"+v
    return v

@router.get('/{job_id}/export')
def export(job_id:int,request:Request,format:str='xlsx',kind:str='comments'):
    if format not in ['xlsx','csv','json','svg'] or kind not in ['comments','keywords']:raise HTTPException(422,'不支持的导出类型')
    task,rows=snapshot(job_id);o=options(request)
    data=worker({'action':'wordcloud' if format=='svg' else 'export','rows':rows,'options':o,'task':task})
    headers={'Content-Disposition':f'attachment; filename="insights-{job_id}-{kind}.{format}"'}
    if format=='svg':return Response(data['svg'],media_type='image/svg+xml',headers=headers)
    records=data['keywords'] if kind=='keywords' else data['rows']
    cols=[('word','关键词'),('comments','评论数'),('posts','作品数'),('occurrences','出现次数'),('share','评论占比')] if kind=='keywords' else COLS
    if format=='json':return Response(json.dumps({'task':task,'scope':'当前筛选的已获取样本','rows':records},ensure_ascii=False),media_type='application/json',headers=headers)
    values=[[safe_cell(r.get(k,'')) for k,_ in cols] for r in records]
    if format=='csv':
        out=io.StringIO();w=csv.writer(out);w.writerow([v for _,v in cols]);w.writerows(values)
        return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers=headers)
    from openpyxl import Workbook
    wb=Workbook();ws=wb.active;ws.title='关键词' if kind=='keywords' else '评论';ws.append([v for _,v in cols])
    for row in values:ws.append(row)
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    meta=wb.create_sheet('范围说明');meta.append(['范围','仅已获取且符合筛选的样本，不代表平台全量']);meta.append(['分析方式','本地分词与规则，分类可重叠']);meta.append(['筛选条件',json.dumps(o,ensure_ascii=False)])
    out=io.BytesIO();wb.save(out)
    return Response(out.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers=headers)

@router.get('/feishu/status')
def feishu_status():return worker({'action':'feishu-status','dataDir':str(DATA)})
class FeishuConfig(BaseModel):
    appId:str=Field(max_length=200)
    appSecret:str=Field(default='',max_length=500)
    baseUrl:str=Field(max_length=1500)
@router.put('/feishu/config')
def feishu_config(body:FeishuConfig):
    with FEISHU_LOCK:return worker({'action':'feishu-save','dataDir':str(DATA),'config':body.model_dump()},timeout=65)
@router.post('/{job_id}/feishu')
def feishu_export(job_id:int,request:Request):
    if not FEISHU_LOCK.acquire(blocking=False):raise HTTPException(409,'飞书导出正在进行，请稍后再试')
    try:
        task,rows=snapshot(job_id)
        return worker({'action':'feishu-export','dataDir':str(DATA),'task':task,'rows':rows,'options':options(request)},timeout=300)
    finally: FEISHU_LOCK.release()

_locating_accounts=set()

@router.post('/{job_id}/comments/{comment_id}/locate')
async def locate_original_comment(job_id:int,comment_id:int):
    from . import main
    from .comment_locator import locate_comment
    from .models import DouyinAccount
    with get_session() as session:
        task=session.get(KeywordCollectionJob,job_id)
        comment=session.get(KeywordCollectionComment,comment_id)
        if not task or not comment or comment.job_id!=job_id: raise HTTPException(404,'评论不属于当前任务')
        if task.platform not in ['douyin','xhs']: raise HTTPException(422,'该平台暂不支持浏览器评论定位')
        account=session.get(DouyinAccount,task.account_id) if task.account_id else None
        if not account or account.platform!=task.platform: raise HTTPException(409,'请先为当前平台配置任务采集账号')
        content=session.get(KeywordCollectionContent,comment.content_id)
        url=source_url(content) if content else ''
        if not url: raise HTTPException(422,'缺少原作品链接')
        account_id=account.id
        target={'comment_id':comment.comment_id,'text':comment.text,'author':comment.user_nickname,'parent_id':comment.reply_to}
    if main.browser is None: raise HTTPException(503,'采集浏览器尚未就绪')
    lease=main.open_browsers.get(account_id)
    if not lease and main.browser.lock_for(f'acc:{account_id}').locked():
        raise HTTPException(409,'该账号正在采集，请稍后再定位，或先暂停该账号任务')
    if account_id in _locating_accounts: raise HTTPException(409,'正在定位该账号的评论，请等待当前操作完成')
    _locating_accounts.add(account_id)
    try:
        await main.open_account_browser(account_id,url=url)
        lease=main.open_browsers.get(account_id)
        page=getattr(lease,'page',None)
        if page is None: raise HTTPException(503,'浏览器未打开，请到平台账号检查登录')
        try:
            result=await locate_comment(page,target)
            await page.bring_to_front()
            return result
        except Exception:
            return {'status':'not_found','message':'原作品已打开，评论定位未完成。请检查登录或验证提示后重试。'}
    finally:
        _locating_accounts.discard(account_id)
