import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.schemas.trip import TimeOfDay, TripRequest


@dataclass(frozen=True)
class PlannerTiming:
    arrival_buffer_minutes: int = 60
    departure_buffer_minutes: int = 60
    day_end: time = time(22, 0)
    max_place_distance_km: float = 150.0

    @classmethod
    def from_environment(cls) -> "PlannerTiming":
        arrival_buffer = int(os.getenv("JOURNI_ARRIVAL_BUFFER_MINUTES", "60"))
        departure_buffer = int(os.getenv("JOURNI_DEPARTURE_BUFFER_MINUTES", "60"))
        max_place_distance = float(os.getenv("JOURNI_MAX_PLACE_DISTANCE_KM", "150"))
        day_end = time.fromisoformat(os.getenv("JOURNI_DAY_END", "22:00"))

        if arrival_buffer < 0 or departure_buffer < 0:
            raise ValueError("JOURNI journey buffers must not be negative.")
        if max_place_distance <= 0:
            raise ValueError("JOURNI_MAX_PLACE_DISTANCE_KM must be greater than zero.")

        return cls(
            arrival_buffer_minutes=arrival_buffer,
            departure_buffer_minutes=departure_buffer,
            day_end=day_end,
            max_place_distance_km=max_place_distance,
        )

    def earliest_start(self, request: TripRequest, current_date: datetime) -> datetime:
        earliest = datetime.combine(current_date.date(), request.day_start)
        if request.journey and request.journey.arrival_at:
            available_at = request.journey.arrival_at + timedelta(
                minutes=self.arrival_buffer_minutes
            )
        else:
            assumed_arrival = {
                TimeOfDay.MORNING: time(12, 0),
                TimeOfDay.AFTERNOON: time(18, 0),
                TimeOfDay.EVENING: time(22, 0),
                TimeOfDay.NIGHT: time(6, 0),
            }[request.arrival]
            assumed_date = current_date.date()
            if request.arrival == TimeOfDay.NIGHT:
                assumed_date += timedelta(days=1)
            available_at = datetime.combine(assumed_date, assumed_arrival) + timedelta(
                minutes=self.arrival_buffer_minutes
            )
        return max(earliest, available_at)

    def latest_end(self, request: TripRequest, day_num: int) -> datetime:
        day_date = request.dates.start + timedelta(days=day_num - 1)
        latest = datetime.combine(day_date, self.day_end)
        if day_num == request.dates.nights + 1:
            departure_window_start = {
                TimeOfDay.MORNING: time(6, 0),
                TimeOfDay.AFTERNOON: time(12, 0),
                TimeOfDay.EVENING: time(18, 0),
                TimeOfDay.NIGHT: time(22, 0),
            }[request.departure]
            departure_limit = datetime.combine(day_date, departure_window_start) - timedelta(
                minutes=self.departure_buffer_minutes
            )
            latest = min(latest, departure_limit)
        return latest

    def describe_arrival_assumption(self, arrival: TimeOfDay) -> str:
        assumed_time = {
            TimeOfDay.MORNING: "12:00",
            TimeOfDay.AFTERNOON: "18:00",
            TimeOfDay.EVENING: "22:00",
            TimeOfDay.NIGHT: "06:00 the following day",
        }[arrival]
        return assumed_time

    def describe_departure_assumption(self, departure: TimeOfDay) -> str:
        assumed_time = {
            TimeOfDay.MORNING: "06:00",
            TimeOfDay.AFTERNOON: "12:00",
            TimeOfDay.EVENING: "18:00",
            TimeOfDay.NIGHT: "22:00",
        }[departure]
        return assumed_time
