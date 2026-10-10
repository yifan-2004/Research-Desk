import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from app import Desk, Server


class DeskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'desk.sqlite3'
        self.desk = Desk(self.path, {})

    def tearDown(self):
        self.temp.cleanup()

    def test_sources_notes_tasks_persist_across_restart(self):
        source_id = self.desk.add('sources', {'title': 'Illumination', 'content': 'Low-light image enhancement', 'url': 'https://example.org/paper'})
        self.desk.add('notes', {'title': '实验', 'content': '低照度图像增强评测需要固定颜色空间。'})
        task_id = self.desk.add('tasks', {'title': 'Run evaluation'})
        self.desk.task(task_id, True)
        restored = Desk(self.path, {}).state()
        self.assertEqual(restored['sources'][0]['id'], source_id)
        self.assertEqual(restored['notes'][0]['title'], '实验')
        self.assertEqual(restored['tasks'][0]['done'], 1)
        self.desk.delete('sources', source_id)
        self.assertEqual(Desk(self.path, {}).state()['sources'], [])
        new_id = self.desk.add('sources', {'title': 'New source', 'content': 'A separate document.'})
        self.assertGreater(new_id, source_id)

    def test_empty_and_unsafe_inputs_rejected(self):
        for data in ({'title': '', 'content': 'hi'}, {'title': 'x', 'content': 'hi', 'url': 'javascript:alert(1)'}):
            with self.assertRaises(ValueError):
                self.desk.add('sources', data)
        with self.assertRaises(ValueError):
            self.desk.task(9, 'yes')
        with self.assertRaises(ValueError):
            self.desk.delete('sources', 99)

    def test_english_and_chinese_retrieval_source_ids(self):
        source_id = self.desk.add('sources', {'title': 'Low-light image enhancement', 'content': 'Low-light images require consistent metrics.'})
        note_id = self.desk.add('notes', {'title': '实验计划', 'content': '单目目标检测需要相机标定。'})
        self.assertEqual(self.desk.retrieve('low-light metrics')[0]['id'], f'S{source_id}')
        self.assertEqual(self.desk.retrieve('单目目标检测')[0]['id'], f'N{note_id}')
        self.assertEqual(self.desk.retrieve('unrelated vocabulary'), [])

    def test_offline_mode_never_calls_provider(self):
        self.desk.add('sources', {'title': 'SSIM', 'content': 'SSIM is an image similarity metric.'})
        with patch('urllib.request.urlopen') as request:
            answer = self.desk.chat({'message': 'SSIM'})
        request.assert_not_called()
        self.assertEqual(answer['mode'], 'offline')
        self.assertIn('不是 AI', answer['answer'])
        self.assertTrue(answer['sources'])

    def test_provider_payload_and_secret_handling(self):
        self.desk.config = {'endpoint': 'https://model.example/v1/chat/completions', 'model': 'test-model', 'key': 'test-secret'}
        self.desk.add('sources', {'title': 'PSNR', 'content': 'PSNR needs consistent pixel range.'})
        response = io.BytesIO(json.dumps({'choices': [{'message': {'content': 'Check pixel range [S1].'}}]}).encode())
        with patch('urllib.request.urlopen', return_value=response) as request:
            answer = self.desk.chat({'message': 'PSNR pixel range'})
        sent = request.call_args.args[0]
        payload = json.loads(sent.data)
        self.assertEqual(sent.get_header('Authorization'), 'Bearer test-secret')
        self.assertEqual(payload['model'], 'test-model')
        self.assertIn('[S1]', payload['messages'][1]['content'])
        self.assertIn('untrusted', payload['messages'][0]['content'])
        self.assertEqual(answer['mode'], 'connected')
        self.assertNotIn('test-secret', json.dumps(self.desk.state()))

    def test_real_local_chat_protocol_stub(self):
        captured = []

        class Stub(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body = json.dumps({'choices': [{'message': {'content': 'Local stub answer [S1].'}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        stub = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
        worker = threading.Thread(target=stub.serve_forever, daemon=True)
        worker.start()
        try:
            self.desk.add('sources', {'title': 'Protocol', 'content': 'Protocol test source.'})
            self.desk.config = {'endpoint': f'http://127.0.0.1:{stub.server_port}/v1/chat/completions', 'model': 'local-test'}
            answer = self.desk.chat({'message': 'Protocol'})
            self.assertEqual(answer['answer'], 'Local stub answer [S1].')
            self.assertEqual(captured[0]['model'], 'local-test')
            self.assertIn('Protocol test source.', captured[0]['messages'][1]['content'])
        finally:
            stub.shutdown()
            stub.server_close()
            worker.join()

    def test_remote_http_and_provider_error_handling(self):
        self.desk.config = {'endpoint': 'http://model.example/chat', 'model': 'x'}
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            self.desk.chat({'message': 'hello'})
        self.desk.config['endpoint'] = 'https://model.example/chat'
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('secret provider body')):
            with self.assertRaisesRegex(ValueError, '模型服务请求失败') as error:
                self.desk.chat({'message': 'hello'})
        self.assertNotIn('secret', str(error.exception))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = Server(('127.0.0.1', 0), Desk(Path(self.temp.name) / 'db.sqlite3', {}))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, path):
        return urllib.request.urlopen(self.base + path)

    def post(self, path, body, headers=None):
        options = {'Content-Type': 'application/json', 'X-Desk-Token': self.server.csrf}
        options.update(headers or {})
        return urllib.request.urlopen(urllib.request.Request(self.base + path, json.dumps(body).encode(), options))

    def test_server_smoke_assets_crud_chat_export(self):
        for path, expected in (('/', b'Research Desk'), ('/app.js', b'use strict'), ('/style.css', b'--teal')):
            with self.get(path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(expected, response.read())
                self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        with self.post('/api/sources', {'title': 'Test PSNR', 'content': 'PSNR pixel range.'}) as response:
            self.assertEqual(response.status, 200)
        with self.post('/api/chat', {'message': 'PSNR'}) as response:
            self.assertEqual(json.load(response)['sources'][0]['id'], 'S1')
        with self.get('/api/export') as response:
            exported = json.load(response)
            self.assertEqual(exported['format'], 'research-desk-v1')
            self.assertEqual(len(exported['sources']), 1)
            self.assertNotIn('csrf', exported)
        with self.post('/api/sources/1/delete', {}) as response:
            self.assertEqual(response.status, 200)
        with self.get('/api/state') as response:
            self.assertEqual(json.load(response)['sources'], [])

    def test_foreign_origin_and_csrf_and_host_rejected(self):
        for headers in ({'Origin': 'https://attacker.example'}, {'X-Desk-Token': 'wrong'}):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post('/api/tasks', {'title': 'bad'}, headers)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        request = urllib.request.Request(self.base + '/api/state', headers={'Host': 'attacker.example'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 403)
        error.exception.close()

    def test_malformed_unknown_and_oversize_requests(self):
        for path, body, code in (('/api/tasks', [], 400), ('/api/tasks', {'title': ''}, 400), ('/api/unknown', {}, 404)):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post(path, body)
            self.assertEqual(error.exception.code, code)
            error.exception.close()
        request = urllib.request.Request(self.base + '/api/tasks', b'{}', {'Content-Type': 'application/json', 'X-Desk-Token': self.server.csrf, 'Content-Length': '600000'})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.get('/app.py')
        self.assertEqual(error.exception.code, 404)
        error.exception.close()


if __name__ == '__main__':
    unittest.main()
