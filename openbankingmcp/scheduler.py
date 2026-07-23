"""Small daily local scheduler; launchd keeps the process alive."""
from __future__ import annotations
import threading
from datetime import datetime, timedelta

class DailyScheduler:
    def __init__(self, callback, hour=3): self.callback,self.hour,self.timer=callback,hour,None
    def delay(self, now=None):
        now=now or datetime.now(); target=now.replace(hour=self.hour,minute=0,second=0,microsecond=0)
        if target <= now: target += timedelta(days=1)
        return (target-now).total_seconds()
    def start(self):
        self.timer=threading.Timer(self.delay(),self._run); self.timer.daemon=True; self.timer.start()
    def _run(self):
        try: self.callback()
        finally: self.start()
    def stop(self):
        if self.timer: self.timer.cancel()
