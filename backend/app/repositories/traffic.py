"""Truy vấn cho Admin 1.2 – lưu lượng truy cập & người dùng online (fact_server_traffic_hourly)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import Connection

from backend.app.core.cache import cached
from backend.app.core.db import fetch_all, fetch_one, fetch_value

HOURLY_COLUMNS = """stat_hour, stat_date, hour_of_day, day_of_week, total_requests, unique_users, login_count,
                    failed_login_count, ws_requests, peak_online_users, avg_online_users, online_sample_count,
                    is_peak_hour"""


def hourly(conn: Connection, from_date: date, to_date: date) -> list[dict]:
    """Các giờ trong [from_date 00:00, to_date + 1 ngày)."""
    start = datetime.combine(from_date, datetime.min.time())
    end = datetime.combine(to_date, datetime.min.time()) + timedelta(days=1)
    return fetch_all(conn, f"""
        SELECT {HOURLY_COLUMNS} FROM analytics.fact_server_traffic_hourly
        WHERE stat_hour >= :start AND stat_hour < :end
        ORDER BY stat_hour""", {"start": start, "end": end})


def realtime(conn: Connection, now: datetime) -> dict:
    """now: giờ địa phương không kèm múi giờ. Chuỗi 24 giờ gần nhất tính tới giờ hiện tại (kể cả giờ đang chạy)."""
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    day_start = current_hour.replace(hour=0)
    series = fetch_all(conn, f"""
        SELECT {HOURLY_COLUMNS} FROM analytics.fact_server_traffic_hourly
        WHERE stat_hour > :from_hour AND stat_hour <= :current_hour
        ORDER BY stat_hour""", {"from_hour": current_hour - timedelta(hours=24), "current_hour": current_hour})
    online = fetch_one(conn, """
        SELECT slot_start, online_users, source FROM analytics.etl_online_snapshot
        WHERE slot_start <= :now ORDER BY slot_start DESC LIMIT 1""", {"now": now})
    requests_today = fetch_value(conn, """
        SELECT COALESCE(SUM(total_requests), 0) FROM analytics.fact_server_traffic_hourly
        WHERE stat_hour >= :day_start AND stat_hour <= :current_hour""",
        {"day_start": day_start, "current_hour": current_hour})
    current = next((r for r in series if r["stat_hour"] == current_hour), None)
    return dict(
        current_hour=current_hour,
        current_online=int(online["online_users"]) if online else 0,
        current_online_at=online["slot_start"] if online else None,
        current_online_source=online["source"] if online else None,
        requests_current_hour=int(current["total_requests"]) if current else 0,
        requests_so_far=int(requests_today),
        series_24h=series,
    )


@cached
def heatmap(conn: Connection, weeks: int, today: date) -> dict:
    """Trung bình theo (thứ, giờ) của `weeks` tuần TRỌN NGÀY gần nhất – không tính hôm nay đang dở dang."""
    from_date = today - timedelta(days=7 * weeks)
    matrix = fetch_all(conn, """
        SELECT day_of_week, hour_of_day,
               ROUND(AVG(total_requests), 1)   AS avg_requests,
               ROUND(AVG(avg_online_users), 1) AS avg_online_users,
               ROUND(100.0 * AVG(is_peak_hour::int), 1) AS peak_share,
               COUNT(*)                        AS days
        FROM analytics.fact_server_traffic_hourly
        WHERE stat_date >= :from_date AND stat_date < :today
        GROUP BY day_of_week, hour_of_day
        ORDER BY day_of_week, hour_of_day""", {"from_date": from_date, "today": today})
    return dict(weeks=weeks, from_date=from_date, to_date=today - timedelta(days=1), matrix=matrix)
