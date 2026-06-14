import unittest
from unittest.mock import patch

from scripts.database import PredictionDatabase


class FakeCursor:
    def __init__(self):
        self.executed_sql = None
        self.executed_params = None
        self.closed = False

    def execute(self, sql, params=None):
        self.executed_sql = sql
        self.executed_params = params

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.autocommit = None
        self.committed = False
        self.closed = False

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class DatabaseSavePredictionTest(unittest.TestCase):
    def test_save_prediction_writes_user_id_and_username_columns(self):
        fake_conn = FakeConnection()
        db = PredictionDatabase()

        with patch('scripts.database.psycopg2.connect', return_value=fake_conn):
            ok = db.save_prediction({
                'prediction_id': 'p1',
                'prediction_mode': 'Classic',
                'user_id': None,
                'username': 'local_guest',
                'home_team': 'A',
                'away_team': 'B',
                'league_name': 'L',
                'match_time': None,
                'home_odds': 2.0,
                'draw_odds': 3.0,
                'away_odds': 4.0,
                'predicted_result': '主胜',
                'prediction_confidence': 8,
                'ai_analysis': 'classic',
                'user_ip': '127.0.0.1',
            })

        self.assertTrue(ok)
        self.assertIn('user_id', fake_conn.cursor_obj.executed_sql)
        self.assertIn('username', fake_conn.cursor_obj.executed_sql)
        self.assertEqual(fake_conn.cursor_obj.executed_params['username'], 'local_guest')


if __name__ == '__main__':
    unittest.main()
