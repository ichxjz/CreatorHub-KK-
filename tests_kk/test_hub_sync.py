import asyncio,unittest
from unittest.mock import patch,MagicMock,AsyncMock
from types import SimpleNamespace
import app
from app import hub_sync as hub
class HubSyncTest(unittest.IsolatedAsyncioTestCase):
 async def test_deduplicate_and_partial_result(self):
  session=MagicMock();session.__enter__.return_value=session;session.get.return_value=SimpleNamespace(status='active',storage_state='test',creator_storage_state='')
  gate=asyncio.Event()
  async def works(id):await gate.wait();return {'ok':True,'fetched':3}
  main=SimpleNamespace(browser=SimpleNamespace(lock_for=lambda k:asyncio.Lock()),engine=SimpleNamespace(risk=SimpleNamespace(preflight=lambda *a:SimpleNamespace(allowed=True)),_guarded_read_dict=AsyncMock(return_value={'ok':True})),OperationKind=SimpleNamespace(READ_HEAVY='heavy',READ_LIGHT='light'),sync_account_works=works,_sync_follows_impl=AsyncMock(return_value={'ok':True}),sync_dm=AsyncMock(return_value={'ok':False,'error':'unsupported'}))
  with patch.object(app,'main',main,create=True),patch.object(hub,'get_session',return_value=session):
   first=hub.schedule(999);task=hub.tasks[999];second=hub.schedule(999,True);self.assertIs(first,second);self.assertIs(task,hub.tasks[999]);gate.set();await task
   self.assertEqual(first['status'],'partial');self.assertEqual(len(first['results']),5);self.assertFalse(first['results'][-1]['ok']);self.assertIs(first,hub.schedule(999))
  hub.states.pop(999);hub.tasks.pop(999)
