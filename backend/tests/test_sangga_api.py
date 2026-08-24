from models import BusinessCategory
from services.external.sangga_api import map_category, to_imported_store


def test_map_category_lodging():
    assert map_category("I1", "I101") == BusinessCategory.LODGING


def test_map_category_cafe_is_the_non_alcoholic_beverage_mid_category():
    assert map_category("I2", "I212") == BusinessCategory.CAFE


def test_map_category_other_food_mid_categories_are_restaurant():
    assert map_category("I2", "I201") == BusinessCategory.RESTAURANT
    assert map_category("I2", "I211") == BusinessCategory.RESTAURANT


def test_map_category_arts_and_culture_mid_categories_are_experience():
    assert map_category("R1", "R101") == BusinessCategory.EXPERIENCE
    assert map_category("R1", "R102") == BusinessCategory.EXPERIENCE


def test_map_category_sports_and_amusement_mid_categories_are_leisure():
    assert map_category("R1", "R103") == BusinessCategory.LEISURE
    assert map_category("R1", "R104") == BusinessCategory.LEISURE


def test_map_category_retail_is_shopping():
    assert map_category("G2", "G208") == BusinessCategory.SHOPPING


def test_map_category_out_of_scope_categories_return_none():
    assert map_category("Q1", "Q102") is None
    assert map_category("P1", "P101") is None


def test_to_imported_store_combines_name_and_branch():
    item = {
        "bizesId": "MA0101",
        "bizesNm": "영종빵집",
        "brchNm": "운서점",
        "indsLclsCd": "I2",
        "indsMclsCd": "I210",
        "rdnmAdr": "인천광역시 영종구 영종대로 1",
    }
    store = to_imported_store(item)
    assert store is not None
    assert store.name_ko == "영종빵집 운서점"
    assert store.category == BusinessCategory.RESTAURANT
    assert store.address == "인천광역시 영종구 영종대로 1"


def test_to_imported_store_falls_back_to_lot_address():
    item = {
        "bizesId": "MA0102",
        "bizesNm": "영종카페",
        "brchNm": "",
        "indsLclsCd": "I2",
        "indsMclsCd": "I212",
        "rdnmAdr": "",
        "lnoAdr": "인천광역시 영종구 중산동 100",
    }
    store = to_imported_store(item)
    assert store is not None
    assert store.address == "인천광역시 영종구 중산동 100"


def test_to_imported_store_skips_out_of_scope_category():
    item = {
        "bizesId": "MA0103",
        "bizesNm": "동네병원",
        "brchNm": "",
        "indsLclsCd": "Q1",
        "indsMclsCd": "Q102",
        "rdnmAdr": "인천광역시 영종구 1",
    }
    assert to_imported_store(item) is None


def test_to_imported_store_skips_when_no_address_available():
    item = {
        "bizesId": "MA0104",
        "bizesNm": "주소없는가게",
        "brchNm": "",
        "indsLclsCd": "I1",
        "indsMclsCd": "I101",
        "rdnmAdr": "",
        "lnoAdr": "",
    }
    assert to_imported_store(item) is None
