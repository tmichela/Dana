from argparse import ZERO_OR_MORE
from dataclasses import dataclass, asdict, field
from datetime import datetime
import json
from timeit import repeat
from typing import Optional, List, Union, Tuple
from functools import wraps

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import numpy as np

from .utils import CachedStore


@dataclass
class Meeting:
    name: str
    description: str
    participants: List[str]
    start: Union[str, datetime]
    zoom_link: Optional[str] = None
    end: Optional[str] = None
    repeat: Optional[Tuple[int, str]] = None
    paused: bool = False
    weight: Optional[List[float]] = None

    def __post_init__(self):
        if isinstance(self.start, str):
            self.start = datetime.fromisoformat(self.start)

        if self.weight is None:
            self.weight = [1. / len(self.participants)] * len(self.participants)

    def __str__(self):
        md = [f'# {self.name}']
        if self.description:
            md.append(f'*{self.description}*')
        md.append(f'start: {self.start.strftime("%Y-%m-%d %H:%M")}')
        md.append(f'end: {self.end.strftime("%Y-%m-%d %H:%M") or "-"}')
        if self.zoom_link:
            md.append(f'url: {self.zoom_link}')
        # if self.repeat:
        #     md.append(f'repeat: {self.repeat}')
        md.append(f'participants:')
        for p in self.participants:
            md.append(f'* {p.strip("@*")}')
        return '\n'.join(md)

    def trigger(self):
        """Generate a trigger object for the scheduler"""
        if self.repeat:
            interval, unit = self.repeat
            return IntervalTrigger(start_date=self.start, end_date=self.end, **{unit: interval})
        else:
            return IntervalTrigger(start_date=self.start, end_date=self.end)

    def takes_minutes(self):
        """Pick a participant taking minutes"""
        if len(self.participants) < 3:
            return [np.random.choice(self.participants)] * 3

        p = np.asarray(self.participants)
        w = np.asarray(self.weight)
        # pick 3 users
        users = np.random.choice(p, 3, replace=False, p=w)
        # change weights (1st /10, 2nd /2)
        w[np.where(p==users[0])[0][0]] /= 10
        w[np.where(p==users[1])[0][0]] /= 2
        w /= w.sum()

        self.participants[:] = p.tolist()
        self.weight[:] = w.tolist()

        return users

    def reminder(self):
        """Return a reminder message"""
        users = self.takes_minutes()

        zl = f'*[zoom link]({self.zoom_link})*\n' if self.zoom_link else ""
        msg = (
            f'**{self.name}** *starting now*\n\n'
            f'{zl}'
            f'{users[0]} was chosen to take minutes (or {users[1]} or '
            f'{users[2]} if not available)\n'
        )
        return {
            'type': 'private',
            'to': self.participants,
            'content': msg,
        }


def ensure_name(func):
    """Ensure the meeting requested exists"""

    @wraps(func)
    def wrapper(self, name, *args, **kwargs):
        if name not in self:
            return f'Meeting "{name}" does not exist'
        return func(self, *args, **kwargs)
    return wrapper


class MeetingBot(CachedStore):
    def __init__(self, bot):
        super().__init__(bot._client, 'meeting')

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def init_data(self, data):
        for key, value in data.items():
            self[key] = meeting = Meeting(**value)
            self._add_job(meeting)

    def commit(self):
        data = json.dumps({k: asdict(v) for k, v in self.items()}, default=str)
        self._client.update_storage({'storage': {self._key: data}})

    def list(self):
        msg = ['# Meetings:']
        for idx, meeting in enumerate(self):
            msg.append(f'{idx}. {meeting}')
        return '\n'.join(msg)

    @ensure_name
    def details(self, name: str):
        return str(self[name])

    def add(self, **kwargs):
        meeting = Meeting(**kwargs)
        if meeting.name in self:
            return f'Meeting {meeting.name} already exists'
        self._add_job(meeting)
        self[meeting.name] = meeting
        self.commit()

    @ensure_name
    def remove(self, name: str):
        self.scheduler.remove_job(name)
        del self[name]
        self.commit()

    @ensure_name
    def edit(self, name: str, **kwargs):
        meeting = self[name]
        for key, value in kwargs.items():
            if key == 'participants':
                meeting.weight = np.ones(len(value), dtype=float)
                # TODO retain weights for existing participants
            setattr(meeting, key, value)
        self.commit()

    def _send_reminder(self, meeting):
        self._client.send_message(meeting.reminder())
        self.commit()  # save updated weights

    def _add_job(self, meeting):
        self.scheduler.add_job(
            self._send_reminder, meeting.trigger(), id=meeting.name, args=(meeting,))
