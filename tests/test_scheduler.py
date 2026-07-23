from datetime import datetime
from openbankingmcp.scheduler import DailyScheduler
from openbankingmcp.retention import enforce

def test_scheduler_waits_until_next_occurrence():
    scheduler=DailyScheduler(lambda:None,hour=3)
    assert 0 < scheduler.delay(datetime(2026,1,1,2,0)) <= 3600
    assert 0 < scheduler.delay(datetime(2026,1,1,4,0)) <= 23*3600
