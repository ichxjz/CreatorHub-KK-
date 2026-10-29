// Preserve phrases; separators mean separate searches, never one oversized query.
export function searchQueries(input) {
 const lines=String(input??'').normalize('NFKC').split(/\r?\n/)
  .map(s=>s.trim()).filter(s=>s&&!/^#{1,6}\s|^```|[：:]$/.test(s))
  .map(s=>s.replace(/^\s*(?:[-*+]\s+|\d+[.)、]\s*)/,'').replace(/\*\*/g,''));
 const result=[...new Map(lines.join('\n').split(/[,，、;；\n]+/).map(s=>s.trim()).filter(Boolean).map(s=>[s.toLowerCase(),s])).values()];
 if(!result.length)throw Error('请输入搜索关键词，每行一个或用顿号分隔');
 if(result.length>100)throw Error('每次最多100个关键词，请拆分任务');
 if(result.some(s=>s.length>100))throw Error('单个关键词不能超过100字，请用换行或顿号分隔');
 return result;
}
export function containsTerm(content,term) {
 const value=String(content??'').normalize('NFKC').toLowerCase();
 const needle=String(term??'').normalize('NFKC').trim().toLowerCase();
 if(!needle)return false;
 const escaped=needle.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 return new RegExp(`${/^[a-z0-9]/.test(needle)?'(?<![a-z0-9_])':''}${escaped}${/[a-z0-9]$/.test(needle)?'(?![a-z0-9_])':''}`,'u').test(value);
}
export function matchesSearch(content,query) {
 return String(query).trim().split(/\s+/).every(term=>containsTerm(content,term));
}
export function matchesSearchResponse(response,p,query) {
 try {
  const u=new URL(response.url());const domain=p==='douyin'?'douyin.com':'xiaohongshu.com';
  if(u.hostname!==domain&&!u.hostname.endsWith('.'+domain))return false;
  if(!/\/search\//i.test(u.pathname)||/suggest|recommend|hot/i.test(u.pathname)||response.status()!==200)return false;
  let payload={};try{payload=response.request().postDataJSON()||{};}catch{}
  const keyword=u.searchParams.get('keyword')??u.searchParams.get('search_keyword')??payload.keyword??payload.search_keyword;
  return typeof keyword==='string'&&keyword.normalize('NFKC').trim().toLowerCase()===query.normalize('NFKC').trim().toLowerCase();
 }catch{return false;}
}
