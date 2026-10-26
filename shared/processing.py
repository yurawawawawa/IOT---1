"""BuddyCheck window statistics in SI units, shared by the Android sender."""

from dataclasses import dataclass
from math import fsum, hypot, isfinite, sqrt

GRAVITY = 9.81


@dataclass(frozen=True)
class SensorSample:
    seconds: float
    acceleration: tuple[float, float, float]
    gyroscope: tuple[float, float, float]


@dataclass(frozen=True)
class Features:
    motion_rms: float
    rotation_rad: float
    accel_peak: float
    window_ms: int
    sample_count: int


def extract_features(samples: list[SensorSample]) -> Features:
    """Summarize one chronological window without retaining raw measurements."""
    count = len(samples)
    if count < 4:
        raise ValueError("BuddyCheck membutuhkan minimal empat sampel per jendela")

    energy_terms, angular_steps, deviations = [], [], []
    previous_time = None
    for measurement in samples:
        if len(measurement.acceleration) != 3 or len(measurement.gyroscope) != 3:
            raise ValueError("Sensor harus menyediakan tiga sumbu")
        values = (*measurement.acceleration, *measurement.gyroscope, measurement.seconds)
        if any(type(value) not in (int, float) or not isfinite(value) for value in values):
            raise ValueError("Nilai sensor harus berupa angka finite")
        if previous_time is not None:
            elapsed = measurement.seconds - previous_time
            if elapsed <= 0:
                raise ValueError("Waktu sampel harus bertambah")
            angular_steps.append(hypot(*measurement.gyroscope) * elapsed)
        deviation = abs(hypot(*measurement.acceleration) - GRAVITY)
        deviations.append(deviation)
        energy_terms.append(deviation * deviation)
        previous_time = measurement.seconds

    return Features(
        motion_rms=round(sqrt(fsum(energy_terms) / count), 4),
        rotation_rad=round(fsum(angular_steps), 4),
        accel_peak=round(max(deviations), 4),
        window_ms=round(1000 * (samples[-1].seconds - samples[0].seconds)),
        sample_count=count,
    )
