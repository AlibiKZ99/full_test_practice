from model_bakery import baker

from app.misc.test import TestCase
from app.questions import serializers


class FlowCloneSerializerTest(TestCase):
    def test_validate_ok(self):
        serializer = serializers.FlowCloneSerializer(data={"name": "A"})
        result = serializer.is_valid()
        self.assertTrue(result)

    def test_validate_already_exists(self):
        baker.make(serializers.Flow, name="A")
        serializer = serializers.FlowCloneSerializer(data={"name": "A"})
        with self.assertRaises(serializers.serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_clone(self):
        domain = baker.make(
            "landpages.Domain",
            hostname="example.com",
        )
        endpoint = baker.make(
            "landpages.Endpoint",
            domain=domain,
            path="/test/",
        )
        instance = baker.make(
            serializers.Flow,
            name="A",
            page_title="B",
            template_name="C",
            meta_description="E",
        )
        config = baker.make(
            "landpages.Config",
            endpoint=endpoint,
            flow=instance,
            config_id=123,
        )
        baker.make(
            "landpages.ConfigBrand",
            config=config,
            brand__id=1,
        )
        step = baker.make(serializers.Step, flow=instance)
        step2 = baker.make(serializers.Step, flow=instance)
        baker.make(serializers.StepQuestion, step=step)
        baker.make(serializers.Branch, source_step=step, destination_step=step2)
        serializer = serializers.FlowCloneSerializer()
        result = serializer.clone(instance, {"name": "B"})
        new_config = result.config_set.all()[0]
        self.assertEqual(result.name, "B")
        self.assertEqual(result.page_title, "B")
        self.assertEqual(result.template_name, "C")
        self.assertEqual(result.meta_description, "E")
        self.assertEqual(new_config.config_id, 124)
        self.assertEqual(config.endpoint, new_config.endpoint)
        self.assertEqual(serializers.Step.objects.filter(flow=result).count(), 2)
        self.assertEqual(
            serializers.StepQuestion.objects.filter(step__flow=result).count(), 1
        )
        self.assertEqual(
            serializers.Branch.objects.filter(source_step__flow=result).count(), 1
        )
        self.assertEqual(new_config.configbrand_set.all().count(), 1)


class FlowConfigBaseTest(TestCase):
    def setUp(self):
        self.endpoint = baker.make(
            "landpages.Endpoint",
            path="/test/",
        )
        self.flow = baker.make(
            serializers.Flow,
            name="A",
            page_title="B",
            template_name="C",
            meta_description="E",
        )
        self.config = baker.make(
            "landpages.Config",
            endpoint=self.endpoint,
            flow=self.flow,
            config_id=123,
        )
        self.brand1 = baker.make(
            "brands.Brand",
            brand_id=1,
        )
        self.brand2 = baker.make(
            "brands.Brand",
            brand_id=2,
        )
        baker.make(
            "landpages.ConfigBrand",
            config=self.config,
            brand=self.brand1,
        )


class FlowConfigUpdateSerializerTest(FlowConfigBaseTest):
    def test_update(self):
        serializer = serializers.FlowConfigUpdateSerializer()
        validated_data = {
            "page_title": "A",
            "meta_description": "AA",
            "ui_base": "AAA",
            "page_type": self.config.page_type,
            "endpoint": self.endpoint,
            "brands": [self.brand2],
            "theme": "AA",
        }
        serializer.update(self.flow, validated_data)
        self.config.refresh_from_db()
        self.assertEqual(self.config.data["base"]["page_title"], "A")
        self.assertEqual(self.config.data["base"]["meta_description"], "AA")
        self.assertEqual(self.config.data["base"]["ui_base"], "AAA")
        self.assertEqual(self.config.data["base"]["theme"], "AA")
        self.assertEqual(self.config.flow, self.flow)
        self.assertEqual(
            list(self.config.configbrand_set.values_list("brand_id", flat=True)), [2]
        )


class FlowConfigRequestSerializerTest(FlowConfigBaseTest):
    def test_update(self):
        serializer = serializers.FlowConfigRequestSerializer()
        validated_data = {
            "configs": [
                {
                    "page_title": "A",
                    "meta_description": "AA",
                    "ui_base": "AAA",
                    "page_type": self.config.page_type,
                    "endpoint": self.endpoint,
                    "brands": [self.brand2],
                    "theme": "AA",
                }
            ]
        }
        serializer.update(self.flow, validated_data)
        self.config.refresh_from_db()
        self.assertEqual(self.config.data["base"]["page_title"], "A")
        self.assertEqual(self.config.data["base"]["meta_description"], "AA")
        self.assertEqual(self.config.data["base"]["ui_base"], "AAA")
        self.assertEqual(self.config.data["base"]["theme"], "AA")
        self.assertEqual(self.config.flow, self.flow)
        self.assertEqual(
            list(self.config.configbrand_set.values_list("brand_id", flat=True)), [2]
        )


class FlowConfigSerializerTest(FlowConfigBaseTest):
    def test_get_page_title(self):
        self.config.data["base"] = {"page_title": "sometitle"}
        serializer = serializers.FlowConfigSerializer()
        self.assertEqual(serializer.get_page_title(self.config), "sometitle")

    def test_get_meta_description(self):
        self.config.data["base"] = {"meta_description": "sometitle"}
        serializer = serializers.FlowConfigSerializer()
        self.assertEqual(serializer.get_meta_description(self.config), "sometitle")

    def test_get_ui_base(self):
        self.config.data["base"] = {"ui_base": "sometitle"}
        serializer = serializers.FlowConfigSerializer()
        self.assertEqual(serializer.get_ui_base(self.config), "sometitle")

    def test_get_brands(self):
        serializer = serializers.FlowConfigSerializer()
        self.assertEqual(
            list(serializer.get_brands(self.config)),
            [{"id": self.brand1.id, "brand_id": 1, "name": self.brand1.name}],
        )

    def test_get_theme(self):
        self.config.data["base"] = {"theme": "sometheme"}
        serializer = serializers.FlowConfigSerializer()
        self.assertEqual(serializer.get_theme(self.config), "sometheme")
