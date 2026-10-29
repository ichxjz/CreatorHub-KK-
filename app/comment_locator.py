"""Read-only, bounded comment navigation in an account browser."""
import json

async def locate_comment(page, comment):
    cid, text, author = (str(comment.get(k) or '') for k in ('comment_id','text','author'))
    selector = '[data-e2e="comment-item"], [data-comment-id], .comment-item'
    # Open the comment panel when the video page starts with it collapsed.
    for css in ['[data-e2e="video-comment"]','[data-e2e="comment-icon"]']:
        toggle=page.locator(css).first
        if await toggle.count() and await toggle.is_visible() and not await page.locator(selector).count():
            await toggle.click(timeout=2000)
            break
    for attempt in range(30):
        if page.is_closed():
            return {'status':'closed','message':'浏览器已关闭，请重新打开定位。'}
        for attr in ('data-comment-id','data-id','id'):
            if not cid: continue
            matches=page.locator(f'[{attr}={json.dumps(cid)}]')
            if await matches.count() == 1 and await matches.first.is_visible():
                target=matches.first
                await target.evaluate("el=>el.scrollIntoView({block:'center',behavior:'instant'})")
                await target.evaluate("el=>{el.style.outline='3px solid #ff4268';el.style.outlineOffset='5px'}")
                return {'status':'found','message':'已按评论 ID 定位并标记原评论。'}
        # Text alone is not identity: require a unique comment block and author.
        if text and author:
            candidates=page.locator(selector).filter(has_text=author)
            found=[]
            for i in range(await candidates.count()):
                candidate=candidates.nth(i)
                same=await candidate.evaluate("""(el,target)=>{
                  const norm=s=>s.normalize('NFKC').replace(/\[[^\]]{1,16}\]/g,'').replace(/\s+/g,'');
                  const value=norm(target.text);const body=norm(el.innerText);
                  return value.length>0&&body.includes(value)&&body.includes(norm(target.author));
                }""",{'text':text,'author':author})
                if same and await candidate.is_visible():found.append(candidate)
            if len(found)==1:
                target=found[0]
                await target.evaluate("el=>el.scrollIntoView({block:'center',behavior:'instant'})")
                await target.evaluate("el=>{el.style.outline='3px solid #ff4268';el.style.outlineOffset='5px'}")
                return {'status':'matched','message':'已按作者与评论内容定位并标记（忽略空白及表情标记），请核对。'}
        # Only expand replies underneath the known parent comment.
        parent=str(comment.get('parent_id') or '')
        if parent:
            root=page.locator(f'[data-comment-id={json.dumps(parent)}], [id={json.dumps(parent)}]').first
            if await root.count():
                expand=root.get_by_text('展开',exact=False).first
                if await expand.count() and await expand.is_visible():
                    await expand.click(timeout=1500)
        await page.evaluate("""() => {
          const item=document.querySelector('[data-e2e="comment-item"], [data-comment-id], .comment-item, [data-e2e="comment-list"]');
          let el=item;
          while(el && el!==document.body){
            if(/auto|scroll/.test(getComputedStyle(el).overflowY)&&el.scrollHeight>el.clientHeight+20){el.scrollBy(0,Math.max(500,el.clientHeight*.8));return;}
            el=el.parentElement;
          }
          window.scrollBy(0,600);
        }""")
        await page.wait_for_timeout(1000)
    return {'status':'not_found','message':'已打开原作品，但尚未找到对应评论。请检查登录并展开评论区后重试；评论可能未加载或已隐藏。'}
