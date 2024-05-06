#!/usr/bin/env python3
# -*- coding: utf-8 -*-


def new_entry():
    entry = {
        "version": 0,
        "date": "today",
        "settings": {
            "working-hours": 0,
            "excess-as-overtime": 0,
            "round-minutes": 0,
        },
        "periods": [],
        "note": "",
    }
    return entry


def is_period_ended(period: str):
    return len(period.split("-")) == 2 and period.split("-")[0] != "" and period.split("-")[1] != ""


def assert_periods_are_valid(periods: list):
    for period in periods:
        if len(period.split("-")) != 2:
            raise ValueError(f"Invalid period: {period}")

        start = float(period.split("-")[0])
        end = float(period.split("-")[1])

        if start >= end:
            raise ValueError(f"Invalid period: {period}")

    # check that the period does not overlap with any other period
    for period in periods:
        start = float(period.split("-")[0])
        end = float(period.split("-")[1])

        for other_period in periods:
            if other_period == period:
                continue

            other_start = float(other_period.split("-")[0])
            other_end = float(other_period.split("-")[1])

            if start <= other_end and other_start <= end:
                raise ValueError(f"Period overlaps: {period} {other_period}")


def parse_line(line: str) -> dict:
    entry = new_entry()
    parts = line.split(";")
    entry["version"] = int(parts[0].strip())
    if entry["version"] == 1:
        # read in v1
        # parse usign datetime
        entry["date"] = parts[1].strip()
        entry["settings"]["working-hours"] = float(parts[2].strip())
        entry["settings"]["excess-as-overtime"] = int(parts[3].strip())
        entry["settings"]["round-minutes"] = int(parts[4].strip())
        entry["periods"] = parts[5].replace(",", " ").split()
        entry["note"] = ";".join(parts[6:]).strip()

    else:
        raise ValueError("Unsupported version")

    return entry


def align_column(text: str, line: str, alignment_line: str | None = None) -> str:
    if alignment_line is None:
        return text

    splits = alignment_line.split(";")
    current_column = line.count(";")

    if current_column == 0:
        return text

    if current_column >= len(splits):
        return text

    leading_whitespace = len(splits[current_column]) - len(splits[current_column].lstrip())
    return " " * leading_whitespace + text


def format_period(period: str) -> str:
    splits = period.split("-")
    if splits[1] == "":
        return f"{float(splits[0]):g}-"
    return f"{float(splits[0]):g}-{float(splits[1]):g}"


def format_entry(entry: dict, alignment_line: str | None = None) -> str:
    line = ""
    if entry["version"] == 1:
        line += align_column(f"{entry['version']};", line, alignment_line)
        line += align_column(f"{entry['date']};", line, alignment_line)
        line += align_column(f"{entry['settings']['working-hours']:g};", line, alignment_line)
        line += align_column(f"{entry['settings']['excess-as-overtime']};", line, alignment_line)
        line += align_column(f"{entry['settings']['round-minutes']};", line, alignment_line)
        periods = [format_period(period) for period in entry["periods"]]
        line += align_column(f"{', '.join(periods)};", line, alignment_line)
        line += align_column(f"{entry['note']}", line, alignment_line)
    else:
        raise ValueError("Unsupported version")

    return line


def get_number_working_hours_from_periods(periods):
    # reads a list of periods of the format n-m, where n and m are floats representing the start and end of a period,
    # respectively
    return sum([float(period.split("-")[1]) - float(period.split("-")[0]) for period in periods])


def get_rounded_timestamp(timestamp: float, rounding_minutes: int) -> float:
    # timestamp is in hours, rounding_minutes is in minutes

    # convert the timestamp to minutes
    return round(timestamp * 60 / rounding_minutes) * rounding_minutes / 60


def get_rounded_timestamp_now(rounding_minutes: int) -> float:
    import datetime
    now = datetime.datetime.now()
    return get_rounded_timestamp(now.hour + now.minute / 60, rounding_minutes)


def get_number_working_hours_right_now(today_entry):
    # reads a list of periods of the format n-m, where n and m are floats representing the start and end of a period,
    # respectively
    # Also includes the current period if it is not ended, up until the current time
    periods = today_entry["periods"].copy()

    if len(periods) == 0:
        return 0

    if not is_period_ended(periods[-1]):
        round_minutes = today_entry["settings"]["round-minutes"]
        current_timestamp = get_rounded_timestamp_now(round_minutes)

        periods[-1] = f"{periods[-1].split('-')[0]}-{current_timestamp}"

    return get_number_working_hours_from_periods(periods)


def get_number_working_hours_from_days(entries: list):
    # reads a list of entries and returns the total number of working hours
    total = 0

    for entry in entries:
        total += get_number_working_hours_right_now(entry)

    return total


def get_list_of_entries_from_date_and_number_days_backwards(lines: list, date: str, num_days: int):
    # reads a list of entries and returns a list of entries starting from the date and going num_days back
    entries = []
    lines = get_only_report_entries(lines)
    # reverse lines
    lines = lines[::-1]
    date_found = False
    for line in lines:
        entry = parse_line(line)
        if entry["date"] == date:
            date_found = True
        if date_found:
            entries.append(entry)
            num_days -= 1
        if num_days == 0:
            break

    return entries


def fill_in_days_to_today(lines, full_file_path):
    import copy
    import datetime
    import holidays

    # check the date of the last entry
    last_entry = parse_line(lines[-1])
    # if the date is not today, append the file with all dates from the last entry to today
    while last_entry["date"] != datetime.date.today().isoformat():
        # deep copy the last entry and update the date
        entry = copy.deepcopy(last_entry)
        entry["date"] = (datetime.date.fromisoformat(last_entry["date"]) + datetime.timedelta(days=1)).isoformat()

        # check if date is a saturday or a swedish financial holiday using the library holidays
        se_holidays = holidays.country_holidays("SE")
        if datetime.date.fromisoformat(entry["date"]).weekday() == 5 or entry["date"] in se_holidays:
            entry["settings"]["working-hours"] = 0
            try:
                entry["note"] = se_holidays[entry["date"]]
            except KeyError:
                entry["note"] = "Saturday"
        else:
            entry["settings"]["working-hours"] = 8
            entry["note"] = ""

        entry["periods"] = []
        new_line = format_entry(entry, lines[-1])
        lines.append(new_line)

        # append the file with the next date
        with open(full_file_path, "a") as f:
            f.write(new_line + "\n")

        last_entry = parse_line(lines[-1])


def read_report_card(full_file_path):
    # read in the report card file using readlines
    lines = []
    with open(full_file_path, "r") as f:
        lines = f.readlines()

    return lines


def usage(lines) -> str:
    out = ""
    for line in lines:
        if line.startswith("#"):
            line = line[1:].strip()
            # replace $0 with the name of the script
            line = line.replace("$0", sys.argv[0])
            print(line)
        else:
            break
    return out


def parse_args(lines):
    # manually parse command line arguments using sys.argv
    import sys
    argv = sys.argv[1:]
    return argv


def remove_last_line_in_file(full_file_path):
    # remove last line of file
    with open(full_file_path, "r+") as file:
        # move the pointer to the end of the file
        file.seek(0, os.SEEK_END)

        # this code means the following code skips the very last character in the file - i.e. in the case the last line
        # is null we delete the last line and the penultimate one
        pos = file.tell() - 1

        # read each character in the file one at a time from the penultimate character going backwards, searching for a
        # newline character if we find a new line, exit the search
        while pos > 0 and file.read(1) != "\n":
            pos -= 1
            file.seek(pos, os.SEEK_SET)

        # so long as we're not at the start of the file, delete all the characters ahead of this position
        if pos > 0:
            file.seek(pos, os.SEEK_SET)
            file.truncate()
            file.write("\n")


def check_number_args(args, expected):
    if len(args) not in expected:
        print(f"Expected {expected} arguments, got {len(args)}")
        sys.exit(1)


def get_only_report_entries(lines):
    report_lines = []

    for line in lines:
        # skip comments
        if line.startswith("#"):
            continue
        # skip empty lines
        if line.strip() == "":
            continue
        # skip header lines
        if line.startswith("@"):
            continue

        report_lines.append(line)

    return report_lines


def get_accumulative_flex_bank_up_to_date(lines, date):
    flex_bank = 0

    lines = get_only_report_entries(lines)

    for line in lines:
        entry = parse_line(line)
        hours_worked = get_number_working_hours_right_now(entry)

        flex_bank = (
            flex_bank - entry["settings"]["working-hours"] + hours_worked
        )

        if entry["date"] == date:
            break

    return flex_bank


def pprint_entry(entry):
    import datetime

    week_number = datetime.date.fromisoformat(entry["date"]).isocalendar()[1]
    weekday = datetime.date.fromisoformat(entry["date"]).strftime("%A")[0:3]
    print(f"w{week_number: <4}", end="")
    print(f"{weekday: <4}", end="")
    print(f"{entry['date']: <11}", end="")
    print(f"{entry['settings']['working-hours']: <6g}", end="")
    print(f"{entry['settings']['excess-as-overtime']: <9g}", end="")
    to_print = f"{get_number_working_hours_right_now(entry):g}"
    if entry["periods"] and not is_period_ended(entry["periods"][-1]):
        to_print += "+"
    print(f"{to_print: <6}", end="")
    print(f"{', '.join(entry['periods']): <22} ", end="")
    print(f"{entry['note']: <0}")


def print_report(lines, num_days):
    import datetime

    lines = get_only_report_entries(lines)

    # take at the most the number of available days in the report
    if num_days > len(lines):
        num_days = len(lines)
    number_of_entries = len(lines)
    range_start = number_of_entries - num_days
    # first print a header line
    print(f"{'Week': <5}", end="")
    print(f"{'Day': <4}", end="")
    print(f"{'Date': <11}", end="")
    print(f"{'Hours': <6}", end="")
    print(f"{'Overtime': <9}", end="")
    print(f"{'Total': <6}", end="")
    print(f"{'Periods': <22} ", end="")
    print(f"{'Note': <0}")
    for day in range(num_days):
        entry = parse_line(lines[range_start + day])
        pprint_entry(entry)

        # after printing sunday (or the last day), print the total working hours for that week along with accumulated
        # flex bank up to that
        weekday = datetime.date.fromisoformat(entry["date"]).weekday()
        if weekday == 6 or day == num_days - 1:
            work_week = get_list_of_entries_from_date_and_number_days_backwards(lines, entry["date"], weekday + 1)
            total = get_number_working_hours_from_days(work_week)
            bank = get_accumulative_flex_bank_up_to_date(lines, entry['date'])
            to_print = f"Week total hours: {total:g}, flex bank: {bank:g}"
            print(f"{' ':<64}{to_print}")


def assert_test(test, equal):
    print(f"{test} == {equal}")
    assert test == equal


def test():
    assert_test(get_rounded_timestamp(8, 15), 8.0)
    assert_test(get_rounded_timestamp(8.20, 15), 8.25)
    assert_test(get_rounded_timestamp(8.74, 30), 8.5)
    assert_test(get_rounded_timestamp(8.75, 30), 9)
    assert_test(is_period_ended("12-13"), True)
    assert_test(is_period_ended("12-"), False)
    print("All tests passed")


if __name__ == "__main__":
    import os
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test()
        sys.exit(0)

    full_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "report.card")

    lines = read_report_card(full_file_path)
    argv = parse_args(lines)
    fill_in_days_to_today(lines, full_file_path)

    today_entry = parse_line(lines[-1])
    round_minutes = today_entry["settings"]["round-minutes"]
    current_timestamp = get_rounded_timestamp_now(round_minutes)

    # parse the first argument as the command
    if argv:
        command = argv[0]
    else:
        command = "31"  # Print the last month by default
    args = argv[1:]
    rerun_argv = []

    if command == "help":
        usage(lines)
        sys.exit(0)

    elif command == "in":
        check_number_args(args, [0, 1])
        if len(args) == 1:
            current_timestamp = get_rounded_timestamp(float(args[0]), round_minutes)

        print(f"checking in at {current_timestamp}")
        if not today_entry["periods"] or is_period_ended(today_entry["periods"][-1]):
            today_entry["periods"].append(f"{str(current_timestamp)}-")
        else:
            print(f"error: a period is already active: {today_entry['periods'][-1]}")
            sys.exit(1)
        rerun_argv = [sys.argv[0], "7"]
        print()

    elif command == "out":
        check_number_args(args, [0, 1])
        if len(args) == 1:
            current_timestamp = get_rounded_timestamp(float(args[0]), round_minutes)

        print(f"checking out at {current_timestamp}")
        if today_entry["periods"] and not is_period_ended(today_entry["periods"][-1]):
            today_entry["periods"][-1] = f"{today_entry['periods'][-1]}{str(current_timestamp)}"
            assert_periods_are_valid(today_entry["periods"])
        else:
            print(f"error: no active period: {today_entry['periods']}")
            sys.exit(1)
        rerun_argv = [sys.argv[0], "7"]
        print()

    elif command == "break":
        print("error: not yet implemented")
        sys.exit(1)
        check_number_args(args, [2])

    elif command == "period":
        check_number_args(args, [1])
        # split the period
        range_split = args[0].split("-")
        # make sure to properly round the timestamps
        rounded_period = ""
        rounded_period += f"{get_rounded_timestamp(float(range_split[0]), round_minutes)}"
        rounded_period += "-"
        rounded_period += f"{get_rounded_timestamp(float(range_split[1]), round_minutes)}"
        print(f"adding period {rounded_period}")
        new_periods = today_entry["periods"].copy()
        # check if the last period is not ended
        if new_periods and not is_period_ended(new_periods[-1]):
            # end it temporarily at 24:00 so the assert will pass
            new_periods[-1] = f"{new_periods[-1].split('-')[0]}-24"
        new_periods.append(rounded_period)
        assert_periods_are_valid(new_periods)

        # sort the periods
        new_periods.sort(key=lambda x: float(x.split("-")[0]))

        # remove the temporary end of the last period
        if new_periods[-1].split("-")[1] == "24":
            new_periods[-1] = f"{new_periods[-1].split('-')[0]}-"

        today_entry["periods"] = new_periods
        rerun_argv = [sys.argv[0], "7"]
        print()

    elif command == "note":
        print("error: not yet implemented")
        sys.exit(1)
    elif command == "working-hours":
        print("error: not yet implemented")
        sys.exit(1)
    elif command == "excess-as-overtime":
        print("error: not yet implemented")
        sys.exit(1)
    elif command == "round-minutes":
        print("error: not yet implemented")
        sys.exit(1)
    elif command.isdigit():
        print_report(lines, int(command))
    else:
        print(f"unknown command: {command}")
        sys.exit(1)

    remove_last_line_in_file(full_file_path)

    # write todays entry to the file
    with open(full_file_path, "a") as file:
        file.write(format_entry(today_entry, lines[-2]) + "\n")

    if rerun_argv:
        os.execv(rerun_argv[0], rerun_argv)
