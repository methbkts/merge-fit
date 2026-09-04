import argparse
import datetime
from pathlib import Path

import fitparse
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_creator_message import FileCreatorMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.sport_message import SportMessage
from fit_tool.profile.profile_type import (
    Event,
    EventType,
    FileType,
    Manufacturer,
    Sport,
    SubSport,
)

SEMI_TO_DEG = 180.0 / (2**31)


def to_millis(dt):
    return round(dt.replace(tzinfo=datetime.UTC).timestamp() * 1000)


def load(fname):
    f = fitparse.FitFile(str(fname))
    data = {
        "records": [],
        "session": None,
        "device_info": None,
        "sport": None,
        "file_id": None,
        "file_creator": None,
        "events": [],
    }
    for msg in f.get_messages():
        if msg.name == "record":
            d = {x.name: x.value for x in msg}
            data["records"].append(d)
        elif msg.name == "session":
            data["session"] = {x.name: x.value for x in msg}
        elif msg.name == "device_info":
            data["device_info"] = {x.name: x.value for x in msg}
        elif msg.name == "sport":
            data["sport"] = {x.name: x.value for x in msg}
        elif msg.name == "file_id":
            data["file_id"] = {x.name: x.value for x in msg}
        elif msg.name == "file_creator":
            data["file_creator"] = {x.name: x.value for x in msg}
        elif msg.name == "event":
            data["events"].append({x.name: x.value for x in msg})
    return data


def add_records(records, dist_offset, builder):
    last_dist = 0.0
    for r in records:
        m = RecordMessage()
        m.timestamp = to_millis(r["timestamp"])
        if "position_lat" in r and r["position_lat"] is not None:
            m.position_lat = r["position_lat"] * SEMI_TO_DEG
        if "position_long" in r and r["position_long"] is not None:
            m.position_long = r["position_long"] * SEMI_TO_DEG
        if "enhanced_altitude" in r and r["enhanced_altitude"] is not None:
            m.enhanced_altitude = r["enhanced_altitude"]
        elif "altitude" in r and r["altitude"] is not None:
            m.enhanced_altitude = r["altitude"]
        if "enhanced_speed" in r and r["enhanced_speed"] is not None:
            m.enhanced_speed = r["enhanced_speed"]
        if "gps_accuracy" in r and r["gps_accuracy"] is not None:
            m.gps_accuracy = r["gps_accuracy"]
        if "heart_rate" in r and r["heart_rate"] is not None:
            m.heart_rate = r["heart_rate"]
        if "distance" in r and r["distance"] is not None:
            last_dist = r["distance"] + dist_offset
            m.distance = last_dist
        builder.add(m)
    return last_dist


def default_output(file1, file2):
    first = Path(file1)
    second = Path(file2)
    name = f"{first.stem}_{second.stem}_merged.fit"
    return first.with_name(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Merge two FIT activity files.")
    parser.add_argument("file1", type=Path, help="the first FIT file")
    parser.add_argument("file2", type=Path, help="the second FIT file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output FIT file (default: <file1>_<file2>_merged.fit)",
    )
    args = parser.parse_args(argv)
    output = args.output or default_output(args.file1, args.file2)

    d1 = load(args.file1)
    d2 = load(args.file2)
    s1, s2 = d1["session"], d2["session"]
    sport = Sport(d1["sport"]["sport"])
    try:
        sub_sport = SubSport(d1["sport"].get("sub_sport"))
    except TypeError, ValueError:
        sub_sport = SubSport.GENERIC

    builder = FitFileBuilder(auto_define=True)

    fid = FileIdMessage()
    fid.type = FileType.ACTIVITY
    fid.manufacturer = Manufacturer.DEVELOPMENT
    fid.product_name = d1["file_id"]["product_name"]
    fid.serial_number = d1["file_id"]["serial_number"]
    fid.time_created = to_millis(d1["file_id"]["time_created"])
    builder.add(fid)

    fc = FileCreatorMessage()
    fc.software_version = d1["file_creator"]["software_version"]
    builder.add(fc)

    dev = DeviceInfoMessage()
    dev.timestamp = to_millis(d1["device_info"]["timestamp"])
    dev.device_index = 0
    dev.manufacturer = Manufacturer.DEVELOPMENT
    dev.product_name = d1["device_info"]["product_name"]
    dev.serial_number = d1["device_info"]["serial_number"]
    dev.descriptor = d1["device_info"]["descriptor"]
    dev.source_type = 5
    builder.add(dev)

    ev = EventMessage()
    ev.event = Event.TIMER
    ev.event_type = EventType.START
    ev.timestamp = to_millis(d1["records"][0]["timestamp"])
    builder.add(ev)

    sp = SportMessage()
    sp.sport = sport
    sp.sub_sport = sub_sport
    sp.sport_name = d1["sport"]["name"]
    builder.add(sp)

    end_dist_1 = add_records(d1["records"], 0.0, builder)

    ev = EventMessage()
    ev.event = Event.SESSION
    ev.event_type = EventType.STOP_ALL
    ev.timestamp = to_millis(d1["records"][-1]["timestamp"])
    builder.add(ev)

    ev = EventMessage()
    ev.event = Event.TIMER
    ev.event_type = EventType.START
    ev.timestamp = to_millis(d2["records"][0]["timestamp"])
    builder.add(ev)

    end_dist_2 = add_records(d2["records"], end_dist_1, builder)

    ev = EventMessage()
    ev.event = Event.SESSION
    ev.event_type = EventType.STOP_ALL
    ev.timestamp = to_millis(d2["records"][-1]["timestamp"])
    builder.add(ev)

    start_time = d1["records"][0]["timestamp"]
    end_time = d2["records"][-1]["timestamp"]
    total_elapsed = (end_time - start_time).total_seconds()
    total_timer = s1["total_timer_time"] + s2["total_timer_time"]
    total_distance = end_dist_2
    total_calories = s1["total_calories"] + s2["total_calories"]

    avg_hr = round(
        (
            s1["avg_heart_rate"] * s1["total_timer_time"]
            + s2["avg_heart_rate"] * s2["total_timer_time"]
        )
        / total_timer
    )
    max_hr = max(s1["max_heart_rate"], s2["max_heart_rate"])
    min_hr = min(s1["min_heart_rate"], s2["min_heart_rate"])

    avg_alt = (
        s1["enhanced_avg_altitude"] * s1["total_timer_time"]
        + s2["enhanced_avg_altitude"] * s2["total_timer_time"]
    ) / total_timer
    max_alt = max(s1["enhanced_max_altitude"], s2["enhanced_max_altitude"])
    min_alt = min(s1["enhanced_min_altitude"], s2["enhanced_min_altitude"])
    avg_speed = total_distance / total_timer

    nec_lat = max(s1["nec_lat"], s2["nec_lat"]) * SEMI_TO_DEG
    nec_long = max(s1["nec_long"], s2["nec_long"]) * SEMI_TO_DEG
    swc_lat = min(s1["swc_lat"], s2["swc_lat"]) * SEMI_TO_DEG
    swc_long = min(s1["swc_long"], s2["swc_long"]) * SEMI_TO_DEG

    sess = SessionMessage()
    sess.message_index = 0
    sess.start_time = to_millis(start_time)
    sess.timestamp = to_millis(end_time)
    sess.total_elapsed_time = total_elapsed
    sess.total_timer_time = total_timer
    sess.total_distance = total_distance
    sess.total_calories = total_calories
    sess.sport = sport
    sess.sub_sport = sub_sport
    sess.avg_heart_rate = avg_hr
    sess.max_heart_rate = max_hr
    sess.min_heart_rate = min_hr
    sess.enhanced_avg_altitude = avg_alt
    sess.enhanced_max_altitude = max_alt
    sess.enhanced_min_altitude = min_alt
    sess.avg_altitude = avg_alt
    sess.max_altitude = max_alt
    sess.min_altitude = min_alt
    sess.enhanced_avg_speed = avg_speed
    sess.avg_speed = avg_speed
    sess.nec_lat = nec_lat
    sess.nec_long = nec_long
    sess.swc_lat = swc_lat
    sess.swc_long = swc_long
    sess.event = Event.SESSION
    sess.event_type = EventType.STOP
    sess.trigger = 0
    sess.first_lap_index = 0
    sess.num_laps = 1
    builder.add(sess)

    act = ActivityMessage()
    act.timestamp = to_millis(end_time)
    act.num_sessions = 1
    act.total_timer_time = total_timer
    act.type = 0
    builder.add(act)

    out_file = builder.build()
    out_file.to_file(output)
    print("Written", output)

    check = fitparse.FitFile(str(output))
    counts = {}
    for msg in check.get_messages():
        counts[msg.name] = counts.get(msg.name, 0) + 1
    print(counts)
    records = list(check.get_messages("record"))
    print(
        "first:",
        records[0].get_value("timestamp"),
        "last:",
        records[-1].get_value("timestamp"),
    )
    print("n records:", len(records))
    for session in check.get_messages("session"):
        print("SESSION:", {x.name: x.value for x in session})


if __name__ == "__main__":
    main()
