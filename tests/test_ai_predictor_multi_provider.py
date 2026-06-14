import unittest
from unittest.mock import patch

from scripts.ai_predictor import AIFootballPredictor


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = 'fake response'

    def json(self):
        return self._payload


class AIPredictorMultiProviderTest(unittest.TestCase):
    def test_openai_compatible_uses_chat_completions_protocol(self):
        predictor = AIFootballPredictor(
            api_key='test-key',
            model_name='gpt-test',
            provider='openai_compatible',
            base_url='https://example.test/v1'
        )

        with patch('scripts.ai_predictor.requests.post', return_value=FakeResponse({
            'choices': [{'message': {'content': 'openai ok'}}]
        })) as post:
            result = predictor._call_ai_model('hello', max_retries=1)

        self.assertEqual(result, 'openai ok')
        self.assertEqual(post.call_args.args[0], 'https://example.test/v1/chat/completions')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer test-key')
        self.assertEqual(post.call_args.kwargs['json']['model'], 'gpt-test')
        self.assertEqual(post.call_args.kwargs['json']['messages'][1]['content'], 'hello')

    def test_gemini_uses_generate_content_protocol(self):
        predictor = AIFootballPredictor(
            api_key='gemini-key',
            model_name='gemini-test',
            provider='gemini',
            base_url='https://generativelanguage.googleapis.com/v1beta'
        )

        with patch('scripts.ai_predictor.requests.post', return_value=FakeResponse({
            'candidates': [{'content': {'parts': [{'text': 'gemini ok'}]}}]
        })) as post:
            result = predictor._call_ai_model('hello', max_retries=1)

        self.assertEqual(result, 'gemini ok')
        self.assertEqual(
            post.call_args.args[0],
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent'
        )
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'gemini-key')
        self.assertEqual(post.call_args.kwargs['json']['contents'][0]['parts'][0]['text'], 'hello')


if __name__ == '__main__':
    unittest.main()
