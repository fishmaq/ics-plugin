import datetime
from dateutil.relativedelta import relativedelta
import json
import subprocess

import icalendar
import pytz

# this script is based on https://github.com/klemensschindler/icalfilter/blob/master/icalfilter.py (18.07.2025)
# REQUIREMENTS: pip install pytz icalendar && sudo apt install syncevolution

utc = pytz.utc

# target .ics file location
# TODO: use parameter or env var for this instead
TARGET_ICS_LOCATION = '/home/itsv.org.sv-services.at/martin.cerny@itsv.at/playground/ics-plugin/test.ics'
regular_events_arr = []
master_events_arr = []
override_events_dict = {}

# get the date of this week's monday and sunday, to only display events that are happening this week
today = datetime.datetime.today()
first_day_of_curr_week = (
        datetime.datetime(year=today.year, month=today.month, day=today.day, hour=0, minute=0, second=0) -
        datetime.timedelta(days=datetime.datetime.now().isocalendar().weekday - 1))
last_day_of_curr_week = (first_day_of_curr_week +
                         datetime.timedelta(days=6))
print(first_day_of_curr_week)


def sync_ics():
    # TODO: add some sort of test !!!!
    print("syncing ICS file...")

    # TODO: improve readability
    subprocess.run(
        # TODO: explain why this reformat is needed
        # start file with BEGIN:VCALENDAR and end it with END:VCALENDAR, remove all other occurrences of it
        "echo BEGIN:VCALENDAR > " + TARGET_ICS_LOCATION + "&& syncevolution --export - backend=evolution-calendar | "
                                                          "sed '/^BEGIN:VCALENDAR/d' | sed '/^END:VCALENDAR/d' >> " +
        TARGET_ICS_LOCATION + " && echo END:VCALENDAR >> " + TARGET_ICS_LOCATION,
        shell=True,
        executable="/bin/bash")
    print("sync done!")


def handle_if_recurring_event(event_to_check):
    # TODO: explain the difference between master and override events
    if 'RRULE' in event_to_check:
        # if there is a recurrence rule, this means, that it is the master event
        master_events_arr.append(event_to_check)
        return True
    elif 'RECURRENCE-ID' in event_to_check:
        # if there is a recurrence-id, this means, that it's an override event
        if event_to_check['UID'] not in override_events_dict:
            override_events_dict[(event_to_check['UID'])] = []
        override_events_dict[(event_to_check['UID'])].append(event_to_check)
        return True
    else:
        return False


# check if the start date is relevant in this week
def active_start_date(start_date):
    active = False

    if type(start_date) == datetime.datetime:
        if start_date.tzinfo is None or start_date.tzinfo.utcoffset(start_date) is None:
            start_date = utc.localize(start_date)
        # check if event is in the current week
        active = utc.localize(first_day_of_curr_week) <= start_date <= utc.localize(
            last_day_of_curr_week)
    elif type(start_date) == datetime.date:
        # check if event is in the current week
        active = (datetime.date(first_day_of_curr_week.year, first_day_of_curr_week.month,
                                first_day_of_curr_week.day) <= start_date
                  <= datetime.date(
                    last_day_of_curr_week.year, last_day_of_curr_week.month,
                    last_day_of_curr_week.day))
    else:
        print('')

    return active


def handle_regular_if_active(event_to_check):
    start_date = event_to_check['dtstart'].dt

    if active_start_date(start_date) and ('STATUS' in event_to_check and event_to_check['STATUS'] != 'CANCELLED'):
        regular_events_arr.append(event_to_check)


def map_event(event):
    out_dict = {}

    if 'summary' in event:
        out_dict['title'] = event['summary']
    else:
        out_dict['title'] = '(no title)'

    out_dict['status'] = event['status']
    out_dict['start'] = event['DTSTART'].dt.strftime('%d.%m.%Y %H:%M')

    if event['dtend'] is not None:
        out_dict['end'] = event['DTEND'].dt.strftime('%d.%m.%Y %H:%M')

    if 'RRULE' in event:
        rrule = event['RRULE']
        if 'UNTIL' in rrule and len(rrule['UNTIL']) == 1:
            out_dict['until'] = rrule['UNTIL'][0].strftime('%d.%m.%Y %H:%M')
            out_dict['freq'] = rrule['FREQ'][0]

    # TODO: comment in and add more data if needed (organizer? location?)
    # if item['description'] is not None:
    #     data['description'] = item['description']
    # data['attendee'] = item['attendee']

    return out_dict


# TODO: add better comments
def map_recurring_event(master_event, override_event_arr):
    out_dict_arr = []
    exclude_date_arr = []

    # sort out irrelevant override events
    override_event_arr = [event for event in override_event_arr if active_start_date(event['dtstart'].dt)]
    if 'EXDATE' in master_event:
        if type(master_event['exdate']) is list:
            for exclude_date_entry in master_event['exdate']:
                for date in exclude_date_entry.dts:
                    exclude_date_arr.append(date)
        else:
            for date in master_event['exdate'].dts:
                exclude_date_arr.append(date)

    if type(master_event['dtstart'].dt) == datetime.datetime:
        max_date = utc.localize(
            last_day_of_curr_week)
        master_event_start = master_event['dtstart'].dt
        master_event_end = master_event['dtend'].dt
        date = master_event_start

        while date <= max_date:
            if date not in exclude_date_arr and by_day(master_event['rrule']['byday'], date):
                # if there is an override event for the day then use the override event
                filtered_override_event_arr = [event for event in override_event_arr if
                                               event['dtstart'].dt == date]
                if not len(filtered_override_event_arr) > 0:
                    # generate object
                    out_dict_arr.append({
                        'title': master_event['summary'],
                        # use date from loop and time from master_event
                        'start': datetime.datetime(date.year, date.month, date.day,
                                                   master_event_start.hour,
                                                   master_event_start.minute),
                        'end': datetime.datetime(date.year, date.month, date.day,
                                                 master_event_end.hour, master_event_end.minute)}
                    )
                else:
                    # use override event
                    override_event = filtered_override_event_arr[0]
                    out_dict_arr.append({
                        'title': override_event['summary'],
                        # use date from loop and time from master_event
                        'start': override_event['dtstart'].dt,
                        'end': override_event['dtstart'].dt}
                    )

            interval = 1
            if 'INTERVAL' in master_event['rrule']:
                interval = master_event['rrule']['interval'][0]

            i = 0
            while i < interval:
                match master_event['rrule']['freq'][0]:
                    case 'MONTHLY':
                        date = date + relativedelta(months=1)
                    case 'YEARLY':
                        break
                    case 'WEEKLY':
                        # when the event has a by day attribute, each day of the week has to be checked for byday match
                        if 'BYDAY' in master_event['rrule']:
                            date = date + relativedelta(days=1)
                        else:
                            date = date + relativedelta(weeks=1)
                    case 'DAILY':
                        date = date + relativedelta(days=1)
                i += 1
    else:
        # TODO:
        print('date not supported yet')

    return out_dict_arr


weekday_arr = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']


def by_day(by_day_arr, date):
    return weekday_arr[date.weekday()] in by_day_arr


def master_event_active(event_to_check):
    start_date = event_to_check['dtstart'].dt
    until_date = None

    # if the master event is cancelled it's not active
    if 'STATUS' in event_to_check and event_to_check['STATUS'] == 'CANCELLED':
        return False

    if 'UNTIL' in event_to_check['rrule']:
        until_date = event_to_check['rrule']['until'][0]
    elif 'COUNT' in event_to_check['rrule']:
        freq = event_to_check['rrule']['freq']
        # note: this only supports weekly or daily freq as of now
        # TODO: add monthly and yearly support
        multiplier = 1
        if freq == 'WEEKLY':
            multiplier = 7
        until_date = start_date + datetime.timedelta(days=event_to_check['rrule']['count'][0] * multiplier)
    elif 'BYDAY' not in event_to_check['rrule']:
        # if the master event doesn't have until, count or byday in it, mark it as inactive
        return False

    # check if master event already started
    if type(start_date) == datetime.datetime:
        active = start_date <= utc.localize(
            first_day_of_curr_week)
    elif type(start_date) == datetime.date:
        active = start_date <= datetime.date(
            first_day_of_curr_week.year, first_day_of_curr_week.month,
            first_day_of_curr_week.day)

    # check if master event hasn't already ended
    if until_date is not None:
        if type(until_date) == datetime.datetime:
            active = active and until_date >= utc.localize(first_day_of_curr_week)
        elif type(until_date) == datetime.date:
            # FIXME: weird intellij warning that i dont understand
            active = active and until_date >= datetime.date(
                first_day_of_curr_week.year, first_day_of_curr_week.month,
                first_day_of_curr_week.day)

    return active


def main():
    # TODO: comment back in
    sync_ics()

    # load ics file
    with open(TARGET_ICS_LOCATION,
              'r', encoding='utf-8') as file:
        cal = icalendar.Calendar.from_ical(file.read())

        # filter out all items, that aren't calendar events
        event_arr = [item for item in cal.subcomponents if item.name == 'VEVENT']

        for event in event_arr:
            if not handle_if_recurring_event(event):
                handle_regular_if_active(event)

        out_arr = []

        # put all regular events into out arr as they are already filtered
        for event in regular_events_arr:
            json_dict_regular = map_event(event)
            out_arr.append(json_dict_regular)

            # filter out all master events, that aren't in this week

        for master_event in [master_event for master_event in master_events_arr if master_event_active(master_event)]:
            # TODO: add exceptiondate support (exdate)
            # if there are any override events for the master event, handle them too
            if master_event['UID'] in override_events_dict:
                json_arr_master = map_recurring_event(master_event, override_events_dict[master_event['UID']])
            else:
                # no override elements, means empty arr as parameter
                json_arr_master = map_recurring_event(master_event, [])

            for generated_event in json_arr_master:
                if active_start_date(generated_event['start']):
                    generated_event['start'] = generated_event['start'].strftime('%d.%m.%Y %H:%M')
                    generated_event['end'] = generated_event['end'].strftime('%d.%m.%Y %H:%M')
                    out_arr.append(generated_event)

        # print events to console
        print(json.dumps(out_arr))

        print(len(out_arr))


main()
