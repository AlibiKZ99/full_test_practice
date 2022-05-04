from unittest.mock import MagicMock

from model_mommy import mommy

from django.test import TestCase
from django.core.exceptions import ValidationError
from parameterized import parameterized

from app.questions import field_types


class DateFieldTest(TestCase):
    def test_valid(self):
        field_types.DateField().validate("2020-12-12", None)


class RangeFieldTest(TestCase):
    def test_invalid_options_json(self):
        with self.assertRaisesMessage(ValidationError, "'end' is a required property"):
            field_types.RangeField().validate_field_options(
                {
                    "start": 5,
                }
            )

    def test_valid_options_json(self):
        field_types.RangeField().validate_field_options(
            {
                "start": 5,
                "end": 6,
            }
        )

    def test_valid_value(self):
        step = mommy.make("questions.QuestionField", data={"start": 5, "end": 10})
        field_types.RangeField().validate(7, step)

    def test_invalid_type_value(self):
        step = mommy.make("questions.QuestionField", data={"start": 5, "end": 10})
        with self.assertRaisesMessage(
            ValidationError, "'hello' is not of type 'integer'"
        ):
            field_types.RangeField().validate("hello", step)

    def test_invalid_range_value(self):
        step = mommy.make("questions.QuestionField", data={"start": 5, "end": 10})

        with self.assertRaisesMessage(
            ValidationError, "15 is greater than the maximum of 10"
        ):
            field_types.RangeField().validate(15, step)


class SingleSelectFieldTest(TestCase):
    def test_get_value_schema(self):
        question_config = {
            "options": [
                {"label": "foo", "value": "X"},
                {"label": "bar", "value": "Y"},
                {"label": "baz", "value": "Z"},
            ]
        }
        question_field = mommy.make("questions.QuestionField", data=question_config)
        expected = {
            "type": "string",
            "enum": ["X", "Y", "Z"],
        }
        actual = field_types.SingleSelectField().get_value_schema(None, question_field)
        self.assertEqual(actual, expected)


class MultipleSelectFieldTest(TestCase):
    def test_get_value_schema(self):
        question_config = {
            "options": [
                {"label": "foo", "value": "X"},
                {"label": "bar", "value": "Y"},
                {"label": "baz", "value": "Z"},
            ]
        }
        question_field = mommy.make("questions.QuestionField", data=question_config)
        expected = {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["X", "Y", "Z"],
            },
        }
        actual = field_types.MultipleSelectField().get_value_schema(
            None, question_field
        )
        self.assertEqual(actual, expected)


class InputTypeFieldStringTest(TestCase):
    @parameterized.expand(
        [
            ("no_constraints", {"required": False}, {"type": "string"}),
            (
                "required",
                {"required": True},
                {"type": "string", "minLength": 1},
            ),
            (
                "required_min_length",
                {"required": True, "minLength": 3},
                {"type": "string", "minLength": 3},
            ),
            (
                "required_max_length",
                {"required": False, "maxLength": 9},
                {"type": "string", "maxLength": 9},
            ),
            (
                "required_strict_length",
                {"required": True, "minLength": 1, "maxLength": 10},
                {"type": "string", "minLength": 1, "maxLength": 10},
            ),
        ]
    )
    def test_input_type_field_string_schema(self, _, constraints, expected):
        question_field = MagicMock()
        question_field.required = constraints.get("required")
        question_field.data = {
            "type": "String",
            "minLength": constraints.get("minLength", 0),
            "maxLength": constraints.get("maxLength", 0),
        }

        field_schema = field_types.InputTypeField().get_value_schema(
            "some str value", question_field
        )

        self.assertDictEqual(field_schema, expected)


class InputTypeFieldAddressTest(InputTypeFieldStringTest):
    def test_input_type_field_address_schema_required(self):
        question_field = MagicMock()
        question_field.required = True
        question_field.data = {"type": "Address"}

        field_schema = field_types.InputTypeField().get_value_schema(
            "245 Kingsbury Grade, Suite 1025", question_field
        )

        self.assertDictEqual(field_schema, {"type": "string", "minLength": 1})


class InputTypeFieldNumberTest(TestCase):
    @parameterized.expand(
        [
            ("no_constraints", {"required": False}, {"type": "number"}),
            (
                "min_number",
                {"required": True, "min": 0},
                {"type": "number", "minimum": 0},
            ),
            (
                "max_number",
                {"required": False, "max": 99},
                {"type": "number", "maximum": 99},
            ),
            (
                "range_number",
                {"required": True, "min": 1, "max": 10},
                {"type": "number", "minimum": 1, "maximum": 10},
            ),
        ]
    )
    def test_input_type_field_number_schema_no_constraints(
        self, _, constraints, expected
    ):
        question_field = MagicMock()
        question_field.required = constraints.get("required")
        question_field.data = {"type": "Number"}

        if "min" in constraints:
            question_field.data["min"] = constraints.get("min")

        if "max" in constraints:
            question_field.data["max"] = constraints.get("max")

        field_schema = field_types.InputTypeField().get_value_schema(1, question_field)

        self.assertDictEqual(field_schema, expected)
