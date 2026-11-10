"""Thread-safe lease producer: an independent sender never renews a stuck loop."""
import threading


class LeasePump:
    def __init__(self,session):
        self.session=session;self.sequence=0;self.updated=None;self.permits={};self.lock=threading.Lock()

    def touch(self,permits,now):
        with self.lock:self.permits=dict(permits);self.updated=now

    def packet(self,now):
        with self.lock:
            if self.updated is None or not 0<=now-self.updated<.15:return None
            self.sequence+=1
            return dict(session=self.session,sequence=self.sequence,expires=now+.25,permits=dict(self.permits))
