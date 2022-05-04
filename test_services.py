from unittest import mock

from django.test import RequestFactory, override_settings

from model_bakery import baker
from parameterized import parameterized

from app.questions import services
from app.questions.field_types import FieldType
from app.questions.models import Step
from app.questions.services import get_flow_fields, prepopulate_answers_v2
from app.misc.test import TestCase


class PrepopulateAnswersTest(TestCase):
    def setUp(self) -> None:
        self.request = mock.MagicMock()
        self.request.flow = mock.MagicMock()
        self.request.store = mock.MagicMock()
        self.request.store.data = {}
        self.request.store.answers = {}
        self.request.method = "post"
        self.request.post = {"zip": "12345", "invalid_field": "random"}

    @mock.patch("app.questions.services.field_valid", return_value=True)
    @mock.patch("app.questions.services.get_flow_fields", return_value={"name", "zip"})
    def test_valid_answers(self, p_get_flow_fields, p_field_valid):
        prepopulate_answers_v2(self.request)
        result = self.request.store.answers
        p_field_valid.assert_called_once()
        p_get_flow_fields.assert_called_once_with(self.request.flow)
        self.assertIn("zip", result)

    @mock.patch("app.questions.services.field_valid", return_value=False)
    @mock.patch("app.questions.services.get_flow_fields", return_value={"name", "zip"})
    def test_no_valid_fields(self, p_get_flow_fields, p_field_valid):
        self.request.post = {"random_field": "blah", "another_field": "bloh"}
        prepopulate_answers_v2(self.request)
        result = self.request.store.answers
        self.assertEqual(result, {})


class GetFlowFieldsTest(TestCase):
    def setUp(self) -> None:
        self.flow = baker.make("questions.Flow")
        self.flow_empty = baker.make("questions.Flow")
        step_1 = baker.make(
            "questions.Step",
            flow=self.flow,
            template="steps/step.html",
            step_type=Step.StepType.question.value,
            order=0,
        )
        step_2 = baker.make(
            "questions.Step",
            flow=self.flow,
            template="steps/step.html",
            step_type=Step.StepType.question.value,
            order=1,
        )
        question_1 = baker.make("questions.Question", title="q_1")
        question_2 = baker.make("questions.Question", title="q_2")
        baker.make(
            "questions.QuestionField",
            field_type=FieldType.range.value,
            data={
                "start": 5,
                "end": 10,
            },
            required=True,
            name="field_step_1",
            question=question_1,
        )
        baker.make(
            "questions.QuestionField",
            field_type=FieldType.input_type.value,
            data={
                "type": "Number",
            },
            name="field_step_2",
            required=False,
            required_text="required yo",
            question=question_2,
        )
        baker.make(
            "questions.QuestionField",
            field_type=FieldType.input_type.value,
            data={
                "type": "Number",
            },
            name="field_step_3",
        )

        baker.make("questions.StepQuestion", step=step_1, question=question_1)
        baker.make("questions.StepQuestion", step=step_2, question=question_2)

    def test_return_only_related_fields(self):
        result = get_flow_fields(self.flow)
        self.assertEqual(result, ["field_step_1", "field_step_2"])

    def test_returns_no_fields(self):
        result = get_flow_fields(self.flow_empty)
        self.assertEqual(result, [])


class AddMissingFieldsTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.session = {}
        self.request.store = services.FlowSessionStore(self.request, 1)
        self.request.trackers = mock.Mock()
        baker.make(
            "zip_code.ZipCode", zip_code=12345, county="AA", state="ST", city="City"
        )
        self.request.config = mock.Mock()
        category = baker.make("brands.Category", id=123)
        self.request.config.flow = baker.make("questions.Flow", category=category)

        self.flow = baker.make("questions.Flow")
        self.flow_empty = baker.make("questions.Flow")
        self.step = baker.make(
            "questions.Step",
            flow=self.flow,
            template="steps/step.html",
            step_type=Step.StepType.question.value,
            order=0,
        )
        question_1 = baker.make("questions.Question", title="q_1")
        baker.make(
            "questions.QuestionField",
            field_type=FieldType.range.value,
            data={
                "start": 5,
                "end": 10,
            },
            required=True,
            name="field_step_1",
            question=question_1,
        )

        baker.make("questions.StepQuestion", step=self.step, question=question_1)

    def test_add_missing_fields_county(self):
        self.request.store.answers = {"zip": 12345}
        question_field = mock.Mock()
        question_field.name = "zip"
        m_step = mock.Mock(question_fields=[question_field], field_names=["zip"])
        result = services.add_missing_fields(self.request, m_step)
        self.assertIsNone(result)
        self.assertEqual(self.request.store.metadata, {"county": "AA"})

    @override_settings(ITERABLE_LIST_ID="888")
    def test_add_missing_fields_subscribe_email_is_called(self):
        self.request.store.answers = {"email": "a@b.c", "fruit": "banana"}
        question_field = mock.Mock()
        question_field.name = "email"
        m_step = mock.Mock(question_fields=[question_field], field_names=["email"])
        self.request.config.flow.subscribe_email = True
        services.add_missing_fields(self.request, m_step)

        self.request.trackers.email_marketing.subscribe.assert_called_once_with(
            email="a@b.c", fruit="banana", category_id=123, list_id="888"
        )

    def test_add_missing_fields_subscribe_email_not_called(self):
        self.request.store.answers = {"email": "a@b.c"}
        question_field = mock.Mock()
        question_field.name = "email"
        m_step = mock.Mock(question_fields=[question_field])
        self.request.trackers.email_marketing.subscribe = mock.Mock()
        self.request.config.flow.subscribe_email = False
        services.add_missing_fields(self.request, m_step)

        self.request.trackers.email_marketing.subscribe.assert_not_called()

    def test_add_missing_fields_county_no_zip(self):
        self.request.store.answers = {"zip": 12340}
        question_field = mock.Mock()
        question_field.name = "zip"
        m_step = mock.Mock(question_fields=[question_field], field_names=["zip"])
        result = services.add_missing_fields(self.request, m_step)
        self.assertIsNone(result)
        self.assertEqual(self.request.store.metadata, {})

    def test_add_missing_fields_city_and_state_no_zip(self):
        self.request.store.metadata = {
            "to_city": "City",
            "to_state": "ST",
        }
        question_field = mock.Mock()
        question_field.name = "zip"
        m_step = mock.Mock(question_fields=[question_field])
        result = services.add_missing_fields(self.request, m_step)
        self.assertIsNone(result)
        self.assertEqual(
            self.request.store.metadata,
            {"to_city": "City", "to_state": "ST", "to_zip": "12345"},
        )

    @mock.patch("app.questions.services.TransUnionClient.get_credit_rating")
    def test_add_missing_fields_ssn(self, p_get_credit_rating):
        p_get_credit_rating.return_value = mock.Mock(value=1)
        self.request.store.answers = {
            "ssn": "111222",
            "first_name": "CEDRIC",
            "last_name": "WYNN",
            "address": "4219 28TH ST",
            "state": "MD",
            "zip": "20712",
        }
        question_field = mock.Mock()
        question_field.name = "ssn"
        m_step = mock.Mock(question_fields=[question_field], field_names=["ssn"])
        result = services.add_missing_fields(self.request, m_step)
        self.assertIsNone(result)
        self.assertEqual(
            self.request.store.metadata,
            {
                "credit_rating": 1,
                "using_partial_ssn": True,
                "using_default_rating": False,
            },
        )
        p_get_credit_rating.assert_called_once_with(
            {
                "ssn": "111222",
                "first_name": "CEDRIC",
                "last_name": "WYNN",
                "street": "4219 28TH ST",
                "state": "MD",
                "zip_code": "20712",
            }
        )

    @parameterized.expand(["birth_date", "birthdate", "date_of_birth"])
    def test_add_missing_fields_birth_date(self, key):
        self.request.store.answers = {key: "12.12.2012", "a": "b"}
        result = services.add_missing_fields(self.request, self.step)
        self.assertIsNone(result)
        self.assertEqual({"a": "b"}, self.request.store.answers)

    @mock.patch("app.questions.services.TransUnionClient.get_credit_rating")
    def test_add_missing_fields_ssn_state(self, p_get_credit_rating):
        p_get_credit_rating.return_value = mock.Mock(value=1)
        self.request.store.answers = {
            "ssn": "111222",
            "first_name": "CEDRIC",
            "last_name": "WYNN",
            "address": "4219 28TH ST",
            "address_autocomplete_state_name": "UU",
            "zip": "20712",
        }
        question_field = mock.Mock()
        question_field.name = "ssn"
        m_step = mock.Mock(question_fields=[question_field], field_names=["ssn"])
        result = services.add_missing_fields(self.request, m_step)
        self.assertIsNone(result)
        self.assertEqual(
            self.request.store.metadata,
            {
                "credit_rating": 1,
                "using_partial_ssn": True,
                "using_default_rating": False,
            },
        )
        p_get_credit_rating.assert_called_once_with(
            {
                "ssn": "111222",
                "first_name": "CEDRIC",
                "last_name": "WYNN",
                "street": "4219 28TH ST",
                "state": "UU",
                "zip_code": "20712",
            }
        )

    @mock.patch("app.questions.services.TransUnionClient.get_credit_rating")
    def test_add_missing_fields_ssn_default_rating(self, p_get_credit_rating):
        p_get_credit_rating.return_value = None
        self.request.store.answers = {
            "ssn": "111222",
            "first_name": "CEDRIC",
            "last_name": "WYNN",
            "address": "4219 28TH ST",
            "address_autocomplete_state_name": "UU",
            "zip": "20712",
        }
        question_field = mock.Mock()
        question_field.name = "ssn"
        m_step = mock.Mock(question_fields=[question_field], field_names=["ssn"])
        result = services.add_missing_fields(self.request, m_step)
        self.assertIsNone(result)
        self.assertEqual(
            self.request.store.metadata,
            {
                "credit_rating": 2,
                "using_default_rating": True,
                "using_partial_ssn": False,
            },
        )
        p_get_credit_rating.assert_called_once_with(
            {
                "ssn": "111222",
                "first_name": "CEDRIC",
                "last_name": "WYNN",
                "street": "4219 28TH ST",
                "state": "UU",
                "zip_code": "20712",
            }
        )


class GetPreviousDistributionStepTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.session = {}
        self.request.store = services.FlowSessionStore(self.request, 1)
        self.flow = baker.make("questions.Flow")
        baker.make(
            "questions.Step",
            flow=self.flow,
            step_type="question",
            order=1,
            template="A",
        )

    def test_get_previous_distribution_step_none(self):
        self.assertIsNone(
            services.get_previous_distribution_step(self.request, self.flow, 1)
        )

    def test_get_previous_distribution_step(self):
        baker.make(
            "questions.Step",
            flow=self.flow,
            step_type="distribution",
            order=0,
            template="D",
        )
        result = services.get_previous_distribution_step(self.request, self.flow, 1)
        self.assertEqual(result.template, "D")


class IsLeadDuplicateTest(TestCase):
    def test_is_duplicate_true(self):
        polled_lead = {
            "referrals": [
                {"brand_id": 1, "status": "Duplicate"},
                {"brand_id": 2, "status": "Duplicate"},
            ]
        }
        self.assertTrue(services.is_lead_duplicate(polled_lead))

    def test_is_duplicate_false(self):
        polled_lead = {
            "referrals": [
                {"brand_id": 1, "status": "Delivered-Ok"},
                {"brand_id": 2, "status": "Duplicate"},
            ]
        }
        self.assertFalse(services.is_lead_duplicate(polled_lead))

    def test_is_duplicate_empty_false(self):
        polled_lead = {"referrals": []}
        self.assertFalse(services.is_lead_duplicate(polled_lead))


class ClearDataTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.session = {}
        self.request.store = services.FlowSessionStore(self.request, 1)
        self.request.store.data = {"control": {"steps_visited": [1, 2]}}

    def test_clear_data(self):
        self.assertEqual(
            self.request.store.data, {"control": {"steps_visited": [1, 2]}}
        )
        self.request.store.clear()
        self.assertEqual(self.request.store.data["control"], {"steps_visited": []})


class SessionWipeCleanTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.session = {}
        self.request.store = services.FlowSessionStore(self.request, 1)
        self.request.store.data = {"a": {"b": [1, 2]}}

    def test_clear_data(self):
        self.assertEqual(self.request.store.data, {"a": {"b": [1, 2]}})
        self.request.store.wipe_clean()
        self.assertEqual(self.request.store.data, {})


class RecapAnswerTest(TestCase):
    def test_recap(self):
        answers = {"question": "single answer"}
        recap = {"question": {"single answer": "sample text"}}
        self.assertEqual(services.recap_answers(answers, recap), ["sample text"])

    def test_recap_replace_answer(self):
        answers = {"question": "single answer"}
        recap = {"question": {"single answer": "You've chosen {}"}}
        self.assertEqual(
            services.recap_answers(answers, recap), ["You've chosen single answer"]
        )

    def test_recap_wildcard(self):
        answers = {"question": "single answer"}
        recap = {"question": {"*": "sample text"}}
        self.assertEqual(services.recap_answers(answers, recap), ["sample text"])

    @mock.patch("app.questions.services.logger")
    def test_recap_maintain_answer(self, p_logger):
        answers = {"question": "single answer"}
        recap = {"question": {"*": "{}"}}
        self.assertEqual(services.recap_answers(answers, recap), ["single answer"])
        p_logger.warning.assert_not_called()

    @mock.patch("app.questions.services.logger")
    def test_recap_question_not_found(self, p_logger):
        answers = {"question_1": "single answer", "question_2": "some other answer"}
        recap = {"question_1": {"single answer": "sample text"}}
        self.assertEqual(services.recap_answers(answers, recap), ["sample text"])
        p_logger.warning.assert_called_once_with("recap question question_2 not found")

    @mock.patch("app.questions.services.logger")
    def test_recap_answer_not_found(self, p_logger):
        answers = {"question_1": "single answer"}
        recap = {"question_1": {"different answer": "anything really"}}
        self.assertEqual(services.recap_answers(answers, recap), [])
        p_logger.warning.assert_called_once_with(
            "no recap answer single answer matched for question question_1"
        )

    @mock.patch("app.questions.services.logger")
    def test_recap_list(self, p_logger):
        answers = {
            "question": ["first answer", "second answer"],
            "ignored_question": "blah",
        }
        recap = {
            "question": {
                "first answer": "replace first",
                "second answer": "replace second",
            }
        }
        self.assertEqual(
            services.recap_answers(answers, recap), ["replace first", "replace second"]
        )
        p_logger.warning.assert_called_once_with(
            "recap question ignored_question not found"
        )

    def test_recap_list_and_item(self):
        answers = {
            "question": ["first answer", "second answer"],
            "other_question": "blah",
        }
        recap = {
            "question": {
                "first answer": "replace first",
                "second answer": "replace second",
            },
            "other_question": {"blah": "hiho"},
        }
        self.assertEqual(
            services.recap_answers(answers, recap),
            ["replace first", "replace second", "hiho"],
        )
