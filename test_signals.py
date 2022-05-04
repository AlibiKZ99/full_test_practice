from unittest import mock
from unittest.mock import ANY

from django.test import (
    RequestFactory,
    TestCase,
)
from model_bakery import baker
from parameterized import parameterized

from app.questions import signals
from app.questions.field_types import FieldType
from app.questions.models import Step
from app.questions.signals import (
    NomatchReasons,
    get_common_context_data,
)


class BaseSignalTestMixIn:
    receiver_function = None
    signal_type = None
    ed = {
        "element": ANY,
        "type": "question_flow",
        "context": {
            "step": 0,
            "step_name": "q_1",
            "category_id": ANY,
            "sequence": 0,
            "questions": ["field_1"],
            "label_name": None,
        },
    }

    def setUp(self):
        self.fn = self.receiver_function
        flow = baker.make("questions.Flow")
        question_1 = baker.make("questions.Question", title="q_1")
        self.step_1 = baker.make(
            "questions.Step",
            flow=flow,
            template="step.html",
            step_type=Step.StepType.question.value,
            order=0,
        )
        baker.make(
            "questions.QuestionField",
            field_type=FieldType.range.value,
            data={
                "start": 5,
                "end": 10,
            },
            required=True,
            name="field_1",
            question=question_1,
        )
        self.step_1.matching_brands = mock.MagicMock(return_value=[])
        baker.make("questions.StepQuestion", step=self.step_1, question=question_1)

        self.request = RequestFactory().get("/")
        self.request.session = {}
        self.request.store = mock.MagicMock()
        self.request.store.control = {}
        self.request.trackers = mock.MagicMock()

    def test_questionflow_step_receiver(self):
        self.fn(request=self.request, step=self.step_1)
        self.request.trackers.userdb.new_event.assert_called_once_with(
            self.signal_type, "form interaction", ed=self.ed, use_referer=True
        )

    def test_questionflow_step_receiver_extra_context(self):
        ed = self.ed
        extra_context = {"step_name": "new_name"}
        ed["context"].update(extra_context)
        self.fn(
            request=self.request,
            step=self.step_1,
            extra_context=extra_context,
        )
        self.request.trackers.userdb.new_event.assert_called_once_with(
            self.signal_type, "form interaction", ed=ed, use_referer=True
        )


class FlowV2StepViewReceiverTest(BaseSignalTestMixIn, TestCase):
    receiver_function = signals.step_view_receiver
    signal_type = "view"


class FlowV2StepSubmitReceiverTest(BaseSignalTestMixIn, TestCase):
    ed = {
        "element": ANY,
        "type": "question_flow",
        "context": {
            "step": 0,
            "step_name": "q_1",
            "category_id": ANY,
            "sequence": 0,
            "questions": ["field_1"],
            "label_name": None,
            "answers": ANY,
        },
    }
    receiver_function = signals.step_submit_receiver
    signal_type = "submit"


class FlowV2StepMatchReceiverTest(BaseSignalTestMixIn, TestCase):
    ed = {
        "element": ANY,
        "type": "question_flow",
        "context": {
            "step": 0,
            "step_name": "q_1",
            "category_id": ANY,
            "sequence": 0,
            "matching_brands": [],
        },
    }
    receiver_function = signals.step_match_receiver
    signal_type = "match"


class FlowV2StepNoMatchReceiverTest(BaseSignalTestMixIn, TestCase):
    ed = {
        "element": ANY,
        "type": "question_flow",
        "context": {
            "step": 0,
            "step_name": "q_1",
            "category_id": ANY,
            "sequence": 0,
            "nomatch_reason": NomatchReasons.BRANDS_REJECT.value,
        },
    }
    receiver_function = signals.step_no_match_receiver
    signal_type = "no_thanks"

    def test_questionflow_nomatch_reason_kwargs(self):
        ed = self.ed
        extra_context = {"step_name": "new_name", "nomatch_reason": "kwargs reason"}
        ed["context"].update(extra_context)
        self.fn(
            request=self.request,
            step=self.step_1,
            extra_context=extra_context,
            nomatch_reason="kwargs reason",
        )
        self.request.trackers.userdb.new_event.assert_called_once_with(
            self.signal_type, "form interaction", ed=ed, use_referer=True
        )

    def test_questionflow_nomatch_reason_request(self):
        ed = self.ed
        extra_context = {
            "step_name": "new_name",
            "nomatch_reason": "request nomatch reason",
        }
        self.request.nomatch_reason = "request nomatch reason"
        ed["context"].update(extra_context)
        self.fn(
            request=self.request,
            step=self.step_1,
            extra_context=extra_context,
            nomatch_reason="request nomatch reason",
        )
        self.request.trackers.userdb.new_event.assert_called_once_with(
            self.signal_type, "form interaction", ed=ed, use_referer=True
        )
        self.request.nomatch_reason = None

    def test_questionflow_step_receiver(self):
        pass

    def test_questionflow_step_receiver_extra_context(self):
        pass


class FlowV2StepCrossSellReceiverTest(BaseSignalTestMixIn, TestCase):
    ed = {
        "element": ANY,
        "type": "question_flow",
        "context": {
            "step": 0,
            "step_name": "q_1",
            "category_id": ANY,
            "sequence": 0,
        },
    }
    receiver_function = signals.step_cross_sell_receiver
    signal_type = "cross sell"

    def test_questionflow_step_receiver(self):
        ed = self.ed
        ed["context"]["originating_category_id"] = ANY
        ed["context"]["category_id"] = 10
        ed["context"]["brand"] = {"id": 2, "name": "B1"}
        ed["context"]["non_referral"] = False
        self.fn(
            request=self.request,
            step=self.step_1,
            brand={"id": 2, "brand_id": 1, "name": "B1"},
            cross_sell_category={
                "category_id": 10,
                "_name": "Category A",
            },
        )
        self.request.trackers.userdb.new_event.assert_called_once_with(
            self.signal_type,
            "form interaction",
            ed=ed,
            use_referer=True,
        )

    def test_questionflow_step_receiver_extra_context(self):
        ed = self.ed
        ed["context"]["originating_category_id"] = ANY
        ed["context"]["category_id"] = 10
        ed["context"]["brand"] = {"id": 2, "name": "B1"}
        ed["context"]["non_referral"] = False
        extra_context = {"step_name": "new_name"}
        ed["context"].update(extra_context)
        self.fn(
            request=self.request,
            step=self.step_1,
            brand={"id": 2, "brand_id": 1, "name": "B1"},
            extra_context=extra_context,
            cross_sell_category={
                "category_id": 10,
                "_name": "Category A",
            },
        )
        self.request.trackers.userdb.new_event.assert_called_once_with(
            self.signal_type, "form interaction", ed=ed, use_referer=True
        )

    @mock.patch("app.questions.signals.logger.error")
    def test_questionflow_step_receiver_no_brand(self, p_error):
        self.fn(
            request=self.request,
            step=self.step_1,
            brand=None,
            extra_context={},
            cross_sell_category={},
        )
        p_error.assert_called_once_with(
            "brand is missing", extra={"flow_pk": self.step_1.flow.pk}
        )


class GetContextDataTest(TestCase):
    @parameterized.expand(
        [
            ("emtpy", [], 0),
            ("step_0", [0], 1),
            ("step_4", [0, 1, 2, 3], 4),
        ]
    )
    def test_get_context_data_step_count(self, _, steps_visited, expected_step_count):
        request = mock.Mock()
        step = mock.Mock()
        request.store.control = {"steps_visited": steps_visited}
        result = get_common_context_data(request, step)
        self.assertEqual(result["sequence"], expected_step_count)
