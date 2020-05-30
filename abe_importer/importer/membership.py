from __future__ import annotations

from collections import Iterable
from dataclasses import dataclass
from functools import total_ordering, reduce


MEMBERSHIP_FEE_PATTERN = "Mitgliedsbeitrag %-%"


@total_ordering
@dataclass
class FeeMonth:
    year: int
    month: int

    @classmethod
    def from_desc(cls, desc: str) -> FeeMonth:
        assert desc.startswith("Mitglieds")
        # Mitgliedsbeitrag 2018-08
        _, isomonth = desc.split(' ')
        year, month = isomonth.split('-')
        return FeeMonth(year=int(year.strip()), month=int(month.strip()))

    def __le__(self, other):
        return all((
            self.year <= getattr(other, 'year', float('NaN')),
            self.month <= getattr(other, 'month', float('NaN')),
        ))


def get_latest_month(descriptions: Iterable[str]) -> FeeMonth:
    def take_max(cur: FeeMonth, new: str):
        return max(cur, FeeMonth.from_desc(new))

    return reduce(take_max, descriptions, FeeMonth(0, 0))


def test_latest_month():
    assert get_latest_month([
        "Mitgliedsbeitrag 2019-12",
        "Mitgliedsbeitrag 2020-01",
        "Mitgliedsbeitrag 2020-02",
        "Mitgliedsbeitrag 2020-03",
        "Mitgliedsbeitrag 2020-04",
    ]) == FeeMonth(year=2020, month=4)
