import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

class PreviewTests(unittest.TestCase):
    def load(self):
        path=Path(__file__).with_name('visual_preview.py')
        self.assertTrue(path.is_file(), 'Visual preview implementation is missing')
        spec=importlib.util.spec_from_file_location('visual_preview',path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    def test_four_readable_panels(self):
        m=self.load()
        with tempfile.TemporaryDirectory() as d:
            paths=m.render_panels(Path(d))
            self.assertEqual(len(paths),4)
            for path in paths:
                with Image.open(path) as im:
                    self.assertEqual(im.size,(1080,1440))
                self.assertLess(path.stat().st_size,10*1024*1024)
    def test_caption_is_labelled_and_links_to_source(self):
        m=self.load()
        self.assertLessEqual(len(m.CAPTION),1024)
        for value in ['preview','6 September 2026','per biopsy','42698384','PMC13545652']:
            self.assertIn(value,m.CAPTION)
    def test_multipart_contains_four_attachments(self):
        m=self.load()
        with tempfile.TemporaryDirectory() as d:
            paths=m.render_panels(Path(d))
            body,content_type=m.make_payload('test-chat',paths)
            self.assertIn(b'name="media"',body)
            self.assertIn(b'test-chat',body)
            for i in range(4):
                self.assertIn(f'attach://panel{i}'.encode(),body)
                self.assertIn(f'name="panel{i}"'.encode(),body)
            self.assertTrue(content_type.startswith('multipart/form-data; boundary='))
    def test_acceptance_requires_four_messages(self):
        m=self.load()
        result={'ok':True,'result':[{'message_id':i,'media_group_id':'x','chat':{'id':123}} for i in range(4)]}
        self.assertEqual(m.validate_response(result,'123')['accepted_images'],4)
        for malformed in [{'ok':False},{'ok':True,'result':[]},{'ok':True,'result':result['result'][:3]}]:
            with self.assertRaises(RuntimeError): m.validate_response(malformed,'123')
        with self.assertRaises(RuntimeError): m.validate_response(result,'124')
    def test_missing_secrets_fail_before_network(self):
        m=self.load()
        with patch.object(m.urllib.request,'urlopen') as opener:
            with self.assertRaises(RuntimeError): m.send_album('', '', [])
            opener.assert_not_called()
    def test_failed_send_does_not_retry_or_expose_token(self):
        m=self.load()
        with tempfile.TemporaryDirectory() as d:
            paths=m.render_panels(Path(d))
            with patch.object(m.urllib.request,'urlopen',side_effect=TimeoutError('secret-test')) as opener:
                with self.assertRaises(RuntimeError) as cm: m.send_album('secret-test','123',paths)
                self.assertNotIn('secret-test',str(cm.exception))
                self.assertEqual(opener.call_count,1)
if __name__=='__main__': unittest.main()
