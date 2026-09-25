"""Bounded session history and ownership of temporary chat sandboxes."""
from collections import OrderedDict
from time import monotonic
from langchain_core.messages import HumanMessage, AIMessage
from app.sandbox import Sandbox


class SessionCapacityError(RuntimeError):
    pass


class Memory:
    def __init__(self, max_sessions=100, ttl_seconds=1800, clock=monotonic):
        self.sessions = OrderedDict()
        self.sandboxes = {}
        self.last_activity = {}
        self.active = set()
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self.clock = clock

    def expire(self):
        for session in list(self.sessions):
            if session not in self.active and self.clock() - self.last_activity[session] >= self.ttl_seconds:
                self.clear(session)

    def _touch(self, session):
        self.expire()
        if session not in self.sessions:
            while len(self.sessions) >= self.max_sessions:
                victim = next((key for key in self.sessions if key not in self.active), None)
                if victim is None:
                    raise SessionCapacityError('All chat sessions are busy')
                self.clear(victim)
            self.sessions[session] = []
        self.last_activity[session] = self.clock()
        self.sessions.move_to_end(session)

    def begin(self, session):
        self._touch(session)
        if session not in self.sandboxes:
            self.sandboxes[session] = Sandbox.create()
        self.active.add(session)
        return self.sandboxes[session]

    def end(self, session):
        self.active.discard(session)
        self.last_activity[session] = self.clock()

    def get(self, session):
        self.expire()
        return list(self.sessions.get(session, []))
    def add(self, session, user, assistant):
        self._touch(session)
        messages = self.get(session) + [HumanMessage(content=user), AIMessage(content=assistant)]
        # Six recent turns; also enforce a character ceiling (not a token counter).
        while len(messages) > 12 or sum(len(str(m.content)) for m in messages) > 24000:
            messages = messages[2:]
        self.sessions[session] = messages
        self.sessions.move_to_end(session)
    def clear(self, session):
        if session in self.active:
            raise RuntimeError('Cannot clear an active session')
        sandbox = self.sandboxes.pop(session, None)
        if sandbox is not None:
            sandbox.cleanup()
        self.sessions.pop(session, None)
        self.last_activity.pop(session, None)

    def close(self):
        for sandbox in self.sandboxes.values():
            sandbox.cleanup()
        self.sandboxes.clear()
        self.sessions.clear()
        self.last_activity.clear()
        self.active.clear()
