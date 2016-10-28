from nose.tools import (
    set_trace,
    eq_,
)

import contextlib

from api.config import (
    temp_config,
    Configuration,
)

from core.lane import (
    Lane,
    Facets,
)

from . import (
    DatabaseTest,
)

from scripts import (
    CacheRepresentationPerLane,
    CacheFacetListsPerLane,
)

class TestLaneScript(DatabaseTest):

    @contextlib.contextmanager
    def temp_config(self):
        """Create a temporary configuration with the bare-bones policies
        and integrations necessary to start up a script.
        """
        with temp_config() as config:
            config[Configuration.POLICIES] = {
                Configuration.AUTHENTICATION_POLICY : {
                    "providers": [
                        { "module" : "api.mock_authentication" }
                    ]
                },
                Configuration.LANGUAGE_POLICY : {
                    Configuration.LARGE_COLLECTION_LANGUAGES : 'eng',
                    Configuration.SMALL_COLLECTION_LANGUAGES : 'fre',
                }
            }
            circ_key = Configuration.CIRCULATION_MANAGER_INTEGRATION
            config[Configuration.INTEGRATIONS][circ_key] = {
                    "url": 'http://test-circulation-manager/'
            }
            yield config


class TestRepresentationPerLane(TestLaneScript):
   
    def test_language_filter(self):
        with self.temp_config() as config:
            script = CacheRepresentationPerLane(
                self._db, ["--language=fre", "--language=English", "--language=none", "--min-depth=0"],
                testing=True
            )
            eq_(['fre', 'eng'], script.languages)

            english_lane = Lane(self._db, self._str, languages=['eng'])
            eq_(True, script.should_process_lane(english_lane))

            no_english_lane = Lane(self._db, self._str, exclude_languages=['eng'])
            eq_(True, script.should_process_lane(no_english_lane))

            no_english_or_french_lane = Lane(
                self._db, self._str, exclude_languages=['eng', 'fre']
            )
            eq_(False, script.should_process_lane(no_english_or_french_lane))
            
    def test_max_and_min_depth(self):
        with self.temp_config() as config:
            script = CacheRepresentationPerLane(
                self._db, ["--max-depth=0", "--min-depth=0"],
                testing=True
            )
            eq_(0, script.max_depth)

            child = Lane(self._db, "sublane")
            parent = Lane(self._db, "parent", sublanes=[child])
            eq_(True, script.should_process_lane(parent))
            eq_(False, script.should_process_lane(child))

            script = CacheRepresentationPerLane(
                self._db, ["--min-depth=1"], testing=True
            )
            eq_(1, script.min_depth)
            eq_(False, script.should_process_lane(parent))
            eq_(True, script.should_process_lane(child))

class TestCacheFacetListsPerLane(TestLaneScript):

    def test_default_arguments(self):
        with self.temp_config() as config:
            # TODO: It would be more robust to set a standard
            # facet configuration rather than relying on the default.
            # This is what core/tests/test_lanes.py does.
            #
            # However, getting this to work requires changing the way
            # the LaneSweeperScript is initialized. Currently the
            # initialization of a CirculationManager object resets the
            # current configuration to the default.
            #
            # In the absense of this ability we're just testing that
            # there _are_ default values for these things -- we don't
            # really care what they are.
            script = CacheFacetListsPerLane(self._db, [], testing=True)
            eq_(1, len(script.orders))
            eq_(1, len(script.availabilities))
            eq_(1, len(script.collections))

    def test_arguments(self):
        with self.temp_config() as config:
            script = CacheFacetListsPerLane(
                self._db, ["--order=title", "--order=added"],
                testing=True
            )
            eq_(['title', 'added'], script.orders)
            script = CacheFacetListsPerLane(
                self._db, ["--availability=all", "--availability=always"],
                testing=True
            )
            eq_(['all', 'always'], script.availabilities)

            script = CacheFacetListsPerLane(
                self._db, ["--collection=main", "--collection=full"],
                testing=True
            )
            eq_(['main', 'full'], script.collections)

            script = CacheFacetListsPerLane(
                self._db, ['--pages=1'], testing=True
            )
            eq_(1, script.pages)

    def test_process_lane(self):
        with self.temp_config() as config:
            lane = Lane(self._db, self._str)

            script = CacheFacetListsPerLane(
                self._db, ["--availability=all", "--availability=always",
                           "--collection=main", "--collection=full",
                           "--order=title", "--pages=1"],
                testing=True
            )
            with script.app.test_request_context("/"):
                cached_feeds = script.process_lane(lane)
                # 2 availabilities * 2 collections * 1 order * 1 page = 4 feeds
                eq_(4, len(cached_feeds))