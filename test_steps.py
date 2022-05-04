from unittest import mock

from model_bakery import baker

from django.test import TestCase

from app.landpages.models import Domain
from app.questions.field_types import FieldType
from app.questions import (
    steps,
    signals,
)


class StepValidatorTest(TestCase):
    def setUp(self):
        question_1 = baker.make("questions.Question", title="q_1")
        question_2 = baker.make("questions.Question", title="q_2")
        self.step = baker.make("questions.Step")
        self.field_1 = baker.make(
            "questions.QuestionField",
            field_type=FieldType.range.value,
            data={
                "start": 5,
                "end": 10,
            },
            required=True,
            name="f_1",
            question=question_1,
        )
        self.field_2 = baker.make(
            "questions.QuestionField",
            field_type=FieldType.input_type.value,
            data={
                "type": "Number",
            },
            name="f_2",
            required=False,
            required_text="required yo",
            question=question_2,
        )
        baker.make("questions.StepQuestion", step=self.step, question=question_1)
        baker.make("questions.StepQuestion", step=self.step, question=question_2)

    def test_is_valid_valid(self):
        answers = {
            "f_1": 6,
            "f_2": 10,
        }
        step_validator = steps.StepValidator(self.step, answers)
        self.assertTrue(step_validator.is_valid())
        self.assertEqual(step_validator.errors, {})

    def test_is_valid_with_non_required_missing(self):
        answers = {
            "f_1": 6,
        }
        step_validator = steps.StepValidator(self.step, answers)
        self.assertTrue(step_validator.is_valid())
        self.assertEqual(step_validator.errors, {})

    def test_is_valid_missing_field_default_text(self):
        answers = {}
        step_validator = steps.StepValidator(self.step, answers)
        self.assertFalse(step_validator.is_valid())
        self.assertEqual(
            step_validator.errors,
            {
                "f_1": ["This field is required"],
            },
        )

    def test_is_valid_missing_field_custom_text(self):
        self.field_2.required = True
        self.field_2.save()

        answers = {
            "f_1": 7,
        }
        step_validator = steps.StepValidator(self.step, answers)
        self.assertFalse(step_validator.is_valid())
        self.assertEqual(
            step_validator.errors,
            {
                "f_2": ["required yo"],
            },
        )

    def test_is_valid_invalid_values(self):
        answers = {
            "f_1": 15,
            "f_2": "wat",
        }
        step_validator = steps.StepValidator(self.step, answers)
        self.assertFalse(step_validator.is_valid())
        self.assertEqual(
            step_validator.errors,
            {
                "f_1": ["15 is greater than the maximum of 10"],
                "f_2": ["'wat' is not of type 'number'"],
            },
        )


class IsEmailSubscription(TestCase):
    def test_for_retirement_living_host(self):
        retirementliving_com = "guides.retirementliving.com"
        baker.make(
            Domain, hostname=retirementliving_com, send_data_to_email_marketing=False
        )

        self.assertFalse(steps.is_email_subscription(retirementliving_com))

    def test_for_any_other_host(self):
        consumeraffairs_com = "consumeraffairs.com"
        baker.make(
            Domain, hostname=consumeraffairs_com, send_data_to_email_marketing=True
        )

        self.assertTrue(steps.is_email_subscription(consumeraffairs_com))

    def test_for_not_found_host(self):
        self.assertTrue(steps.is_email_subscription("not_host_found.com"))


class DistributionStepTest(TestCase):
    def setUp(self):
        signals.step_match.disconnect(signals.step_match_receiver)

    @mock.patch("app.questions.services.get_next_match_step")
    @mock.patch("app.questions.services.serialize_flow")
    @mock.patch("app.brands.services.send_leads")
    @mock.patch("app.brands.services.get_matching_brands")
    @mock.patch("app.brands.services.get_brands_from_distribution")
    def test_process_leads_disabled(
        self,
        p_get_brands_from_distribution,
        p_get_matching_brands,
        p_send_leads,
        p_serialize_flow,
        p_get_next_match_step,
    ):
        p_get_matching_brands.return_value = ([{"brand_id": 1}], None, {"a": "b"})
        step = baker.make(
            "questions.Step",
            reusable_config_part=baker.make("landpages.ReusableConfigPart"),
            flow__disable_leads=True,
        )
        request = mock.Mock()
        request.config.flow = step.flow
        distribution_step = steps.DistributionStep(step)
        distribution_step.process(request)
        p_send_leads.assert_not_called()
