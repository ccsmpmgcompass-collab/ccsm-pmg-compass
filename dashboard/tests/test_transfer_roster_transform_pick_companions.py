"""_pick_companions() had no test coverage at all before a real live IMOS
roster pull (2026-08-06, run 31129784751) hit a 5-person companionship and
raised ValueError, killing the entire roster pull over one outlier area.
Fixed to log + truncate instead of raise; these tests lock that in."""
from app.ingestion.transfer_roster_transform import _pick_companions


def test_single_missionary():
    assert _pick_companions(["Alice Smith"], [""]) == ("Alice Smith", "", "", "")


def test_pair_sc_first_in_file_order():
    comp1, comp2, comp3, comp4 = _pick_companions(
        ["Alice Smith", "Bob Jones"], ["SC", ""])
    assert (comp1, comp2, comp3, comp4) == ("Alice Smith", "Bob Jones", "", "")


def test_pair_sc_listed_second_still_becomes_comp1():
    comp1, comp2, comp3, comp4 = _pick_companions(
        ["Bob Jones", "Alice Smith"], ["", "SC"])
    assert (comp1, comp2, comp3, comp4) == ("Alice Smith", "Bob Jones", "", "")


def test_quad_no_sc_fills_all_four_slots():
    names = ["Alice", "Bob", "Carol", "Dave"]
    result = _pick_companions(names, ["", "", "", ""])
    assert result == ("Alice", "Bob", "Carol", "Dave")


def test_five_person_companionship_truncates_instead_of_raising():
    names = ["Corben Low", "Carlos Laiton", "Zackary Butterfield",
             "Gustavo Caetano", "Collin Anderson"]
    result = _pick_companions(names, ["", "", "", "", ""])
    assert len(result) == 4
    # comp1 (no SC present) is the first name in file order; the 5th name
    # (last in file order) is the one dropped, comp2-4 keep the middle three.
    assert result == ("Corben Low", "Carlos Laiton", "Zackary Butterfield",
                       "Gustavo Caetano")


def test_five_person_companionship_preserves_sc_even_if_listed_last():
    names = ["A", "B", "C", "D", "Senior Comp"]
    positions = ["", "", "", "", "SC"]
    result = _pick_companions(names, positions)
    assert result[0] == "Senior Comp"
    assert len(result) == 4
