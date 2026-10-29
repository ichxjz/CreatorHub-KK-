import unittest
from app.relevance import relevant,clean_query,task_anchor
class RelevanceTest(unittest.TestCase):
 def test_numbered_question(self):self.assertEqual(clean_query('1. 母线槽多少钱一米？'),'母线槽多少钱一米?')
 def test_generic_price_needs_task_topic(self):
  terms=['多少钱一米','密集型母线槽','母线槽 vs 电缆','发热']
  self.assertTrue(relevant('母线槽价格与安装','多少钱一米',terms))
  self.assertFalse(relevant('全屋定制价格','多少钱一米',terms))
 def test_no_subject_in_title_is_not_recommendation(self):
  self.assertFalse(relevant('装修施工教程','母线槽防水',['母线槽防水']))
  self.assertTrue(relevant('母线槽防水安装','母线槽防水',['母线槽防水']))
