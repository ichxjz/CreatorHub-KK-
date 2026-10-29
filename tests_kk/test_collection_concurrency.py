import asyncio,tempfile,unittest
from types import SimpleNamespace
from sqlmodel import SQLModel,Session,create_engine
import app.db as db
from app.models import KeywordCollectionJob
from app.engine.monitor import MonitorEngine

class ConcurrencyTest(unittest.IsolatedAsyncioTestCase):
 async def test_platform_caps_and_immediate_refill(self):
  old=db._engine
  with tempfile.TemporaryDirectory() as tmp:
   db._engine=create_engine('sqlite:///'+tmp+'/test.db');SQLModel.metadata.create_all(db._engine)
   try:
    with Session(db._engine) as s:
     for id in range(1,13):s.add(KeywordCollectionJob(id=id,account_id=id,platform='douyin' if id<=6 else 'xhs'))
     s.add(KeywordCollectionJob(id=13,account_id=2,platform='douyin'));s.commit()
    e=object.__new__(MonitorEngine);e._collection_tasks={};e._collection_platforms={};e._collection_accounts={};e._running=True
    locks={};e.browser=SimpleNamespace(lock_for=lambda k:locks.setdefault(k,asyncio.Lock()))
    e.risk=SimpleNamespace(preflight=lambda *a:SimpleNamespace(allowed=True))
    events={id:asyncio.Event() for id in range(1,14)};started=[]
    started_events={id:asyncio.Event() for id in range(1,14)}
    async def run(id):
     started.append(id)
     started_events[id].set()
     await events[id].wait()
     with Session(db._engine) as s:
      j=s.get(KeywordCollectionJob,id);j.status='done';s.add(j);s.commit()
    e.run_collection_job=run
    await e._process_collection_jobs()
    await asyncio.wait_for(asyncio.gather(*(started_events[id].wait() for id in [1,2,3,4,5,7,8,9,10,11])),timeout=10)
    self.assertEqual(len(started),10);self.assertNotIn(6,started);self.assertNotIn(12,started)
    self.assertFalse(e.enqueue_collection_job(1))
    events[1].set()
    # Await the completion callback, not a 50ms timer that races Windows I/O.
    # No manual scheduler tick is called: automatic refill is still required.
    await asyncio.wait_for(started_events[6].wait(),timeout=10)
    self.assertIn(6,started);self.assertNotIn(13,started)
    e._running=False
    for t in e._collection_tasks.values():t.cancel()
    await asyncio.gather(*list(e._collection_tasks.values()),return_exceptions=True)
   finally:db._engine.dispose();db._engine=old
