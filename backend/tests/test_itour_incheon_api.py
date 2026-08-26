from models import BusinessCategory
from services.external.itour_incheon_api import ItourIncheonApiClient, to_imported_business


def test_to_imported_business_maps_lodging_categories():
    assert (
        to_imported_business("외국인관광도시민박업", "허브게스트하우스", "인천광역시 영종구 백년로9번길 8-1", "").category
        == BusinessCategory.LODGING
    )
    assert to_imported_business("호스텔업", "테스트호스텔", "인천광역시 영종구 1", "").category == BusinessCategory.LODGING
    assert to_imported_business("관광호텔업", "테스트호텔", "인천광역시 영종구 1", "").category == BusinessCategory.LODGING


def test_to_imported_business_maps_restaurant_experience_leisure():
    assert to_imported_business("관광식당업", "테스트식당", "주소", "").category == BusinessCategory.RESTAURANT
    assert to_imported_business("일반야영장업", "테스트캠핑장", "주소", "").category == BusinessCategory.EXPERIENCE
    assert (
        to_imported_business("기타유원시설업(기타테마파크업)", "테스트파크", "주소", "").category
        == BusinessCategory.LEISURE
    )


def test_to_imported_business_skips_out_of_scope_categories():
    """여행사(B2B)/카지노/국제회의 등은 손님에게 추천할 "장소"가 아니므로
    sangga_api.py와 동일한 원칙으로 건너뛴다(강제 매핑하지 않음)."""
    assert to_imported_business("종합여행업", "테스트여행사", "주소", "") is None
    assert to_imported_business("카지노업", "테스트카지노", "주소", "") is None
    assert to_imported_business("국제회의기획업", "테스트기획사", "주소", "") is None


def test_to_imported_business_skips_duty_free_wholesalers():
    """관광면세업은 실제 라이브 조회에서 "풍림명품물산㈜" 같은 면세품 도매/유통
    법인만 나와서(추측이 아니라 dry-run으로 직접 확인) 의도적으로 매핑하지
    않는다 - 손님이 찾아갈 수 있는 매장이 아니다."""
    assert to_imported_business("관광면세업", "풍림명품물산㈜", "주소", "") is None


def test_to_imported_business_falls_back_to_lot_address():
    item = to_imported_business("호스텔업", "테스트호스텔", "", "영종구 중산동 100")
    assert item is not None
    assert item.address == "영종구 중산동 100"


def test_to_imported_business_skips_when_no_address_or_name():
    assert to_imported_business("호스텔업", "이름없음", "", "") is None
    assert to_imported_business("호스텔업", "", "주소", "") is None


def test_to_imported_business_external_id_is_stable_and_dedupes_same_name_and_address():
    a = to_imported_business("호스텔업", "동일호스텔", "동일주소", "")
    b = to_imported_business("호스텔업", "동일호스텔", "동일주소", "")
    assert a.external_id == b.external_id

    different = to_imported_business("호스텔업", "다른호스텔", "동일주소", "")
    assert different.external_id != a.external_id


def test_fetch_by_city_parses_real_xml_shape(monkeypatch):
    """가이드/실제 라이브 호출로 확인한 응답 형태(restVOes > TourStatistics
    반복) 그대로 파싱되는지 확인 - 실제 네트워크 호출은 하지 않는다."""
    import httpx

    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <restVOes>
        <TourStatistics>
            <regst_org>영종구</regst_org>
            <busi_mid_lvl_nm>호스텔업</busi_mid_lvl_nm>
            <company_nm>테스트호스텔</company_nm>
            <tel_no></tel_no>
            <road_addr>인천광역시 영종구 테스트로 1</road_addr>
            <addr></addr>
        </TourStatistics>
        <TourStatistics>
            <regst_org>영종구</regst_org>
            <busi_mid_lvl_nm>종합여행업</busi_mid_lvl_nm>
            <company_nm>테스트여행사</company_nm>
            <tel_no></tel_no>
            <road_addr>인천광역시 영종구 테스트로 2</road_addr>
            <addr></addr>
        </TourStatistics>
    </restVOes>"""

    def fake_get(self, url, *args, **kwargs):
        return httpx.Response(200, text=sample_xml, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    results = ItourIncheonApiClient().fetch_by_city()

    assert len(results) == 1  # 종합여행업은 범위 밖이라 건너뜀
    assert results[0].name_ko == "테스트호스텔"
    assert results[0].category == BusinessCategory.LODGING
