import calendar
import io
from datetime import datetime


def format_calendar(cal: calendar.Calendar, year: str, month: int) -> str:
    with io.StringIO() as out:
        write = lambda data: out.write(f'{data}\n')

        for n, week in enumerate(cal.monthdatescalendar(year, month)):
            if n == 0:
                write(f"{week[-1].strftime('%B')} {year}")
                write('Week | ' + calendar.weekheader(3))
            week_nr = week[0].isocalendar().week
            days = ''.join(f'{day.day:>4}' if day.month == month else '    ' for day in week)
            write(f'{week_nr:>4} |{days}')
        return out.getvalue()


def make_calendar(year=None, month=None, start_sunday=False):
    full_year = year is not None and month is None
    year = year or datetime.today().year
    month = month or datetime.today().month

    if not (1 <= year <= 99999):
        return f'Invalid year: {year} :face_with_monocle:'
    if not (1 <= month <= 12):
        return f'Invalid month: {month} :face_with_monocle:'

    firstweekday = calendar.SUNDAY if start_sunday else calendar.MONDAY
    calendar.setfirstweekday(firstweekday)
    cal = calendar.Calendar()

    if full_year:
        cal_str = '\n'.join(format_calendar(cal, year, m) for m in range(1, 13))
    else:
        cal_str = format_calendar(cal, year, month)
    return f'```text\n{cal_str}\n```'
