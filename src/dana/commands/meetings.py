import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import wraps
from timeit import repeat
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger as log

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
        if isinstance(self.end, str):
            self.end = datetime.fromisoformat(self.end)

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
        for p in sorted(self.participants):
            md.append(f'* {p}')
        return '\n'.join(md)

    def trigger(self):
        """Generate a trigger object for the scheduler"""
        end = self.end.isoformat() if self.end else None
        if self.repeat:
            interval, unit = self.repeat
            trigger = IntervalTrigger(start_date=self.start.isoformat(), end_date=end, **{unit: interval})
        else:
            trigger = IntervalTrigger(start_date=self.start.isoformat(), end_date=end)
        log.info(f'trigger: {trigger}')
        return trigger

    def takes_minutes(self):
        """Pick a participant taking minutes"""
        if len(self.participants) < 3:
            return [np.random.choice(list(self.participants.keys()))] * 3

        p = np.asarray(list(self.participants.keys()))
        w = np.asarray(self.weight)
        # pick 3 users
        users = np.random.choice(p, 3, replace=False, p=w)
        # change weights (1st /10, 2nd /2)
        w[np.where(p==users[0])[0][0]] /= 10
        w[np.where(p==users[1])[0][0]] /= 2
        w /= w.sum()

        log.info(f'{self.name} takes minutes: {users}\nold weights: {self.weight}\nnew weights: {w}')
        self.weight[:] = w

        return users

    def reminder(self):
        """Return a reminder message"""
        users = self.takes_minutes()

        msg = (
            f'**[{self.name}]({self.url or ""})** *starts now*\n\n'
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
            import traceback
            return traceback.format_exc()
        else:
            return result
    return wrapper


class MeetingBot(CachedStore):
    def __init__(self, bot):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        super().__init__(bot._client, 'meeting')
        log.info('Meeting bot initialized')

    def init_data(self, data):
        for key, value in data.items():
            self[key] = meeting = Meeting(**value)
            self._add_job(meeting)

    def commit(self):
        log.debug(f'Update storage for meeting with {len(self)} meetings')
        data = json.dumps({k: asdict(v) for k, v in self.items()}, default=str)
        self._client.update_storage({'storage': {self._key: data}})

    def _zulip_users(self, users=None):
        _users = self._client.get_users()['members']
        if users is not None:
            if isinstance(users, str):
                users = [users]
            return {u['full_name']: u['user_id'] for u in _users if u['full_name'] in users}
        return {u['full_name']: u['user_id'] for u in _users}

    @return_exc
    def execute(self, command, **kwargs):
        log.debug(f'Executing command {command} with args {kwargs}')
        re_participants = re.compile(r'\@\*\*([\w\s\']+)\*\*')

        if command == 'add':
            name = ' '.join(kwargs['name'])
            start = re.match(r'<time:(.*)>', kwargs['start'])[1]
            end = re.match(r'<time:(.*)>', kwargs['end'])[1] if kwargs['end'] else None
            desc = ' '.join(kwargs['description']) if kwargs['description'] else None
            participants = re_participants.findall(' '.join(kwargs['participants']))
        
            return self.add(
                name=name,
                description=desc,
                participants=self._zulip_users(users=participants),
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
        elif command in ('add_participant', 'remove_participant'):
            participants = re_participants.findall(' '.join(kwargs['participants']))
            return getattr(self, command)(' '.join(kwargs['name']), participants)
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
        log.info(f'Adding meeting:\n{meeting}')
        if meeting.name in self:
            return f':warning: Meeting {meeting.name} already exists!'
        self._add_job(meeting)
        self[meeting.name] = meeting
        self.commit()
        return str(meeting)

    @ensure_name
    def remove(self, name: str):
        log.info(f'Removing meeting {name}')
        self.scheduler.remove_job(name)
        del self[name]
        self.commit()

    @ensure_name
    def edit(self, name: str, **kwargs):
        log.info(f'Editing meeting {name} with {kwargs}')
        meeting = self[name]
        for key, value in kwargs.items():
            if key == 'participants':
                meeting.weight = [1. / len(value)] * len(value)
                # TODO retain weights for existing participants
            setattr(meeting, key, value)
        self.commit()

    @ensure_name
    def add_participant(self, name: str, users: str):
        log.info(f'Adding new participant {users} to meeting {name}')
        meeting = self[name]

        if any(u in meeting.participants for u in users):
            return  # user already participates in meeting

        meeting.participants.update(self._zulip_users(users=users))
        meeting.weight += [max(meeting.weight)] * (len(meeting.participants) - len(meeting.weight))
        sum_weight = sum(meeting.weight)
        meeting.weight[:] = [w / sum_weight for w in meeting.weight]
        assert len(meeting.weight) == len(meeting.participants)
        self.commit()

    @ensure_name
    def remove_participant(self, name: str, users: str):
        log.info(f'Remove participant {users} from meeting {name}')
        meeting = self[name]

        for user in users:
            if user not in meeting.participants:
                continue
            idx = list(meeting.participants).index(user)
            meeting.participants.pop(user)
            meeting.weight.pop(idx)
        assert len(meeting.weight) == len(meeting.participants)
        self.commit()

    def _send_reminder(self, meeting: Meeting):
        r = self._client.send_message(meeting.reminder())
        log.info(f'Reminder sent for {meeting.name}: {r}')
        self.commit()  # save updated weights

    def _add_job(self, meeting: Meeting):
        log.info(f'Adding job for {meeting.name} with trigger:\n{repr(meeting.trigger())}')
        self.scheduler.add_job(
            self._send_reminder, meeting.trigger(), id=meeting.name, args=(meeting,))
