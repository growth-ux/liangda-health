from pathlib import Path
import sys
import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.scrape_fu800_mall_images import (
    RemoteProductImage,
    enrich_jd_images_with_detail,
    parse_jd_module_images,
    pick_jd_detail_image,
)


def test_parse_jd_module_images_extracts_detail_url():
    raw = """
    <ul>
    <li class="jSubObject gl-item">
      <div class="jPic">
        <a href="//item.jd.com/100104276720.html?pcdk=demo" title="中盐低钠盐400g*5【未加碘】减盐不减咸 低钠 吃好盐 选中盐">
          <img src="//img14.360buyimg.com/n7/jfs/t1/demo.jpg" />
        </a>
      </div>
      <div class="jDesc">
        <a href="//item.jd.com/100104276720.html?pcdk=demo" title="中盐低钠盐400g*5【未加碘】减盐不减咸 低钠 吃好盐 选中盐">商品</a>
      </div>
    </li>
    </ul>
    <span class="clr"></span>
    """

    items = parse_jd_module_images(raw, "https://mall.jd.com/view_search-2178728-0-99-1-24-1.html")
    assert len(items) == 1
    assert items[0].goods_id == "100104276720"
    assert items[0].detail_url is not None
    assert items[0].detail_url.startswith("https://item.jd.com/100104276720.html")


def test_pick_jd_detail_image_prefers_largest_image_from_detail_page():
    html = """
    <script>
    var pageConfig = {
      product: {
        skuid: 100104276720,
        imageList: ["jfs/t1/71456/26/26475/65425/66ac5242F22c745dc/001ea595e6eda20e.jpg"]
      }
    };
    </script>
    <div class="spec-list">
      <img src="//img10.360buyimg.com/n5/jfs/t1/small.jpg" />
      <img src="//img10.360buyimg.com/n1/jfs/t1/large.jpg" />
    </div>
    """

    image_url = pick_jd_detail_image(html)
    assert image_url == "https://img10.360buyimg.com/n1/s720x720_jfs/t1/71456/26/26475/65425/66ac5242F22c745dc/001ea595e6eda20e.jpg"


def test_pick_jd_detail_image_falls_back_to_existing_detail_images():
    html = """
    <div class="spec-list">
      <img src="//img10.360buyimg.com/n5/jfs/t1/small.jpg" />
      <img src="//img10.360buyimg.com/n1/jfs/t1/large.jpg" />
    </div>
    """

    image_url = pick_jd_detail_image(html)
    assert image_url == "https://img10.360buyimg.com/n1/jfs/t1/large.jpg"


def test_enrich_jd_images_with_detail_replaces_list_thumbnail_with_detail_main_image(monkeypatch):
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    detail_html = """
    <script>
    var pageConfig = {
      product: {
        skuid: 10211691661797,
        imageList: ["jfs/t1/395518/35/18664/105187/69a52dd5F9cb752e9/008332032024f009.jpg"]
      }
    };
    </script>
    """

    def fake_get(url, headers=None, timeout=20):
        assert "item.jd.com/10211691661797.html" in url
        return FakeResponse(detail_html)

    monkeypatch.setattr("scripts.scrape_fu800_mall_images.requests.get", fake_get)

    images = [
        RemoteProductImage(
            title="蒙牛高钙牛奶营养早餐牛奶送礼推荐礼盒装年货送礼盒 250ml×24盒*2箱",
            url="https://img10.360buyimg.com/n7/jfs/t1/thumb.jpg",
            source_page="https://mall.jd.com/view_search-2113248-17960386-99-1-20-1.html",
            goods_id="10211691661797",
            detail_url="https://item.jd.com/10211691661797.html?pcdk=demo",
        )
    ]

    enriched = enrich_jd_images_with_detail(images)
    assert len(enriched) == 1
    assert enriched[0].source_page.startswith("https://item.jd.com/10211691661797.html")
    assert enriched[0].url.startswith("https://img10.360buyimg.com/n1/s720x720_")
    assert "/n7/" not in enriched[0].url


def test_enrich_jd_images_with_detail_falls_back_to_upgraded_main_image_when_detail_request_fails(monkeypatch):
    def fake_get(url, headers=None, timeout=20):
        raise requests.RequestException("blocked")

    monkeypatch.setattr("scripts.scrape_fu800_mall_images.requests.get", fake_get)

    images = [
        RemoteProductImage(
            title="蒙牛高钙牛奶营养早餐牛奶送礼推荐礼盒装年货送礼盒 250ml×24盒*2箱",
            url="https://img11.360buyimg.com/n7/jfs/t1/395518/35/18664/105187/69a52dd5F9cb752e9/008332032024f009.jpg",
            source_page="https://mall.jd.com/view_search-2113248-17960386-99-1-20-1.html",
            goods_id="10211691661797",
            detail_url="https://item.jd.com/10211691661797.html?pcdk=demo",
        )
    ]

    enriched = enrich_jd_images_with_detail(images)
    assert len(enriched) == 1
    assert enriched[0].source_page.startswith("https://item.jd.com/10211691661797.html")
    assert enriched[0].url == "https://img10.360buyimg.com/n1/s720x720_jfs/t1/395518/35/18664/105187/69a52dd5F9cb752e9/008332032024f009.jpg"
