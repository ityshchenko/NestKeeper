"""Guards that typeguard instrumentation is really active for the nestkeeper package."""

from __future__ import annotations

from typing import Any, cast

import pytest
from typeguard import TypeCheckError

from nestkeeper.logging import mask_email
from nestkeeper.models.domain import normalise_email


def test_runtime_type_checks_are_active() -> None:
    with pytest.raises(TypeCheckError):
        mask_email(cast(Any, 123))
    with pytest.raises(TypeCheckError):
        normalise_email(cast(Any, None))
