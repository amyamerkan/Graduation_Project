from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests

from .normalization import clean_text, stable_id


CATALOGUE_VERSION = "2026.9.0"
CATALOGUE_URL = "https://pypi.org/project/vietnam-provinces/2026.9.0/"
TOURISM_ROOT = "https://csdl.vietnamtourism.gov.vn"
EFFECTIVE_DATE = "2025-07-01"
LEGACY_DATE = "2025-06-30"
CURRENT_SNAPSHOT_DATE = "2026-10-24"


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


class PublicCrawler:
    def __init__(self, directory, delay=.8):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.session = requests.Session()
        self.agent = "VN-Admin-Tourism-Thesis/1.0"
        self.session.headers["User-Agent"] = self.agent
        self.robots = {}
        self.last_request = {}
        self.manifest = []

    def get(self, url, *, check_robots=True):
        host = urlsplit(url).netloc
        if check_robots:
            if host not in self.robots:
                robot_url = urlsplit(url).scheme + "://" + host + "/robots.txt"
                response = self.session.get(robot_url, timeout=25)
                if response.status_code not in (200, 404):
                    response.raise_for_status()
                robot = RobotFileParser()
                robot.parse(response.text.splitlines() if response.status_code == 200 else [])
                self.robots[host] = robot
            if not self.robots[host].can_fetch(self.agent, url):
                raise ValueError("robots.txt disallows " + url)
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.directory / (key + ".html")
        if path.exists():
            body = path.read_bytes()
            status = "cached"
        else:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request.get(host, 0))))
            response = self.session.get(url, timeout=35)
            self.last_request[host] = time.monotonic()
            response.raise_for_status()
            body = response.content
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(body)
            temporary.replace(path)
            status = response.status_code
        self.manifest.append({"url": url, "file": path.name, "status": status, "bytes": len(body),
                              "sha256": hashlib.sha256(body).hexdigest(), "retrieved_at": datetime.now(timezone.utc).isoformat()})
        return BeautifulSoup(body, "html.parser")


def _record(kind, data, domain="administration", source="vietnam-provinces", url=CATALOGUE_URL):
    return {"record_id": stable_id(kind, data.get("snapshot", ""), data.get("code", ""), data.get("name", ""), url),
            "record_type": kind, "domain": domain, "source_name": source, "source_url": url, "data": data}


def collect_administration():
    import importlib.metadata
    from vietnam_provinces import Province, Ward, legacy
    from vietnam_provinces import _province_conversion_2025 as province_bridges, _ward_conversion_2025 as ward_bridges
    from importlib.resources import files

    if importlib.metadata.version("vietnam-provinces") != CATALOGUE_VERSION:
        raise ValueError("Administrative catalogue version mismatch")
    provinces = {int(item.code): item for item in Province.iter_all()}
    old_provinces = {int(item.code): item for item in legacy.Province.iter_all()}
    districts = {int(item.code): item for item in legacy.District.iter_all()}
    wards = {int(item.code): item for item in Ward.iter_all()}
    old_wards = {int(item.code): item for item in legacy.Ward.iter_all()}
    if len(provinces) != 34 or len(wards) != 3321 or len(old_provinces) != 63:
        raise ValueError("Unexpected administrative catalogue counts")
    records = []
    for snapshot, collection, level, width in (
        ("legacy", old_provinces, "province", 2), ("legacy", districts, "district", 3),
        ("legacy", old_wards, "ward", 5), ("current", provinces, "province", 2), ("current", wards, "ward", 5),
    ):
        for code, item in sorted(collection.items()):
            province_code = code if level == "province" else int(item.province_code)
            province = (old_provinces if snapshot == "legacy" else provinces)[province_code]
            data = {"snapshot": snapshot, "level": level, "name": item.name, "code": str(code).zfill(width),
                    "province_code": str(province_code).zfill(2), "province_name": province.name,
                    "catalogue_version": CATALOGUE_VERSION, "snapshot_date": LEGACY_DATE if snapshot == "legacy" else CURRENT_SNAPSHOT_DATE,
                    "division_type": str(item.division_type.value), "country": "VN"}
            if snapshot == "legacy":
                data["valid_to"] = LEGACY_DATE
            if level == "ward" and snapshot == "legacy":
                data["district_code"] = str(int(item.district_code)).zfill(3)
                data["district_name"] = districts[int(item.district_code)].name
            if level == "district":
                data["district_code"] = str(code).zfill(3)
            time_label = "trước sắp xếp tháng 7/2025" if snapshot == "legacy" else "được thu thập ngày " + CURRENT_SNAPSHOT_DATE
            data["description"] = f"Theo danh mục {time_label}, {item.name} có mã {data['code']}, cấp {level}, thuộc {province.name}. Mốc snapshot: {data['snapshot_date']}."
            records.append(_record("administrative_snapshot", data))
    baseline = json.loads((files("vietnam_provinces")/"data/nested-divisions.json").read_text())
    baseline_codes = {"province":set(), "ward":set()}
    baseline_names = {}
    for province in baseline:
        for level, units, width in (("province", [province], 2), ("ward", province["wards"], 5)):
            for unit in units:
                code = int(unit["code"])
                baseline_codes[level].add(code)
                baseline_names[level, code] = unit["name"]
                data = {"snapshot": "reorganized2025", "level":level, "name":unit["name"], "code":str(code).zfill(width),
                        "province_code":str(province["code"]).zfill(2), "province_name":province["name"],
                        "catalogue_version":CATALOGUE_VERSION, "snapshot_date":EFFECTIVE_DATE, "valid_from":EFFECTIVE_DATE,
                        "country":"VN", "division_type":unit["division_type"],
                        "description":f"Danh mục sau sắp xếp 2025: {unit['name']}, mã {str(code).zfill(width)}, thuộc {province['name']}. Mốc snapshot: {EFFECTIVE_DATE}; không dùng tên cập nhật năm 2026 để suy ngược cho năm 2025."}
                records.append(_record("administrative_snapshot", data))
    skipped = []
    for level, bridges, old_items, new_items in (
        ("province", province_bridges.OLD_TO_NEW, old_provinces, provinces),
        ("ward", ward_bridges.OLD_TO_NEW, old_wards, wards),
    ):
        for old_code, bridge in sorted(bridges.items()):
            if old_code not in old_items:
                skipped.append({"level": level, "old_code": old_code})
                continue
            destinations = bridge.new_provinces if level == "province" else bridge.new_wards
            for destination in destinations:
                new_code = destination.code
                if new_code not in new_items or new_code not in baseline_codes[level]:
                    skipped.append({"level": level, "old_code": old_code, "new_code": new_code})
                    continue
                old = old_items[old_code]
                new_name = baseline_names[level, new_code]
                width = 2 if level == "province" else 5
                partial = bool(getattr(bridge.old_ward, "is_partly_merged", False)) if level == "ward" else len(destinations) > 1
                data = {"level": level, "old_code": str(old_code).zfill(width), "new_code": str(new_code).zfill(width),
                        "old_name": old.name, "new_name": new_name, "name": old.name,
                        "code": f"{old_code}-{new_code}", "is_partial": partial, "valid_from": EFFECTIVE_DATE,
                        "catalogue_version": CATALOGUE_VERSION, "country": "VN"}
                data["description"] = (f"Bảng chuyển đổi danh mục 2025: {old.name}, mã cũ {data['old_code']}, liên hệ với "
                    f"{new_name}, mã mới {data['new_code']}. " +
                    ("Chỉ chuyển một phần hoặc có nhiều đơn vị kế tiếp; không được suy ra chuyển toàn bộ địa bàn." if partial else "Đây là liên kết chuyển đổi giữa hai snapshot danh mục.") +
                    f" Mốc chuyển đổi được nguồn ghi nhận: {EFFECTIVE_DATE}.")
                records.append(_record("administrative_conversion", data))
    report = {"current_provinces": len(provinces), "current_wards": len(wards), "legacy_provinces": len(old_provinces),
              "legacy_districts": len(districts), "legacy_wards": len(old_wards), "records": len(records),
              "conversion_links": sum(row["record_type"] == "administrative_conversion" for row in records), "skipped_conversion_links": skipped,
              "snapshot_dates":[LEGACY_DATE,EFFECTIVE_DATE,CURRENT_SNAPSHOT_DATE],
              "source": CATALOGUE_URL, "license": "GPL-3.0-or-later", "source_verified": False,
              "scope": "Versioned community catalogue attributed to NSO; 2025 snapshot and conversion reference, not proof of every current 2026 boundary."}
    return records, provinces, report


def parse_tourism_detail(soup):
    main = soup.select_one("main")
    if main is None:
        return None
    heading = main.select_one("h4")
    if heading is None:
        return None
    card = heading.find_parent("div", class_="listing-shot")
    if card is None:
        return None
    title = clean_text(heading.get_text(" ", strip=True))
    if title.casefold().startswith("lễ hội"):
        return None
    address = next((clean_text(tag.get_text(" ", strip=True)).removeprefix("Địa chỉ:").strip()
                    for tag in card.select("span.d-block") if "Địa chỉ:" in tag.get_text()), "")
    paragraphs = [clean_text(tag.get_text(" ", strip=True)) for tag in card.select(".content-detail")]
    description = "\n".join(dict.fromkeys(text for text in paragraphs if text))
    if len(description) < 60:
        return None
    return {"name": title, "address": address, "description": description}


def collect_tourism(crawler, provinces, *, per_province=6, progress=None):
    root = crawler.get(TOURISM_ROOT + "/dest/")
    selectors = {}
    for option in root.select("select#province option[value]"):
        value = option.get("value", "")
        codes = {int(part) for part in value.split(",") if part.isdigit()}
        current = codes.intersection(provinces)
        if len(current) == 1:
            selectors[next(iter(current))] = value
    records = {}
    errors = []
    coverage = Counter()
    for province_code, province in sorted(provinces.items()):
        if province_code not in selectors:
            errors.append({"province": province.name, "reason": "missing_directory_province_selector"})
            continue
        seen = set()
        for section in ("dest", "area", "vcgt"):
            if coverage[province_code] >= per_province:
                break
            directory_url = TOURISM_ROOT + "/" + section + "/?" + urlencode({"province": selectors[province_code]})
            try:
                soup = crawler.get(directory_url)
                anchors = soup.select("main h4 a[href]")
                for anchor in anchors:
                    url = urljoin(directory_url, anchor["href"])
                    if urlsplit(url).netloc != urlsplit(TOURISM_ROOT).netloc or not parse_qs(urlsplit(url).query).get("item") or url in seen:
                        continue
                    seen.add(url)
                    if url in records:
                        if records[url]["data"]["province_code"] != str(province_code).zfill(2):
                            errors.append({"url": url, "reason": "conflicting_directory_province_filters"})
                        continue
                    detail = parse_tourism_detail(crawler.get(url))
                    if detail is None:
                        continue
                    detail.update({"province_name": province.name, "province_code": str(province_code).zfill(2),
                                   "province_mapping_basis": "official directory province filter, legacy codes grouped by current province",
                                   "country": "VN", "retrieved_at": datetime.now(timezone.utc).isoformat(), "section": section,
                                   "address_time_scope": "verbatim source address; may still contain legacy district/province names"})
                    records[url] = _record("tourism_place", detail, "tourism", "Cơ sở dữ liệu ngành Du lịch — TITC", url)
                    coverage[province_code] += 1
                    if coverage[province_code] >= per_province:
                        break
            except (requests.RequestException, ValueError) as error:
                errors.append({"url": directory_url, "reason": str(error)})
        if progress:
            write_jsonl(progress, records.values())
        print(json.dumps({"province": province.name, "tourism_records": coverage[province_code], "total": len(records)}), flush=True)
    report = {"documents": len(records), "province_coverage": {str(code).zfill(2): count for code,count in coverage.items()},
              "errors": errors, "source": TOURISM_ROOT, "country": "VN", "per_province_target": per_province}
    return list(records.values()), report


def document_from_record(record):
    data = record["data"]
    title = data["name"]
    if record["record_type"] == "administrative_conversion":
        title = f"{data['old_name']} → {data['new_name']} ({data['old_code']} → {data['new_code']})"
    text = title + ".\n" + data["description"]
    if record["record_type"] == "tourism_place":
        text = title + ".\nĐịa chỉ được nguồn ghi nhận: " + data["address"] + ".\n" + data["description"]
    return {"id": record["record_id"], "domain": record["domain"], "title": title, "text": text,
            "source": {"name": record["source_name"], "url": record["source_url"]},
            "metadata": {"record_type": record["record_type"], "source_verified": False, "country": "VN"}}


def collect_official_administration(crawler):
    index_url = "https://baochinhphu.vn/34-nghi-quyet-cua-ubtvqh-ve-sap-xep-cac-don-vi-hanh-chinh-cap-xa-102250618163209716.htm"
    index = crawler.get(index_url)
    urls = list(dict.fromkeys(a["href"] for a in index.select('.detail-content a[href]')
                             if urlsplit(a["href"]).netloc == "vanban.chinhphu.vn" and "docid=" in a["href"]))
    urls.extend([
        "https://vanban.chinhphu.vn/?classid=1&docid=214409&orggroupid=3&pageid=27160",
        "https://vanban.chinhphu.vn/?classid=1&docid=213930&orggroupid=1&pageid=27160",
        "https://chinhphu.vn/?classid=0&docid=219325&pageid=27160",
    ])
    records, errors = [], []
    for url in urls:
        try:
            soup = crawler.get(url)
            fields = {}
            for row in soup.select("tr"):
                columns = row.find_all("td", recursive=False)
                if len(columns) == 2:
                    key, value = (clean_text(col.get_text(" ", strip=True)) for col in columns)
                    if key in {"Số ký hiệu", "Ngày ban hành", "Ngày có hiệu lực", "Loại văn bản", "Cơ quan ban hành", "Người ký", "Trích yếu"}:
                        fields[key] = value
            if "Số ký hiệu" not in fields or "Trích yếu" not in fields:
                raise ValueError("Missing legal document metadata")
            title = fields["Số ký hiệu"] + ": " + fields["Trích yếu"]
            description = "; ".join(key + ": " + value for key, value in fields.items())
            data = {"name": title, "description": description,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(), "country": "VN",
                    "extraction_scope": "document catalogue metadata only; signed attachment not transcribed",
                    "official_fields": fields}
            records.append(_record("administrative_source_document", data, source="Cổng thông tin điện tử Chính phủ", url=url))
        except (requests.RequestException, ValueError) as error:
            errors.append({"url": url, "reason": str(error)})
    return records, {"documents": len(records), "commune_resolution_links": len(urls)-3, "errors": errors,
                     "scope": "Official legal metadata, not a transcription of legal annexes", "index_url": index_url}


def collect_selected_destinations(crawler, provinces, existing):
    root = crawler.get(TOURISM_ROOT + "/dest/")
    selectors = {}
    for option in root.select("select#province option[value]"):
        value = option["value"]
        codes = {int(part) for part in value.split(",") if part.isdigit()}.intersection(provinces)
        if len(codes) == 1:
            selectors[next(iter(codes))] = value
    targets = [("Hội An",48), ("Mỹ Sơn",48), ("Hạ Long",22), ("Sa Pa",15), ("Phú Quốc",91),
               ("Nha Trang",56), ("Đà Lạt",68), ("Phong Nha",44), ("Cát Bà",31), ("Côn Đảo",79)]
    found = {r["source_url"]:r for r in existing}
    additions, coverage, errors = [], {}, []
    for term, province_code in targets:
        coverage[term] = []
        for section in ("dest", "area"):
            url = TOURISM_ROOT + "/" + section + "/?" + urlencode({"title":term, "province":selectors[province_code]})
            try:
                listing = crawler.get(url)
                anchors = listing.select("main h4 a[href]")
                for anchor in anchors[:2]:
                    detail_url = urljoin(url, anchor["href"])
                    if urlsplit(detail_url).netloc != urlsplit(TOURISM_ROOT).netloc or not parse_qs(urlsplit(detail_url).query).get("item"):
                        continue
                    if detail_url in found:
                        coverage[term].append(found[detail_url]["data"]["name"])
                        continue
                    detail = parse_tourism_detail(crawler.get(detail_url))
                    if not detail or term.casefold() not in detail["name"].casefold():
                        continue
                    detail.update({"province_name":provinces[province_code].name,"province_code":str(province_code).zfill(2),
                                   "country":"VN", "retrieved_at":datetime.now(timezone.utc).isoformat(), "section":section,
                                   "province_mapping_basis":"official directory province filter", "address_time_scope":"verbatim source address; may contain legacy locality names"})
                    record = _record("tourism_place",detail,"tourism","Cơ sở dữ liệu ngành Du lịch — TITC",detail_url)
                    found[detail_url] = record
                    additions.append(record)
                    coverage[term].append(detail["name"])
            except (requests.RequestException, ValueError) as error:
                errors.append({"url":url,"reason":str(error)})
        print(json.dumps({"destination":term,"matched":coverage[term]},ensure_ascii=False),flush=True)
    return additions, {"added_documents":len(additions),"coverage":coverage,"errors":errors}
