import json

import icalendar
import datetime
import pytz
import subprocess

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
first_day_of_curr_week = (datetime.datetime.today() -
                          datetime.timedelta(days=datetime.datetime.now().isocalendar().weekday - 1))
last_day_of_curr_week = (first_day_of_curr_week +
                         datetime.timedelta(days=7))


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
        # if there is a recurrence-id, this means, that it an override event
        if event_to_check['UID'] not in override_events_dict:
            override_events_dict[(event_to_check['UID'])] = []
        override_events_dict[(event_to_check['UID'])].append(event_to_check)
        return True
    else:
        return False


def handle_regular_if_active(event_to_check):
    start_date = event_to_check['dtstart'].dt
    active = False
    if type(start_date) == datetime.datetime:
        # check if event is in the current week
        active = utc.localize(first_day_of_curr_week) <= start_date <= utc.localize(
            last_day_of_curr_week)
    elif type(start_date) == datetime.date:
        # check if event is in the current week
        active = datetime.date(first_day_of_curr_week.year, first_day_of_curr_week.month,
                               first_day_of_curr_week.day) <= start_date <= datetime.date(
            last_day_of_curr_week.year, last_day_of_curr_week.month,
            last_day_of_curr_week.day)

    if active:
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
    # TODO: mark events as recurring and how often
    # TODO: support all day events

    # print(json.dumps(out_dict))
    # print('-----------------------------------')
    return out_dict


def map_recurring_event(event, override_event_arr):
    out_dict = map_event(event)

    out_dict['overrides'] = []

    # FIXME: map all recurring events to regular events including overrides
    for event in override_event_arr:
        override_event_dict = map_event(event)
        out_dict['overrides'].append(override_event_dict)

    return out_dict


def master_event_active(event_to_check):
    active = False
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
            active = active and until_date >= utc.localize(last_day_of_curr_week)
        elif type(until_date) == datetime.date:
            # FIXME: weird intellij warning that i dont understand
            active = active and until_date >= datetime.date(
                last_day_of_curr_week.year, last_day_of_curr_week.month,
                last_day_of_curr_week.day)

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
            handle_if_recurring_event(event)
            handle_regular_if_active(event)

        out_arr = []

        # put all regular events into out arr as they are already filtered
        for event in regular_events_arr:
            json_dict_regular = map_event(event)
            out_arr.append(json.dumps(json_dict_regular))

        # filter out all master events, that aren't in this week

        for event in [master_event for master_event in master_events_arr if master_event_active(master_event)]:
            # TODO: add exceptiondate support (exdate)
            # if there are any override events for the master event, handle them too
            if event['UID'] in override_events_dict:
                json_dict_master = map_recurring_event(event, override_events_dict[event['UID']])
            else:
                # no override elements, means empty arr as parameter
                json_dict_master = map_recurring_event(event, [])

            out_arr.append(json.dumps(json_dict_master))

        # print events to console
        print(json.dumps(out_arr))

        print(len(out_arr))


main()
