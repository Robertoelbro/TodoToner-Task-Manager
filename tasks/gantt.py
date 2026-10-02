from datetime import timedelta
from math import ceil
from django.utils import timezone


def build_timeline(tasks, date_from=None, date_to=None):
    today = timezone.localdate()
    start = date_from or min((t.start_date for t in tasks), default=date_to or today)
    end = date_to or max((t.deadline for t in tasks), default=start + timedelta(days=13))
    end = max(start, end)
    days = (end - start).days + 1
    # At most 90 date columns, including for long-running projects.
    step = max(1, ceil(days / 90))
    ticks = []
    for offset in range(0, days, step):
        length = min(step, days - offset)
        ticks.append({'date': start + timedelta(days=offset),
                      'width': format(length * 100 / days, '.6f')})
    rows = []
    for task in tasks:
        left = max(start, task.start_date)
        right = min(end, task.deadline)
        if left > right:
            continue
        rows.append({'task': task, 'left': format((left - start).days * 100 / days, '.6f'),
                     'width': format(((right - left).days + 1) * 100 / days, '.6f'),
                     'days': (task.deadline - task.start_date).days + 1})
    today_left = format((today - start).days * 100 / days, '.6f') if start <= today <= end else None
    return {'start': start, 'end': end, 'ticks': ticks, 'rows': rows,
            'step': step, 'today_left': today_left, 'min_width': max(660, len(ticks) * 64)}

