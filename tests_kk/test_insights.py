import io,json,sqlite3,tempfile,unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel,create_engine,Session
import app.db as database
import app.insights as ins
from app.models import KeywordCollectionJob,KeywordCollectionContent,KeywordCollectionComment

class InsightsTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.old_data=ins.DATA;cls.old_engine=database._engine
  ins.DATA=Path(cls.tmp.name)/'marks';database._engine=create_engine('sqlite:///'+cls.tmp.name+'/test.sqlite',connect_args={'check_same_thread':False})
  SQLModel.metadata.create_all(database._engine)
  with Session(database._engine) as s:
   for jid,platform in [(1,'douyin'),(2,'xhs')]:
    s.add(KeywordCollectionJob(id=jid,account_id=jid,platform=platform,keywords='["安装"]'))
    s.add(KeywordCollectionContent(id=jid,job_id=jid,platform=platform,aweme_id=str(jid),desc='安装教程',xsec_token='testToken'))
    for i in range(23 if jid==1 else 1):s.add(KeywordCollectionComment(id=jid*100+i,job_id=jid,content_id=jid,platform=platform,aweme_id=str(jid),comment_id=str(i),text='新手安装多少钱？' if i%2==0 else '=HYPERLINK("bad")',like_count=i,create_time=1700000000+i))
   s.commit()
  app=FastAPI();app.include_router(ins.router);cls.client=TestClient(app)
 @classmethod
 def tearDownClass(cls):database._engine.dispose();database._engine=cls.old_engine;ins.DATA=cls.old_data;cls.tmp.cleanup()
 def test_pagination_and_scope(self):
  pages=[self.client.get(f'/api/insights/1/analysis?page={i}').json() for i in [1,2,3]]
  self.assertEqual([len(x['comments']) for x in pages],[10,10,3]);ids=[c['id'] for p in pages for c in p['comments']];self.assertEqual(len(set(ids)),23)
  self.assertEqual(pages[0]['analysis']['total'],23)
 def test_platform_isolation_and_source(self):
  r=self.client.get('/api/insights/2/analysis').json();self.assertEqual(r['analysis']['total'],1);self.assertEqual(r['comments'][0]['platform'],'xiaohongshu');self.assertIn('xsec_token=testToken',r['comments'][0]['source_url'])
 def test_favorite_and_cross_job_rejected(self):
  self.assertEqual(self.client.put('/api/insights/2/comments/100',json={'favorite':True}).status_code,404)
  self.assertEqual(self.client.put('/api/insights/1/comments/100',json={'favorite':True,'note':'跟进'}).status_code,200)
  r=self.client.get('/api/insights/1/analysis?favorite=1').json();self.assertEqual(r['matched'],1);self.assertEqual(r['comments'][0]['note'],'跟进')
 def test_filter_export_all_pages_and_formula(self):
  r=self.client.get('/api/insights/1/export?format=json').json();self.assertEqual(len(r['rows']),23)
  r=self.client.get('/api/insights/1/analysis?category=购买咨询').json();self.assertEqual(r['matched'],12)
  r=self.client.get('/api/insights/1/export?format=xlsx');from openpyxl import load_workbook
  w=load_workbook(io.BytesIO(r.content));self.assertEqual(w.active.max_row,24);self.assertFalse(any(c.data_type=='f' for row in w.active for c in row))
 def test_empty_and_bad_inputs(self):
  self.assertEqual(self.client.get('/api/insights/1/analysis?q=不存在').json()['matched'],0)
  self.assertEqual(self.client.get('/api/insights/999/analysis').status_code,404)
  self.assertEqual(self.client.get('/api/insights/1/analysis?page=no').status_code,422)
 def test_duplicate_accounting_and_wechat(self):
  rows=[{'id':1,'comment_id':'x','post_id':'p','platform':'wechat','text':'求安装教程'},{'id':2,'comment_id':'x','post_id':'p','platform':'wechat','text':'求安装教程','favorite':True}]
  r=ins.worker({'rows':rows})
  self.assertEqual(r['analysis']['rawTotal'],2);self.assertEqual(r['analysis']['duplicates'],1);self.assertEqual(r['comments'][0]['platform'],'wechat');self.assertTrue(r['comments'][0]['favorite'])
 def test_wordcloud(self):
  r=self.client.get('/api/insights/1/export?format=svg');self.assertEqual(r.status_code,200);self.assertIn('<svg',r.text)
if __name__=='__main__':unittest.main()
