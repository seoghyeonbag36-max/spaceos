"""프론트 정적 서빙의 캐시 정책 — 배포 뒤 옛 화면이 남지 않게.

2026-09-13: Deploy 가 성공했는데 사용자 화면에는 개명 전 빌드(로고 S · 서울·거점 탭)가 떠 있었다.
index.html 에 Cache-Control 이 없어 브라우저가 Last-Modified 휴리스틱으로 재검증 없이 재사용했다.
이 그물은 index.html 이 매번 재검증되고, 해시가 붙은 assets 만 오래 캐시되는지를 본다.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import FrontendFiles


def _client(tmp_path) -> TestClient:
    (tmp_path / "index.html").write_text("<!doctype html><title>PlaceOS</title>", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-AbC123.js").write_text("console.log(1)", encoding="utf-8")
    app = FastAPI()
    app.mount("/", FrontendFiles(directory=str(tmp_path), html=True), name="frontend")
    return TestClient(app)


def test_index_html_is_revalidated_every_time(tmp_path):
    client = _client(tmp_path)
    for url in ("/", "/index.html", "/favicon.svg"):
        resp = client.get(url)
        assert resp.status_code == 200, url
        assert resp.headers["cache-control"] == "no-cache", url


def test_hashed_assets_are_immutable(tmp_path):
    resp = _client(tmp_path).get("/assets/index-AbC123.js")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_revalidation_304_keeps_no_cache(tmp_path):
    client = _client(tmp_path)
    etag = client.get("/").headers["etag"]
    resp = client.get("/", headers={"If-None-Match": etag})
    assert resp.status_code == 304
    assert resp.headers["cache-control"] == "no-cache"


def test_missing_file_gets_no_long_cache(tmp_path):
    resp = _client(tmp_path).get("/assets/missing-000.js")
    assert resp.status_code == 404
    assert "immutable" not in resp.headers.get("cache-control", "")
