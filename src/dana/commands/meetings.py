from argparse import ZERO_OR_MORE
from dataclasses import dataclass, asdict, field
from datetime import datetime
import json
from timeit import repeat
from typing import Optional, List, Union, Tuple, Dict
from functools import wraps
import re

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import numpy as np

from .utils import CachedStore


@dataclass
class Meeting:
    name: str
    description: str
    participants: Dict[str, int]
    start: Union[str, datetime]
    url: Optional[str] = None
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
            md.append(f'*{self.description}*\n')
        if self.url:
            md.append(f'url: {self.url}')
        md.append(f'start: {self.start.strftime("%Y-%m-%d %H:%M")}')
        md.append(f'end: {self.end.strftime("%Y-%m-%d %H:%M") if self.end is not None else "-"}')
        if self.repeat:
            md.append(f'repeats every {self.repeat[0]} {self.repeat[1]}')
        md.append(f'\nparticipants:')
        for p in self.participants:
            md.append(f'* {p}')
        return '\n'.join(md)

    def trigger(self):
        """Generate a trigger object for the scheduler"""
        end = self.end.isoformat() if self.end else None
        if self.repeat:
            interval, unit = self.repeat
            print(self.start, self.end, unit, interval)
            return IntervalTrigger(start_date=self.start.isoformat(), end_date=end, **{unit: interval})
        else:
            return IntervalTrigger(start_date=self.start.isoformat(), end_date=end)

    def takes_minutes(self):
        """Pick a participant taking minutes"""
        if len(self.participants) < 3:
            return [np.random.choice(list(self.participants.values()))] * 3

        p = np.asarray(list(self.participants.keys()))
        print(p, '<<< pppp')
        print('weight >>>>>>>>>', self.weight)
        w = np.asarray(self.weight)
        # pick 3 users
        users = np.random.choice(p, 3, replace=False, p=w)
        # change weights (1st /10, 2nd /2)
        w[np.where(p==users[0])[0][0]] /= 10
        w[np.where(p==users[1])[0][0]] /= 2
        w /= w.sum()

        # self.participants[:] = p.tolist()
        self.weight[:] = w.tolist()
        print('weight <<<<<<<<<<', self.weight)

        return users

    def reminder(self):
        """Return a reminder message"""
        users = self.takes_minutes()

        # zl = f'*[url]({self.url})*\n' if self.url else ""
        msg = (
            f'**[{self.name}]({self.url or ""})** *starting now*\n\n'
            f'**{users[0]}** was randomly selected to take minutes (then **{users[1]}** or '
            f'**{users[2]}** if unavailable)\n'
        )
        return {
            'type': 'private',
            'to': list(self.participants.values()),
            'content': msg,
        }


def ensure_name(func):
    """Ensure the meeting requested exists"""

    @wraps(func)
    def wrapper(self, name, *args, **kwargs):
        if name not in self:
            return f'Meeting "{name}" does not exist'
        return func(self, name, *args, **kwargs)
    return wrapper


def return_exc(func):
    """Return the exception as a string"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            return str(e)
        else:
            return result
    return wrapper


class MeetingBot(CachedStore):
    def __init__(self, bot):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        super().__init__(bot._client, 'meeting')

    def init_data(self, data):
        for key, value in data.items():
            self[key] = meeting = Meeting(**value)
            self._add_job(meeting)

    def commit(self):
        data = json.dumps({k: asdict(v) for k, v in self.items()}, default=str)
        print(self._key, data)
        self._client.update_storage({'storage': {self._key: data}})

    @return_exc
    def execute(self, command, **kwargs):
        if command == 'add':
            name = ' '.join(kwargs['name'])
            start = re.match(r'<time:(.*)>', kwargs['start'])[1]
            end = re.match(r'<time:(.*)>', kwargs['end'])[1] if kwargs['end'] else None
            desc = ' '.join(kwargs['description']) if kwargs['description'] else None
            participants = re.findall(r'\@\*\*([\w\s]+)\*\*', ' '.join(kwargs['participants']))

            users = {user['full_name']: user['user_id'] for user in self._client.get_users()['members']
                     if user['full_name'] in participants}
        
            return self.add(
                name=name,
                description=desc,
                participants=users,
                start=start,
                end=end,
                url=kwargs['url'],
                repeat=kwargs['repeat'],
            )
        elif command == 'remove':
            return self.remove(' '.join(kwargs['name']))
        elif command == 'list':
            return self.list()
        elif command == 'info':
            return self.info(' '.join(kwargs['name']))
        elif command == 'edit':
            raise NotImplementedError
        else:
            return f'Unknown command "{command}"'

    def list(self):
        msg = ['# Meetings:']
        for idx, meeting in enumerate(self):
            msg.append(f'{idx}. {meeting}')
        return '\n'.join(msg)

    @ensure_name
    def info(self, name: str = None):
        return str(self[name])

    def add(self, **kwargs):
        meeting = Meeting(**kwargs)
        if meeting.name in self:
            return f':warning: Meeting {meeting.name} already exists!'
        self._add_job(meeting)
        self[meeting.name] = meeting
        self.commit()
        return str(meeting)

    @ensure_name
    def remove(self, name: str):
        print('remove scheduled job')
        self.scheduler.remove_job(name)
        print('remove from dict')
        del self[name]
        print('update db')
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
        func = lambda: self._client.send_message(meeting.reminder())
        self.scheduler.add_job(
            self._send_reminder, meeting.trigger(), id=meeting.name, args=(meeting,))
