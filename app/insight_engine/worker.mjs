import {normalize,analyze,eligible,classify,sentiment,tokens} from './lib/core.mjs';
import {containsTerm} from './lib/search-query.mjs';
import {wordcloudSVG} from './lib/wordcloud.mjs';
import {Feishu} from './lib/feishu.mjs';
import {DatabaseSync} from 'node:sqlite';
import {mkdirSync} from 'node:fs';
import path from 'node:path';
let raw='';for await(const chunk of process.stdin)raw+=chunk;
try {
 const input=JSON.parse(raw),o=input.options||{};
 let rows=(input.rows||[]).map(r=>{const n=normalize(r);if(n&&r.platform==='wechat'){n.platform='wechat';n.key=n.key.replace(/^unknown:/,'wechat:');}return n?{...n,id:r.id,author_url:r.author_url||'',off_topic:!!r.off_topic,keyword:r.keyword,favorite:!!r.favorite,note:r.note||'',parent_text:r.parent_text||'',category:classify(n.text).join('、'),sentiment:sentiment(n.text)}:null;}).filter(Boolean);
 const rawTotal=(input.rows||[]).length, normalizedTotal=rows.length, unique=new Map();
 for(const r of rows){const old=unique.get(r.key);if(!old)unique.set(r.key,r);else{old.favorite ||= r.favorite;old.note ||= r.note;}}
 rows=[...unique.values()];
 const analysis={...analyze(rows,o),rawTotal,empty:rawTotal-normalizedTotal,duplicates:normalizedTotal-rows.length};
 for(const item of [...analysis.keywords,...analysis.topics])delete item.ids;
 let matched=rows.filter(r=>(o.all||eligible(r,o))&&(!o.q||containsTerm(r.text,o.q))&&(!o.word||tokens(r.text).includes(o.word.toLowerCase()))&&(!o.category||classify(r.text).includes(o.category))&&(!o.sentiment||r.sentiment===o.sentiment)&&(!o.favorite||r.favorite)&&(!o.needs||!!r.category));
 matched.sort(o.sort==='oldest'?(a,b)=>a.created_at.localeCompare(b.created_at):o.sort==='likes'?(a,b)=>b.likes-a.likes:(a,b)=>b.created_at.localeCompare(a.created_at)||b.id-a.id);
 let result;
 if(input.action?.startsWith('feishu')){
  const dir=input.dataDir;mkdirSync(dir,{recursive:true});const db=new DatabaseSync(path.join(dir,'feishu.sqlite'));const store={db};const f=new Feishu(store,path.join(dir,'feishu.json'));
  result=input.action==='feishu-status'?await f.status():input.action==='feishu-save'?await f.save(input.config||{}):await f.export(input.task,matched);
  db.close();
 }else if(input.action==='wordcloud')result={svg:wordcloudSVG(analyze(matched,{includeNoise:true}).keywords,input.task.name)};
 else if(input.action==='export')result={rows:matched,keywords:analyze(matched,{includeNoise:true}).keywords};
 else {const pages=Math.max(1,Math.ceil(matched.length/10)),page=Math.max(1,Math.min(pages,Number(o.page)||1));result={analysis,hot:rows.filter(r=>eligible(r,o)).sort((a,b)=>b.likes-a.likes).slice(0,5),matched:matched.length,page,pages,comments:matched.slice((page-1)*10,page*10)};}
 process.stdout.write(JSON.stringify({ok:true,result}));
}catch(e){process.stdout.write(JSON.stringify({ok:false,error:e.message}));process.exitCode=1;}
