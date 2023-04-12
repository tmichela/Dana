import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from functools import lru_cache, wraps
from itertools import chain
from math import isclose
from timeit import repeat
from typing import Dict, List, Optional, Tuple, Union

import holidays
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger as log

from .utils import CachedStore


COUNTRY = 'Germany'
PROVINCE = 'HH'


@lru_cache()
def public_holidays(year: int):
    h = holidays.CountryHoliday(COUNTRY, subdiv=PROVINCE, years=year)
    return h


def time_delta(time: time, delta: timedelta):
    return (datetime.combine(date(1, 1, 1), time) + delta).time()


@dataclass
class Meeting:
    """

    schedules:
        list of tuples with schedule definitions formatted as (day(s), hour, minute),
        e.g. ('Mon,Tue', 10, 0). If empty, the meeting will be triggered once at `start`
        time.
    """
    name: str
    description: str
    participants: Dict[str, int]
    start: Union[str, datetime]
    url: Optional[str] = None
    end: Optional[str] = None
    schedules: Optional[List[Tuple[int, str, int, int]]] = field(default_factory=dict)
    paused: bool = False
    weight: Optional[List[float]] = None
    participants_optional: Optional[Dict[str, int]] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.start, str):
            self.start = datetime.fromisoformat(self.start)
        if isinstance(self.end, str):
            self.end = datetime.fromisoformat(self.end)

        if self.weight is None:
            self.weight = [1. / len(self.participants)] * len(self.participants)

        # fix invalid data
        if not isclose(sum(self.weight), 1.):
            sum_w = sum(self.weight)
            self.weight[:] = [w / sum_w for w in self.weight]

        for p in list(self.participants_optional):
            if p in self.participants:
                del self.participants_optional[p]

    @property
    def status(self):
        if self.end is not None and self.end < datetime.now(tz=self.end.tzinfo):
            return 'expired'
        if not self.schedules and self.start < datetime.now(tz=self.start.tzinfo):
            return 'expired'
        return "active" if not self.paused else "paused"

    def __str__(self):
        md = [f'# {self.name}']
        if self.description:
            md.append(f'*{self.description}*\n')
        md.append(f'status: {self.status}')
        if self.url:
            md.append(f'url: {self.url}')
        md.append(f'start: {self.start.strftime("%Y-%m-%d %H:%M")}')
        md.append(f'end: {self.end.strftime("%Y-%m-%d %H:%M") if self.end is not None else "-"}')
        if self.schedules:
            sc = ', '.join(
                [f'every{" " + str(week) if week > 1 else ""} week on {week_days} at {hour:02}:{minute:02}'
                 for week, week_days, hour, minute in self.schedules]
            )
            md.append(f'Schedules: {sc}')
        md.append(f'\nparticipants:')
        for p in sorted(self.participants | self.participants_optional):
            md.append(f'* {p}{" (optional)" if p in self.participants_optional else ""}')
        return '\n'.join(md)

    def trigger(self):
        if self.schedules:
            triggers = {}
            for n, (week_interval, days, hour, minute) in enumerate(self.schedules):
                rem_time = time_delta(time(hour=hour, minute=minute), timedelta(minutes=-5))
                reminder = CronTrigger(day_of_week=days, hour=rem_time.hour, minute=rem_time.minute, start_date=self.start, end_date=self.end, timezone='Europe/Berlin')
                trigger = CronTrigger(day_of_week=days, hour=hour, minute=minute, start_date=self.start, end_date=self.end, timezone='Europe/Berlin')

                triggers[f'{self.name}.schedule-{n}'] = (trigger, week_interval)
                triggers[f'{self.name}.schedule-{n}.reminder'] = (reminder, week_interval)
            return triggers

        else:
            # single instance meeting
            trigger = DateTrigger(self.start)
            reminder = DateTrigger(self.start - timedelta(minutes=5))
            return {self.name: (trigger, 1), f'{self.name}.reminder': (reminder, 1)}

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

    def appointment(self):
        """Return an appointment message"""
        users = self.takes_minutes()
        msg = (
            f'**[{self.name}]({self.url or ""})** *starts now*\n\n'
            f'**{users[0]}** was randomly selected to take minutes (then **{users[1]}** or '
            f'**{users[2]}** if unavailable)\n'
        )
        return {
            'type': 'private',
            'to': [p for p in chain(self.participants.values(), self.participants_optional.values())],
            'content': msg,
        }

    def reminder(self):
        """Return a reminder message"""
        return {
            'type': 'private',
            'to': [p for p in chain(self.participants.values(), self.participants_optional.values())],
            'content': f'**[{self.name}]({self.url or ""})** *starts in 5 minutes*\n\n'
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
    def __init__(self, bot, cache_path):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        super().__init__(bot._client, cache_path)
        log.info('Meeting bot initialized')

    def init_data(self, data):
        for key, value in data.items():
            self[key] = meeting = Meeting(**value)
            if not meeting.paused:
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

        name = ' '.join(kwargs.get('name', []))

        if command == 'add':
            start = re.match(r'<time:(.*)>', kwargs['start'])[1]
            end = re.match(r'<time:(.*)>', kwargs['end'])[1] if kwargs['end'] else None
            desc = ' '.join(kwargs['description']) if kwargs['description'] else None
            participants = re_participants.findall(' '.join(kwargs['participants']))
            optional = re_participants.findall(' '.join(kwargs['optional'] or []))

            schedules = []
            for days_of_week, time_of_day in kwargs.get('schedule', []):
                days_of_week, _, week_interval = days_of_week.lower().partition('/')
                hour, _, minute = time_of_day.partition(':')
                schedules.append((int(week_interval or 1), days_of_week, int(hour), int(minute)))

            return self.add(
                name=name,
                description=desc,
                participants=self._zulip_users(users=participants),
                start=start,
                end=end,
                url=kwargs['url'],
                schedules=schedules,
                participants_optional=self._zulip_users(users=optional),
            )
        elif command == 'remove':
            return self.remove(name)
        elif command == 'list':
            return self.list()
        elif command == 'info':
            return self.info(name)
        elif command == 'edit':
            raise NotImplementedError
        elif command in ('add_participant', 'remove_participant'):
            participants = re_participants.findall(' '.join(kwargs['participants']))
            kw = {'optional': kwargs['optional']} if command == 'add_participant' else {}
            return getattr(self, command)(' '.join(kwargs['name']), participants, **kw)
        elif command == 'pause':
            return self.pause(name)
        elif command == 'resume':
            return self.resume(name)
        else:
            return f'Unknown command "{command}"'

    def list(self):
        msg = ['# Meetings:']
        for idx, (name, meeting) in enumerate(self.items()):
            msg.append(f'{idx}. [{meeting.status}] {name}')
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
    def add_participant(self, name: str, users: List[str], optional=False):
        """
        name, str: Meeting name
        users, list[str]: users to add
        optional, bool: are the additional users optional participants
        """
        log.info(f'Adding new participant {users} to meeting {name}')
        meeting = self[name]

        if any(u in (meeting.participants | meeting.participants_optional) for u in users):
            return  # user already participates in meeting

        if optional == False:
            meeting.participants.update(self._zulip_users(users=users))
            meeting.weight += [max(meeting.weight)] * (len(meeting.participants) - len(meeting.weight))
            sum_weight = sum(meeting.weight)
            meeting.weight[:] = [w / sum_weight for w in meeting.weight]
            assert len(meeting.weight) == len(meeting.participants)
        else:
            meeting.participants_optional.update(self._zulip_users(users=users))
        self.commit()
        return str(meeting)

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

        sum_weight = sum(meeting.weight)
        meeting.weight[:] = [w / sum_weight for w in meeting.weight]
        assert len(meeting.weight) == len(meeting.participants)
        self.commit()
        return str(meeting)

    @ensure_name
    def pause(self, name: str):
        # TODO add argument to pause the meeting for <duration>
        log.info(f'Pause reminders for meeting: {name}')
        meeting = self[name]
        if meeting.paused:
            return f'Meeting "{name}" is already paused.'

        meeting.paused = True
        # remove all jobs for that meeting
        self._remove_job(meeting)
        self.commit()
        return f'Meeting "{name}" is paused.'

    @ensure_name
    def resume(self, name: str):
        log.info(f'Resume reminders for meeting: {name}')
        meeting = self[name]
        if not meeting.paused:
            return f'Meeting "{name}" is not currently paused.'
        
        meeting.paused = False
        # add jobs for that meeting
        self._add_job(meeting)
        self.commit()
        return f'Meeting "{name}" is resumed.'

    def _run_trigger_this_week(self, meeting, week_interval, delta=0):
        # start day
        start_day = datetime(meeting.start.year, meeting.start.month, meeting.start.day)
        # seconds since meeting start
        dt = datetime.now().timestamp() + delta - start_day.timestamp()
        # number of weeks since start of meeting
        n_weeks = dt // 604800  # 604800: number of seconds in a week
        return (n_weeks % week_interval) == 0

    def _skip(self, meeting, week_interval):
        if not self._run_trigger_this_week(meeting, week_interval):
            return True

        today = date.today()
        if today in public_holidays(today.year):
            return True

        return False

    def _send_reminder(self, meeting: Meeting, week_interval: int):
        if self._skip(meeting, week_interval):
            return
        r = self._client.send_message(meeting.reminder())
        log.info(f'Reminder sent for {meeting.name}: {r}')

    def _send_appointment(self, meeting: Meeting, week_interval: int):
        if self._skip(meeting, week_interval):
            return
        r = self._client.send_message(meeting.appointment())
        log.info(f'Appointment sent for {meeting.name}: {r}')
        self.commit()  # save updated weights

    def _remove_job(self, meeting: Meeting):
        job_ids = [job.id for job in self.scheduler.get_jobs()]
        for job in job_ids:
            if job.startswith(meeting.name):
                self.scheduler.remove_job(job)

    def _add_job(self, meeting: Meeting):
        triggers = meeting.trigger()
        log.info(f'Adding job for {meeting.name} with triggers:\n{repr(triggers)}')

        for trigger_id, (trigger, week_interval) in triggers.items():
            func = self._send_reminder if trigger_id.endswith('.reminder') else self._send_appointment
            self.scheduler.add_job(func, trigger, id=trigger_id, args=(meeting, week_interval))
