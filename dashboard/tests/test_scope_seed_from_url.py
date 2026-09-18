"""A link into a scope opens on it — scope_selector.seed_from_params.

PLAN-2026-09-18-data-pages.md §3, step B3. The Key Indicator drill-down's
"Por área" rows link to ``/Desgloses?bd_area=<name>&ki=…``, and a card on
Desgloses links to ``?bd_zone=<name>&ki=…``. Both cause a full page load, on
which render_scope_selectors resets the cascade to "any" — unless the URL
names a scope, which is what these pin.
"""

from app.components.scope_selector import seed_from_params


def test_no_params_means_no_seed():
    assert seed_from_params("bd", {}) == {}
    assert seed_from_params("bd", None) == {}
    assert seed_from_params("bd", {"ki": "ki_new_people_real"}) == {}


def test_an_area_param_seeds_the_area():
    assert seed_from_params("bd", {"bd_area": "Angol 1"}) == {"bd_area_val": "Angol 1"}


def test_the_deepest_level_wins():
    seed = seed_from_params("bd", {"bd_zone": "Angol", "bd_district": "Angol A",
                                   "bd_area": "Angol 1"})
    assert seed == {"bd_area_val": "Angol 1"}
    seed = seed_from_params("bd", {"bd_zone": "Angol", "bd_district": "Angol A"})
    assert seed == {"bd_district_val": "Angol A"}


def test_a_list_valued_param_takes_its_first_value():
    assert seed_from_params("bd", {"bd_zone": ["Angol", "Talcahuano"]}) == {"bd_zone_val": "Angol"}


def test_blank_and_other_prefixes_are_ignored():
    assert seed_from_params("bd", {"bd_zone": "  ", "sc_area": "Angol 1"}) == {}
