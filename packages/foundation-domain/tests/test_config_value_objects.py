"""Tests for configuration value objects."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError as PydanticValidationError

from praecepta.foundation.domain.config_value_objects import (
    BooleanConfigValue,
    ConfigKey,
    ConfigValue,
    EnumConfigValue,
    FloatConfigValue,
    IntegerConfigValue,
    PercentageConfigValue,
    StringConfigValue,
)


@pytest.mark.unit
class TestConfigKey:
    """Tests for ConfigKey extensible enum."""

    def test_is_empty_base(self) -> None:
        # ConfigKey has no members -- it's an extensible base
        assert len(list(ConfigKey)) == 0

    def test_extensible(self) -> None:
        class MyKey(ConfigKey):
            FOO = "foo"
            BAR = "bar"

        assert MyKey.FOO == "foo"
        assert MyKey.BAR == "bar"
        assert isinstance(MyKey.FOO, str)


@pytest.mark.unit
class TestBooleanConfigValue:
    """Tests for BooleanConfigValue."""

    def test_true(self) -> None:
        v = BooleanConfigValue(value=True)
        assert v.type == "boolean"
        assert v.value is True

    def test_false(self) -> None:
        v = BooleanConfigValue(value=False)
        assert v.value is False


@pytest.mark.unit
class TestIntegerConfigValue:
    """Tests for IntegerConfigValue."""

    def test_basic(self) -> None:
        v = IntegerConfigValue(value=42)
        assert v.type == "integer"
        assert v.value == 42

    def test_with_bounds(self) -> None:
        v = IntegerConfigValue(value=50, min_value=0, max_value=100)
        assert v.min_value == 0
        assert v.max_value == 100

    def test_no_bounds_default_none(self) -> None:
        v = IntegerConfigValue(value=1)
        assert v.min_value is None
        assert v.max_value is None


@pytest.mark.unit
class TestFloatConfigValue:
    """Tests for FloatConfigValue."""

    def test_basic(self) -> None:
        v = FloatConfigValue(value=3.14)
        assert v.type == "float"
        assert v.value == pytest.approx(3.14)

    def test_with_bounds(self) -> None:
        v = FloatConfigValue(value=0.5, min_value=0.0, max_value=1.0)
        assert v.min_value == pytest.approx(0.0)
        assert v.max_value == pytest.approx(1.0)


@pytest.mark.unit
class TestStringConfigValue:
    """Tests for StringConfigValue."""

    def test_basic(self) -> None:
        v = StringConfigValue(value="hello")
        assert v.type == "string"
        assert v.value == "hello"

    def test_with_max_length(self) -> None:
        v = StringConfigValue(value="hi", max_length=100)
        assert v.max_length == 100


@pytest.mark.unit
class TestPercentageConfigValue:
    """Tests for PercentageConfigValue."""

    def test_basic(self) -> None:
        v = PercentageConfigValue(value=50)
        assert v.type == "percentage"
        assert v.value == 50

    def test_min_zero(self) -> None:
        v = PercentageConfigValue(value=0)
        assert v.value == 0

    def test_max_hundred(self) -> None:
        v = PercentageConfigValue(value=100)
        assert v.value == 100

    def test_rejects_negative(self) -> None:
        with pytest.raises(PydanticValidationError):
            PercentageConfigValue(value=-1)

    def test_rejects_over_hundred(self) -> None:
        with pytest.raises(PydanticValidationError):
            PercentageConfigValue(value=101)


@pytest.mark.unit
class TestEnumConfigValue:
    """Tests for EnumConfigValue."""

    def test_basic(self) -> None:
        v = EnumConfigValue(value="a", allowed_values=["a", "b", "c"])
        assert v.type == "enum"
        assert v.value == "a"
        assert v.allowed_values == ["a", "b", "c"]


@pytest.mark.unit
class TestConfigValueDiscriminatedUnion:
    """Tests for the ConfigValue discriminated union."""

    def test_deserialize_boolean(self) -> None:
        adapter = TypeAdapter(
            BooleanConfigValue
            | IntegerConfigValue
            | FloatConfigValue
            | StringConfigValue
            | PercentageConfigValue
            | EnumConfigValue
        )
        result = adapter.validate_python({"type": "boolean", "value": True})
        assert isinstance(result, BooleanConfigValue)

    def test_deserialize_integer(self) -> None:
        adapter = TypeAdapter(
            BooleanConfigValue
            | IntegerConfigValue
            | FloatConfigValue
            | StringConfigValue
            | PercentageConfigValue
            | EnumConfigValue
        )
        result = adapter.validate_python({"type": "integer", "value": 42})
        assert isinstance(result, IntegerConfigValue)

    def test_config_value_type_alias_exists(self) -> None:
        # ConfigValue is a type alias -- verify it references the right types
        # We just verify it can be used in type checking context
        val: ConfigValue = BooleanConfigValue(value=True)
        assert val.type == "boolean"
