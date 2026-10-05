import unittest

from reddit_growth_miner.analysis import Enricher, EntityExtractor
from reddit_growth_miner.classify import RuleClassifier
from reddit_growth_miner.domain import Switch
from reddit_growth_miner.rules import RuleSet
from reddit_growth_miner.sources import post_from_raw

from fakes import raw_post

RULES = RuleSet.load()
CLF = RuleClassifier(RULES)


def intents(title, body=""):
    return {l.intent for l in CLF.classify(title, body)}


class ClassifierTests(unittest.TestCase):
    def test_multi_label(self):
        found = intents("Notion is so slow, any alternative to it?")
        self.assertIn("alternative_search", found)
        self.assertIn("complaint", found)

    def test_promotion_does_not_hide_demand(self):
        labels = CLF.classify("I built a tool, but honestly looking for an alternative to Zapier for myself")
        self.assertIn("promotion", {l.intent for l in labels})
        self.assertEqual(CLF.primary(labels).intent, "alternative_search")

    def test_promotion_only(self):
        labels = CLF.classify("Check out my new app")
        self.assertEqual(CLF.primary(labels).intent, "promotion")

    def test_help_is_not_matched_by_bare_word(self):
        self.assertNotIn("help_request", intents("This tool helped our team ship faster"))
        self.assertNotIn("recommendation_request", intents("Thanks for the suggestions everyone"))

    def test_workaround_needs_a_described_manual_process(self):
        self.assertNotIn("workaround_share", intents("", "stop manually fixing the flat files before pushing"))
        self.assertIn("workaround_share", intents("", "Right now we track every deadline manually"))
        self.assertIn("workaround_share", intents("", "I manually copy the numbers into the report"))

    def test_purchase_intent(self):
        self.assertIn("purchase_intent", intents("Need a CRM, budget is $50/month, willing to pay for good support"))

    def test_themes_use_whole_words(self):
        self.assertEqual(CLF.themes("My therapist moved to Seoul after the breach"), [])
        self.assertIn("workflow-friction", CLF.themes("Their API is a pain"))
        self.assertIn("distribution", CLF.themes("SEO is dead"))
        self.assertIn("reliability", CLF.themes("it doesn't work anymore"))


class EntityTests(unittest.TestCase):
    def test_switch_without_known_list(self):
        found = EntityExtractor().switches("We switched from Notion to Obsidian last month.")
        self.assertEqual(found, [Switch("Notion", "Obsidian")])

    def test_mentions_without_list_need_comparison_language(self):
        ex = EntityExtractor()
        self.assertEqual(ex.mentions("On Monday I wrote Python all day"), [])
        self.assertEqual(ex.mentions("Looking for an alternative to Calendly"), ["Calendly"])

    def test_known_list_normalises_aliases(self):
        ex = EntityExtractor.parse("Linear=linear.app|Linear App,Jira")
        self.assertEqual(ex.mentions("we left jira, now on linear.app"), ["Linear", "Jira"])
        self.assertEqual(ex.switches("Moved from Jira to Linear App and never looked back"), [Switch("Jira", "Linear")])

    def test_known_list_drops_untracked_switches(self):
        self.assertEqual(EntityExtractor.parse("Jira").switches("switched from Asana to Trello"), [])


class EnrichTests(unittest.TestCase):
    def setUp(self):
        self.enricher = Enricher(CLF, EntityExtractor())

    def test_enrich_keeps_no_author(self):
        raw = raw_post("a", "Looking for an alternative to Acme")
        raw["author"] = "someone"
        post = self.enricher.enrich(post_from_raw(raw, "x"))
        self.assertFalse(hasattr(post, "author"))
        self.assertEqual(post.intent, "alternative_search")
        self.assertTrue(post.signals.buying)
        self.assertEqual(post.competitors, ("Acme",))

    def test_promotional_post_is_not_demand_but_its_replies_are(self):
        post = self.enricher.enrich(post_from_raw(raw_post("a", "We just launched our invoicing app"), "x"))
        self.assertTrue(post.signals.promotion)
        self.assertFalse(post.signals.demand)
        post = self.enricher.attach_comments(post, [
            {"id": "c1", "body": "Nice. I switched from FreshBooks to Wave last year, would pay $10 for this", "score": 12},
            {"id": "c2", "body": "cool", "score": 50},
        ])
        self.assertTrue(post.signals.demand)
        self.assertTrue(post.signals.from_comments)
        self.assertTrue(post.signals.budget)
        self.assertIn(Switch("FreshBooks", "Wave"), post.switches)
        self.assertEqual(post.comments[0].id, "c1")  # signal-bearing comment ranked above higher score
        self.assertEqual(post.comments_scanned, 2)


if __name__ == "__main__":
    unittest.main()
