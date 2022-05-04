import uuid
from datetime import timedelta
from unittest import mock

from model_bakery import baker

from django.test import (
    RequestFactory,
    TestCase,
)

from app.questions import checkpoint
from app.questions.models import FlowCheckpoint, Step


class CreateFlowAbandonCheckpoint(TestCase):
    def setUp(self):
        self.session_data = mock.Mock(used_brands=["mock"])
        self.flow_obj = baker.make("questions.Flow", data=[{"step_rules": []}] * 15)
        self.config_obj = baker.make("landpages.Config", flow=self.flow_obj)
        self.request = RequestFactory().get("/")
        self.step_1 = baker.make(
            "questions.Step",
            flow=self.flow_obj,
            template="step.html",
            step_type=Step.StepType.question.value,
            order=0,
        )
        self.request.request_step = self.step_1
        self.request.config = self.config_obj
        self.request.store = mock.Mock()
        self.request.store.answers = {"5": "6"}
        self.request.store.metadata = {"a": "b"}
        self.request.store.control = {"banana": "apple"}

    def test_with_ca_session_id(self):

        self.request.COOKIES["CA_SESSION_ID"] = "d88d1916-20e0-45b7-a186-e342b4a42531"

        obj = checkpoint.create_flow_abandon_checkpoint(
            self.request, self.request.request_step
        )

        self.assertEqual(str(obj.ca_session_id), "d88d1916-20e0-45b7-a186-e342b4a42531")
        self.assertEqual(obj.type, FlowCheckpoint.Type.abandon.value)
        self.assertEqual(obj.config, self.config_obj)
        self.assertEqual(obj.flow, self.flow_obj)
        self.assertEqual(
            obj.data,
            {
                "answers": {"5": "6"},
                "control": {"banana": "apple"},
                "metadata": {"a": "b"},
            },
        )
        self.assertEqual(obj.step, self.step_1)

    @mock.patch("app.misc.utils.logger")
    def test_wo_ca_session_id(self, p_logger):
        request = RequestFactory().get("/")

        obj = checkpoint.create_flow_abandon_checkpoint(
            request, self.request.request_step
        )

        self.assertIsNone(obj)
        p_logger.warning.assert_called_once_with(
            "get_ca_session_id without ca_session_id",
            extra={"stack": True},
        )


class GetCheckpointTest(TestCase):
    def setUp(self):
        self.match = baker.make(
            "questions.FlowCheckpoint",
            type=1,
            status=0,
            config__config_id=1,
        )
        self.abandon = baker.make(
            "questions.FlowCheckpoint",
            type=0,
            status=0,
            config__config_id=1,
        )

    def test_no_unique_id(self):
        ch, error_msg = checkpoint.get_checkpoint(None)
        self.assertIsNone(ch)
        self.assertIsNone(error_msg)

        ch, error_msg = checkpoint.get_checkpoint("")
        self.assertIsNone(ch)
        self.assertIsNone(error_msg)

    def test_non_uuid(self):
        ch, error_msg = checkpoint.get_checkpoint("hello")
        self.assertIsNone(ch)
        self.assertEqual(error_msg, "Invalid unique id")

    def test_non_existent(self):
        ch, error_msg = checkpoint.get_checkpoint(uuid.uuid4())
        self.assertIsNone(ch)
        self.assertEqual(error_msg, "Checkpoint does not exist")

    def test_different_config_check(self):
        ch, error_msg = checkpoint.get_checkpoint(self.match.unique_id)
        self.assertEqual(ch, self.match)
        self.assertIsNone(error_msg)

        ch, error_msg = checkpoint.get_checkpoint(
            self.match.unique_id, self.match.config.id + 1
        )
        self.assertIsNone(ch)
        self.assertEqual(error_msg, "Checkpoint used for different config")

    def test_match_checkpoint_too_old(self):
        self.match.created = self.match.created - timedelta(days=90)
        self.match.save()

        ch, error_msg = checkpoint.get_checkpoint(self.match.unique_id)
        self.assertIsNone(ch)
        self.assertEqual(error_msg, "Match link expired")

    def test_abandon_checkpoint_too_old(self):
        self.abandon.created = self.abandon.created - timedelta(days=90)
        self.abandon.save()

        ch, error_msg = checkpoint.get_checkpoint(self.abandon.unique_id)
        self.assertIsNone(ch)
        self.assertEqual(error_msg, "Abandon link expired")

    def test_abandon_checkpoint_already_matched(self):
        self.abandon.status = 1
        self.abandon.save()

        ch, error_msg = checkpoint.get_checkpoint(self.abandon.unique_id)
        self.assertIsNone(ch)
        self.assertEqual(error_msg, "Checkpoint already matched")

    def test_valid(self):
        ch, error_msg = checkpoint.get_checkpoint(self.match.unique_id)
        self.assertEqual(ch, self.match)
        self.assertIsNone(error_msg)
