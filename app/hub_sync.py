"""Deduplicated background sync for the account hub, using existing platform adapters."""
import asyncio,time
from datetime import datetime
from fastapi import APIRouter,HTTPException
from .db import get_session
from .models import DouyinAccount
router=APIRouter(prefix='/api/hub/sync')
states={}
tasks={}
def schedule(account_id,force=False):
    with get_session() as s:
        account=s.get(DouyinAccount,account_id)
        if not account:raise HTTPException(404,'账号不存在')
        if account.status=='invalid':raise HTTPException(409,'登录已失效，请重新登录后同步')
    if account_id in tasks and not tasks[account_id].done():return states[account_id]
    old=states.get(account_id)
    if old and not force and time.time()-old['started']<600:return old
    state={'account_id':account_id,'status':'running','step':'等待账号空闲','started':time.time(),'results':[]}
    states[account_id]=state
    tasks[account_id]=asyncio.create_task(run(account_id,state))
    return state
async def run(account_id,state):
    from . import main
    try:
        for _ in range(60):
            if main.browser is None:raise RuntimeError('浏览器尚未就绪')
            if not main.browser.lock_for(f'acc:{account_id}').locked():break
            state['step']='等待账号空闲：请关闭手动打开的账号窗口，或等待采集结束'
            await asyncio.sleep(5)
        else:raise RuntimeError('账号仍被占用，请关闭账号窗口后点击重新同步')
        async def profile():
            with get_session() as session:
                account=session.get(DouyinAccount,account_id)
                storage=account.storage_state or account.creator_storage_state or ''
            async def fetch():
                status,error=await main._enrich_account_profile(account_id,storage,detailed=True)
                return {'ok':status=='ok','error':error if status!='ok' else ''}
            return await main.engine._guarded_read_dict(account_id,main.OperationKind.READ_LIGHT,f'hub-profile:{account_id}',fetch)
        operations=[('账号资料',profile),('作品',lambda:main.sync_account_works(account_id)),('关注',lambda:main._sync_follows_impl(account_id,'following')),('粉丝',lambda:main._sync_follows_impl(account_id,'fan')),('私信',lambda:main.sync_dm(account_id))]
        for label,operation in operations:
            kind=main.OperationKind.READ_HEAVY if label in ['关注','粉丝'] else main.OperationKind.READ_LIGHT
            for _ in range(120):
                decision=main.engine.risk.preflight(account_id,kind)
                if decision.allowed:break
                state['step']=f'{label}：{decision.reason}，到期后自动继续'
                await asyncio.sleep(5)
            else:
                state['results'].append({'name':label,'ok':False,'message':'平台仍在冷却，请稍后重试'})
                continue
            state['step']='正在同步'+label
            try:
                result=await asyncio.wait_for(operation(),timeout=120)
                if result.get('skipped') or result.get('ok') is False or result.get('error'):
                    state['results'].append({'name':label,'ok':False,'message':str(result.get('reason') or result.get('error') or '暂未完成，请检查平台状态')})
                else:state['results'].append({'name':label,'ok':True,'message':'已更新'})
            except asyncio.TimeoutError:state['results'].append({'name':label,'ok':False,'message':'同步超时，可稍后重试'})
            except Exception as e:state['results'].append({'name':label,'ok':False,'message':str(getattr(e,'detail',str(e)))})
        state['status']='done' if all(r['ok'] for r in state['results']) else 'partial'
        state['step']='同步完成' if state['status']=='done' else '部分数据未更新，请查看详情'
    except asyncio.CancelledError:
        state.update(status='interrupted',step='同步中断，请重新同步');raise
    except Exception as e:state.update(status='failed',step=str(e))
    finally:state['finished']=time.time()
@router.post('/{account_id}')
async def start(account_id:int,force:bool=False):return schedule(account_id,force)
@router.get('/{account_id}')
async def status(account_id:int):return states.get(account_id,{'account_id':account_id,'status':'idle','step':'尚未同步','results':[]})
