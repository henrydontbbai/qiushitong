import unittest
from unittest.mock import patch

from scripts.sync_daily_matches import MatchSyncManager


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeDB:
    def __init__(self):
        self.connection = FakeConnection()

    def _get_conn(self):
        return self.connection


class FakeSpider:
    pass


class SyncDailyMatchesTest(unittest.TestCase):
    def test_connection_uses_existing_get_conn_method(self):
        with patch('scripts.sync_daily_matches.ChinaLotterySpider', return_value=FakeSpider()):
            manager = MatchSyncManager()
        manager.db = FakeDB()

        self.assertTrue(manager.test_connection())
        self.assertTrue(manager.db.connection.closed)


if __name__ == '__main__':
    unittest.main()
