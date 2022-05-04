from model_bakery import baker
from app.questions.models import Step

from app.misc.test import TestCase


class StepTest(TestCase):
    def setUp(self) -> None:
        self.step_1 = baker.make(
            "questions.Step",
            step_type=Step.StepType.timed.value,
            template="templates/abandon.html",
        )
        self.step_2 = baker.make(
            "questions.Step", step_type=Step.StepType.no_match.value
        )

    def test_is_abandon(self):
        self.assertTrue(self.step_1.is_abandon)

    def test_is_abandon_false(self):
        self.assertFalse(self.step_2.is_abandon)

    def test_is_last(self):
        self.assertTrue(self.step_2.is_last)

    def test_is_last_false(self):
        self.assertFalse(self.step_1.is_last)

    def test_is_no_match(self):
        self.assertTrue(self.step_2.is_no_match)

    def test_is_no_match_false(self):
        self.assertFalse(self.step_1.is_no_match)

    def test_field_names(self):
        question = baker.make("questions.Question", name="buhbye")
        baker.make("questions.QuestionField", name="hiho", question=question)
        baker.make("questions.QuestionField", name="buhbye", question=question)
        baker.make("questions.StepQuestion", question=question, step=self.step_1)
        self.assertCountEqual(self.step_1.field_names, ["buhbye", "hiho"])


class FlowCheckpointTest(TestCase):
    def setUp(self):
        flow = baker.make("questions.Flow")
        self.step_1 = baker.make(
            "questions.Step", flow=flow, order=1, template="templates/anything.html"
        )
        self.step_2_abandon = baker.make(
            "questions.Step", flow=flow, order=2, template="templates/abandon_step.html"
        )
        domain = baker.make("landpages.Domain", hostname="t.es.t")
        self.fc = baker.make(
            "questions.FlowCheckpoint",
            status=0,
            flow=flow,
            config__endpoint__path="path/",
            config__endpoint__domain=domain,
        )

    def test_is_active(self):
        self.assertTrue(self.fc.is_active)

        self.fc.status = 1
        self.assertFalse(self.fc.is_active)

    def test_get_abandon_link(self):
        self.assertEqual(
            self.fc.get_abandon_link(),
            f"https://t.es.t/path/?continue={self.fc.unique_id}",
        )

    def test_get_match_link(self):
        # TODO:
        pass

    def test_abandon_step(self):
        self.assertEqual(self.fc.flow.abandon_step.pk, self.step_2_abandon.pk)
