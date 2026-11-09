#!/usr/bin/env python3
"""Compose a factory-insight big-data report by orchestrating the factory-insight MCP.

Calls the upstream factory-insight-mcp-server tools and assembles a structured
JSON payload rendered into a professional HTML / Markdown report. Supports
``--dry-run`` which returns a well-formed skeleton from the bundled sample data
WITHOUT contacting the MCP.

Two modes:
  * Enterprise mode (``--enterprise``): resolve the canonical enterprise name,
    then query factory profile (概况/风险), factory capabilities (产能), and
    factory product stats (产品统计).
  * Search mode (``--search`` + ``--address``): query factory_search to find
    factories by keyword and region, and assemble a search-result report.

This file never prints secrets; MCP credentials live in the server's own .env.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import pathlib
import re as _re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from common import (
    REPORT_BANNER,
    REPORT_TYPE,
    attach_pagination,
    call_tool_once,
    collect_detail_pages,
    json_dumps,
    load_json_file,
    paid_call_scope,
    print_json,
)
import mcp_client
from semantic_review import prepare_draft
from render_report import render_html, render_markdown, html_to_pdf

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent.parent / "assets" / "report.example.json"

# Factory-insight MCP tools.
T_FUZZY = "factory_insight_fuzzy_search"
T_PRODUCT_STATS = "factory_insight_factory_product_stats"
T_CAPABILITIES = "factory_insight_factory_capabilities"
T_FACTORY_SEARCH = "factory_insight_factory_search"
T_PROFILE = "factory_insight_factory_profile"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_api_error(value: Any) -> bool:
    """Detect MCP API error responses (not empty data, but actual failures like 405)."""
    if value is None:
        return False
    if isinstance(value, str):
        return any(s in value for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5"))
    if isinstance(value, dict):
        if value.get("_mcp_error") or value.get("_error") or value.get("isError") is True or value.get("error"):
            return True
        for v in value.values():
            if isinstance(v, str) and any(s in v for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5")):
                return True
    return False

def _first_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if _is_api_error(value):
            return []
        if set(value) <= {"text", "error", "code", "_error", "_mcp_error"}:
            return []
        for key in ("resultList", "list", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    if value in (None, "", {}):
        return []
    return []


def _first_record(value: Any) -> Dict[str, Any]:
    for record in _first_list(value):
        if isinstance(record, dict):
            return record
    if isinstance(value, dict) and not _is_api_error(value):
        return value
    return {}


def _text(value: Any, limit: int = 0) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        t = json.dumps(value, ensure_ascii=False)
    else:
        t = str(value)
    t = " ".join(t.split())
    if limit and len(t) > limit:
        return t[: limit - 1].rstrip() + "…"
    return t


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_call(tool: str, arguments: Dict[str, Any]) -> Any:
    try:
        result = call_tool_once(mcp_client.call_tool, tool, arguments)
        # Detect API error responses (405, etc.) and return error marker
        if _is_api_error(result):
            return {"_error": "API错误", "_raw": result}
        return result
    except Exception as exc:
        return {"_error": str(exc)}


def _safe_total(payload: Any) -> Any:
    if isinstance(payload, dict):
        if _is_api_error(payload):
            return None
        return payload.get("total")
    return None


def _payload_status(payload: Any) -> str:
    if _is_api_error(payload):
        return "error"
    if isinstance(payload, dict) and str(payload.get("text") or "").strip() == "查询数据为空":
        return "empty"
    if _first_list(payload) or _safe_total(payload) is not None:
        return "success" if (_first_list(payload) or _safe_total(payload) not in (0, "0")) else "empty"
    if isinstance(payload, dict) and payload:
        return "success"
    return "empty"


def _join_list(value: Any) -> str:
    items = _first_list(value)
    return "、".join(_text(t) for t in items if t) if items else ""


def _parse_cert_list(value: Any) -> List[str]:
    """Parse a messy managementSystemCertification field into discrete certs.

    Upstream returns a list whose entries may themselves pack multiple certs
    with mixed separators, e.g. ``"CCC"`` and ``"ISO9000\\ISO14000?OHSAS18000?QC080000?RoHS"``.
    Split on ``\\``, ``?``, ``,``, ``、``, ``/``, ``;`` and whitespace, then de-dupe
    while preserving order. Non-string items are stringified.
    """
    raw_items = _first_list(value)
    certs: List[str] = []
    seen = set()
    for item in raw_items:
        s = _text(item)
        if not s:
            continue
        # split on common separators (backslash, question mark, comma, Chinese comma, slash, semicolon)
        parts = _re.split(r"[\\?,、/;]+", s)
        for p in parts:
            t = p.strip().strip("\"'").strip()
            if t and t not in seen:
                seen.add(t)
                certs.append(t)
    return certs


def _concentration(rows: List[Mapping[str, Any]], name_key: str, value_key: str, top_n: int = 3) -> Dict[str, Any]:
    """Compute top-N concentration (CRn) and dominant category from {name,count} rows."""
    items = []
    for r in rows:
        try:
            items.append((r.get(name_key, "-"), float(str(r.get(value_key, 0)).replace(",", ""))))
        except (TypeError, ValueError):
            items.append((r.get(name_key, "-"), 0.0))
    total = sum(v for _, v in items)
    if not total:
        return {}
    items.sort(key=lambda x: x[1], reverse=True)
    cr = sum(v for _, v in items[:top_n]) / total * 100
    return {"top": items[0][0], "top_share": items[0][1] / total * 100, "cr": cr, "total": total, "n": len(items)}


def _merge_address_parts(values: Sequence[Any]) -> str:
    """Join address fields without duplicating identical/prefix-overlapping regions."""
    parts: List[str] = []
    for raw in values:
        value = _text(raw)
        if not value or value in parts:
            continue
        joined = "".join(parts)
        if joined and value.startswith(joined):
            parts = [value]
        elif joined.startswith(value):
            continue
        elif value.endswith(("省", "市", "区", "县")) and value in joined:
            continue
        elif parts and value.startswith(parts[-1]):
            parts[-1] = value
        else:
            parts.append(value)
    return "".join(parts)


def _profile_address(value: Any) -> tuple[str, str, str]:
    """Preserve factory profile address evidence without claiming normalization."""
    if isinstance(value, dict):
        source_parts = []
        for key in ("province", "city", "district", "value"):
            raw_part = value.get(key)
            readable_part = "-" if raw_part in (None, "") else _text(raw_part)
            source_parts.append(f"{key}={readable_part}")
        raw_source = "；".join(source_parts)
        admin_parts = [_text(value.get(key)) for key in ("province", "city", "district")]
        admin_parts = [part for part in admin_parts if part]
        detail = _text(value.get("value"))
        overlaps = [part for part in admin_parts if detail and part in detail]
        repeated = [part for part in overlaps if detail.count(part) > 1]
        if detail and overlaps:
            address = detail
            note = (
                "上游 value 原文含重复行政区片段；报告保留 value 原文，未做地理校验。"
                if repeated
                else "上游 value 与省市区层级字段重叠；报告优先展示 value 原文，未做地理校验。"
            )
        else:
            address = _merge_address_parts([*admin_parts, detail])
            note = "按上游省市区与 value 字段保守拼接；未做地理校验。"
        return address, raw_source, note
    raw_text = _text(value)
    if not raw_text:
        return "", "", ""
    return raw_text, raw_text, "上游仅返回单一地址原文；报告不清洗其中潜在重复，未做地理校验。"


def _trim_number(value: float) -> str:
    text = f"{value:,.2f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _reg_capital_text(value: Any) -> str:
    """Readable capital from either a dict or a raw numeric string; keep coin."""
    if isinstance(value, dict):
        amount = value.get("value")
        coin = _text(value.get("coinType"))
    else:
        amount = value
        coin = ""
    if amount in (None, ""):
        return _text(amount)
    raw = _text(amount)
    match = _re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(亿|万)?\s*(.*)$", raw)
    if not match:
        return f"{raw} {coin}".strip()
    number = float(match.group(1))
    unit = match.group(2) or ""
    tail = match.group(3) or ""
    coin = coin or tail
    if unit:
        return f"{_trim_number(number)} {unit} {coin}".strip()
    if number >= 1e8:
        return f"{_trim_number(number / 1e8)} 亿 {coin}".strip()
    if number >= 1e4:
        return f"{_trim_number(number / 1e4)} 万 {coin}".strip()
    return f"{number:,.0f} {coin}".strip()


def _product_tag_summary(value: Any, keyword: str) -> tuple[str, Dict[str, Any]]:
    """Summarise upstream product tags while keeping the raw list in the record.

    The upstream ``mainProducts`` field is an unordered tag set, not a verified
    product catalogue; it often contains cross-industry tags. We keep the count,
    keyword-bearing tags, and a bounded sample of other tags instead of dumping
    the entire comma string into one table cell.
    """
    raw = _join_list(value) if isinstance(value, list) else _text(value)
    parts: List[str] = []
    seen = set()
    for part in _re.split(r"[、,，;；]", raw):
        tag = part.strip()
        if tag and tag not in seen:
            seen.add(tag)
            parts.append(tag)
    if not parts:
        return "", {"total": 0, "hits": 0, "others": 0}
    token = "".join(str(keyword or "").casefold().split())
    hits = [p for p in parts if token and token in "".join(p.casefold().split())]
    others = [p for p in parts if p not in hits]
    summary = f"上游标签 {len(parts)} 项"
    if hits:
        summary += f"，含关键词 {len(hits)} 项：{'、'.join(hits[:8])}"
    if others:
        summary += f"；其他标签 {len(others)} 项，如 {'、'.join(others[:4])}"
    if len(hits) > 8 or len(others) > 4:
        summary += "…"
    return summary, {"total": len(parts), "hits": len(hits), "others": len(others)}


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

def resolve_enterprise_name(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {"keyword": "", "enterprise": "", "resolved": False, "reason": "关键词为空"}
    if any(suffix in raw for suffix in ("公司", "集团", "有限", "院", "厂", "中心", "事务所", "合作社", "合伙")):
        return {"keyword": raw, "enterprise": raw, "resolved": True, "reason": "视为企业全称"}
    fuzzy = _safe_call(T_FUZZY, {"matchKeyword": raw, "pageSize": 1})
    record = _first_record(fuzzy)
    name = str(record.get("name") or "").strip()
    if name:
        return {"keyword": raw, "enterprise": name, "resolved": True, "reason": "由关键词模糊查询补全", "fuzzy_total": _int(_safe_total(fuzzy)), "record": record}
    return {"keyword": raw, "enterprise": raw, "resolved": False, "reason": "模糊查询未命中企业全称，按关键词直查"}


# --------------------------------------------------------------------------- #
# Enterprise profile helpers (from fuzzy_search record)
# --------------------------------------------------------------------------- #

def _extract_profile(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract enterprise profile fields from a fuzzy_search record."""
    return {
        "name": _text(record.get("name")),
        "reg_capital": record.get("regCapitalValue"),
        "reg_capital_coin": _text(record.get("regCapitalCoinType")),
        "annual_turnover": _text(record.get("annualTurnover")),
        "oper_status": _text(record.get("operStatus")),
        "enterprise_type": _text(record.get("enterpriseType")),
        "found_time": _text(record.get("foundTime")),
        "legal_rep": _text(record.get("legalRepresentative")),
        "address": _text(record.get("address")),
        "homepage": _text(record.get("homepage")),
    }


def _format_capital(val: Any, coin: str = "") -> str:
    """Format capital value: 10995210218.0 -> '109.95 亿'."""
    try:
        v = float(val)
        if v >= 1e8:
            s = f"{v / 1e8:.2f} 亿"
        elif v >= 1e4:
            s = f"{v / 1e4:.2f} 万"
        else:
            s = f"{v:.0f}"
        if coin:
            s += f" {coin}"
        return s
    except (TypeError, ValueError):
        return _text(val) if val else "-"


def _enrich_metrics_with_profile(metrics: List[Dict[str, Any]], record: Any) -> List[Dict[str, Any]]:
    """Append enterprise profile metrics from a fuzzy_search record."""
    if not isinstance(record, dict):
        return metrics
    _prof = _extract_profile(record)
    if _prof.get("reg_capital") and _prof["reg_capital"] not in ("-", "", None):
        metrics.append({"label": "注册资本", "value": _format_capital(_prof["reg_capital"], _prof.get("reg_capital_coin", "")), "hint": "工商登记注册资本"})
    if _prof.get("found_time") and _prof["found_time"] != "-":
        metrics.append({"label": "成立时间", "value": _prof["found_time"], "hint": "工商登记成立日期"})
    if _prof.get("oper_status") and _prof["oper_status"] != "-":
        metrics.append({"label": "经营状态", "value": _prof["oper_status"], "hint": "工商登记经营状态"})
    if _prof.get("enterprise_type") and _prof["enterprise_type"] != "-":
        metrics.append({"label": "企业类型", "value": _prof["enterprise_type"], "hint": "工商登记企业类型"})
    if _prof.get("legal_rep") and _prof["legal_rep"] != "-":
        metrics.append({"label": "法定代表人", "value": _prof["legal_rep"], "hint": "工商登记法定代表人"})
    return metrics

def _derive_core_metrics(metrics: List[Dict[str, Any]], core: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Derive additional metrics from core analysis sections."""
    product_stats = core.get("product_stats", []) if isinstance(core, dict) else []
    profile = core.get("factory_profile", {}) if isinstance(core, dict) else {}
    caps = core.get("factory_capabilities", {}) if isinstance(core, dict) else {}
    if isinstance(product_stats, list) and product_stats:
        metrics.append({"label": "产品类目数", "value": str(len(product_stats)), "hint": "覆盖的产品类目数量"})
        try:
            def _cnt(r):
                v = str(r.get("数量", "0"))
                return int(v) if v.isdigit() else 0
            top_cat = max(product_stats, key=_cnt)
            if top_cat.get("产品类目"):
                metrics.append({"label": "主营类目", "value": str(top_cat["产品类目"]), "hint": "产品数量最多的类目"})
        except (ValueError, TypeError):
            pass
    if isinstance(profile, dict) and profile:
        reg = profile.get("注册资本")
        if reg and str(reg) not in ("-", "", "None"):
            try:
                v = float(str(reg).split()[0])
                if v >= 1e8:
                    s = f"{v/1e8:.2f} 亿"
                elif v >= 1e4:
                    s = f"{v/1e4:.2f} 万"
                else:
                    s = f"{v:.0f}"
                coin = "人民币" if "人民币" in str(reg) else ""
                metrics.append({"label": "注册资本", "value": f"{s} {coin}".strip(), "hint": "工商登记注册资本"})
            except (ValueError, TypeError):
                metrics.append({"label": "注册资本", "value": str(reg), "hint": "工商登记注册资本"})
        found_time = profile.get("成立时间")
        if found_time and str(found_time) not in ("-", "", "None"):
            metrics.append({"label": "成立时间", "value": str(found_time), "hint": "企业工商登记成立日期"})
        factory_type = profile.get("工厂类型")
        if factory_type and str(factory_type) not in ("-", "", "None"):
            metrics.append({"label": "工厂类型", "value": str(factory_type), "hint": "工厂类型分类"})
        risk = profile.get("账期风险")
        if risk and str(risk) not in ("-", "", "None"):
            metrics.append({"label": "账期风险", "value": str(risk), "hint": "上游返回的账期风险指标"})
    if isinstance(caps, dict) and caps:
        cert_count = caps.get("管理体系认证数")
        if cert_count and str(cert_count) not in ("-", "", "0", "None"):
            metrics.append({"label": "体系认证数", "value": str(cert_count), "hint": "管理体系认证数量"})
    return metrics


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #

def build_subject(raw: str, resolved: Mapping[str, Any], keyword_type: str) -> Dict[str, Any]:
    return {
        "enterprise": resolved.get("enterprise") or raw,
        "matchKeyword": resolved.get("enterprise") or raw,
        "keywordType": keyword_type,
        "match_raw": raw,
        "resolved": bool(resolved.get("resolved")),
        "resolve_reason": resolved.get("reason", ""),
    }


def build_metrics(profile: Mapping[str, Any], capabilities: Mapping[str, Any], product_stats: Mapping[str, Any], search_total: Any) -> List[Dict[str, Any]]:
    metrics: List[Dict[str, Any]] = []
    p = profile if isinstance(profile, dict) else {}
    c = capabilities if isinstance(capabilities, dict) else {}
    ps = product_stats if isinstance(product_stats, dict) else {}

    scale = _text(p.get("factoryScale"))
    if scale:
        metrics.append({"label": "工厂规模", "value": scale, "hint": "工厂规模等级"})
    lines = _int(c.get("assemblyLine"))
    if lines is not None:
        metrics.append({"label": "生产线数", "value": str(lines), "hint": "生产流水线条数"})
    monthly = _text(c.get("monthlyProductionAmountValue") or p.get("monthlyProductionAmountValue"))
    if monthly:
        metrics.append({"label": "月产值", "value": monthly, "hint": "工厂月产值"})
    brand_count = _int(ps.get("serviceBrandCount"))
    product_count = _int(ps.get("mainProductCount"))
    if brand_count is not None:
        if product_count and brand_count:
            metrics.append({"label": "服务品牌数", "value": str(brand_count), "hint": "服务的品牌数量", "delta": f"产品/品牌 {product_count / brand_count:.1f}"})
        else:
            metrics.append({"label": "服务品牌数", "value": str(brand_count), "hint": "服务的品牌数量"})
    if product_count is not None:
        metrics.append({"label": "主营产品数", "value": str(product_count), "hint": "主营产品数量"})
    if search_total is not None:
        metrics.append({"label": "检索结果", "value": _text(search_total), "hint": "工厂检索命中数"})
    return [m for m in metrics if m.get("value") not in ("", None, "-")]


def _capability_kinds(capabilities: Mapping[str, Any]) -> Dict[str, bool]:
    production_keys = {
        "生产线数", "月产值", "打版人数", "检验人数", "是否支持打样", "工厂工艺", "主要设备",
    }
    return {
        "production": any(key in capabilities for key in production_keys),
        "certification": any(key in capabilities for key in ("管理体系认证", "生产质量认证")),
        "identity": "企业平台/身份认证" in capabilities,
    }


def build_caliber(subject: Mapping[str, Any], core: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    if subject.get("mode") == "search":
        return {
            "match_target": subject.get("match_raw"),
            "match_type": f"工厂检索模式（keywordType={subject.get('keywordType')}，address={subject.get('address') or []}）",
            "data_scope": "工厂检索本次采集候选样本",
            "products": ["工厂检索"],
            "limit": "地区条件由上游执行；若单条记录未返回地区/地址字段，报告会明确标注不可逐条独立复核。检索结果不等同于已审核供应商。",
        }
    ca = core if isinstance(core, Mapping) else {}
    profile_value = ca.get("factory_profile")
    capabilities_value = ca.get("factory_capabilities")
    product_stats_value = ca.get("product_stats")
    profile: Dict[str, Any] = profile_value if isinstance(profile_value, dict) else {}
    capabilities: Dict[str, Any] = capabilities_value if isinstance(capabilities_value, dict) else {}
    product_stats: List[Any] = product_stats_value if isinstance(product_stats_value, list) else []
    kinds = _capability_kinds(capabilities)
    scopes: List[str] = []
    if profile:
        scopes.append("工厂概况与上游风险指标")
    if kinds["production"]:
        scopes.append("上游生产相关字段")
    if kinds["certification"]:
        scopes.append("管理体系/质量认证字段")
    if kinds["identity"]:
        scopes.append("平台身份信息线索")
    if product_stats:
        scopes.append("工厂产品类目统计")
    return {
        "match_target": subject.get("enterprise") or subject.get("match_raw"),
        "match_type": f"工厂概况按企业主体匹配（keywordType={subject.get('keywordType', 'name')}）；工厂检索支持工厂名称/主营产品/产品名称等关键词",
        "data_scope": "、".join(scopes) if scopes else "本次未返回有效工厂字段",
        "products": scopes,
        "limit": "仅呈现上游实际返回字段与信息线索；规模、认证、平台身份及类目标签均需结合原始材料独立核验，不直接证明产能、质量、准入或合作适配。",
    }


def _product_stat_rows(stats: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in _first_list(stats.get("productCategoriesStatInfo")):
        if not isinstance(item, dict):
            continue
        rows.append({
            "产品类目": _text(item.get("name")) or "-",
            "数量": _text(item.get("value") or item.get("count") or "-"),
        })
    return rows


def _sum_product_category_values(stats: Mapping[str, Any]) -> int:
    """Sum the numeric values across productCategoriesStatInfo entries."""
    total = 0
    for item in _first_list(stats.get("productCategoriesStatInfo")):
        if not isinstance(item, dict):
            continue
        v = item.get("value")
        if v is None:
            v = item.get("count")
        try:
            total += int(float(str(v)))
        except (TypeError, ValueError):
            pass
    return total


def build_core_analysis(profile: Mapping[str, Any], capabilities: Mapping[str, Any], product_stats: Mapping[str, Any], search: Any, search_keyword: str = "") -> Dict[str, Any]:
    p = profile if isinstance(profile, dict) else {}
    c = capabilities if isinstance(capabilities, dict) else {}
    ps = product_stats if isinstance(product_stats, dict) else {}

    # 工厂概况 KV
    profile_kv: Dict[str, Any] = {}
    if p.get("name") is not None:
        profile_kv["企业名称"] = _text(p.get("name"))
    if p.get("foundTime"):
        profile_kv["成立时间"] = _text(p.get("foundTime"))
    if p.get("factoryScale"):
        profile_kv["工厂规模"] = _text(p.get("factoryScale"))
    addr, addr_source, addr_note = _profile_address(p.get("factoryAddress"))
    if addr:
        profile_kv["工厂地址"] = addr
        profile_kv["工厂地址原始字段"] = addr_source
        profile_kv["工厂地址说明"] = addr_note
    cap = _reg_capital_text(p.get("regCapital"))
    if cap:
        profile_kv["注册资本"] = cap
    if isinstance(p.get("factoryTypeList"), list) and p["factoryTypeList"]:
        profile_kv["工厂类型"] = "、".join(_text(t) for t in p["factoryTypeList"] if t)
    if p.get("monthlyProductionAmountValue"):
        profile_kv["月产值"] = _text(p.get("monthlyProductionAmountValue"))
    if p.get("accountPeriodRisk"):
        profile_kv["账期风险"] = _text(p.get("accountPeriodRisk"))

    # 工厂产能 KV
    capabilities_kv: Dict[str, Any] = {}
    if c.get("assemblyLine") is not None:
        capabilities_kv["生产线数"] = _text(c.get("assemblyLine"))
    if c.get("monthlyProductionAmountValue"):
        capabilities_kv["月产值"] = _text(c.get("monthlyProductionAmountValue"))
    if c.get("boarderStaffNumber"):
        capabilities_kv["打版人数"] = _text(c.get("boarderStaffNumber"))
    if c.get("inspectionStaffNumber"):
        capabilities_kv["检验人数"] = _text(c.get("inspectionStaffNumber"))
    if c.get("isSupportProofing") is not None:
        capabilities_kv["是否支持打样"] = "是" if _int(c.get("isSupportProofing")) else "否"
    tech = _join_list(c.get("companyTechnicList"))
    if tech:
        capabilities_kv["工厂工艺"] = tech
    cert = _join_list(c.get("managementSystemCertification"))
    cert_list = _parse_cert_list(c.get("managementSystemCertification"))
    if cert_list:
        # parsed discrete certs (split on ?/\/,/etc.) + count, replacing the raw messy blob
        capabilities_kv["管理体系认证"] = "、".join(cert_list)
        capabilities_kv["管理体系认证数"] = str(len(cert_list))
    elif cert:
        capabilities_kv["管理体系认证"] = cert
    ec = _join_list(c.get("enterpriseCertification"))
    if ec:
        capabilities_kv["企业平台/身份认证"] = ec
    device_list = _first_list(c.get("mainDeviceList"))
    if device_list:
        capabilities_kv["主要设备"] = "；".join(
            f"{_text(d.get('equipName'))}({_text(d.get('brand'))})×{_text(d.get('equipNum'))}"
            for d in device_list if isinstance(d, dict)
        )

    # 产品统计表
    product_rows = _product_stat_rows(ps)
    tag_names = _join_list(ps.get("tagNames"))
    if tag_names:
        product_rows_note = f"产品标签：{tag_names}"
    else:
        product_rows_note = "按产品类目统计数量"

    # 工厂检索表
    search_rows = []
    total = None
    if isinstance(search, dict):
        total = search.get("total")
    for item in _first_list(search):
        if not isinstance(item, dict):
            continue
        address_values = []
        address_sources: Dict[str, Any] = {}
        for key in ("province", "city", "district", "address", "addressValue"):
            value = _text(item.get(key))
            if value:
                address_values.append(value)
                address_sources[key] = value
        factory_address_value = item.get("factoryAddress")
        factory_address: Dict[str, Any] = factory_address_value if isinstance(factory_address_value, dict) else {}
        for key in ("province", "city", "district", "value"):
            value = _text(factory_address.get(key))
            if value:
                address_values.append(value)
                address_sources[f"factoryAddress.{key}"] = value
        raw_products = _join_list(item.get("mainProducts")) or "-"
        summary, tag_meta = _product_tag_summary(item.get("mainProducts"), search_keyword)
        company_name = _text(item.get("name")) or "-"
        name_token = "".join(str(search_keyword or "").casefold().split())
        row = {
            "企业名称": company_name,
            "主营产品": summary or "-",
            "主营产品原文": raw_products,
            "主营标签统计": tag_meta,
            "名称含关键词": "是" if name_token and name_token in "".join(company_name.casefold().split()) else "否",
            "注册资本": _reg_capital_text(item.get("regCapital")) or "-",
            "注册资本原文": _text(item.get("regCapital")) or "-",
            "成立日期": _text(item.get("foundTime")) or "-",
            "地区/地址": _merge_address_parts(address_values) or "上游未返回（不可逐条复核）",
            "地址来源字段": address_sources,
        }
        search_rows.append(row)

    capability_kinds = _capability_kinds(capabilities_kv)
    if capability_kinds["production"]:
        capability_title = "生产相关字段"
        capability_note = "上游返回的产线/人员/设备/质检等字段；仅作字段展示，不直接证明产能或履约能力"
    elif capability_kinds["certification"]:
        capability_title = "认证与平台字段"
        capability_note = "上游返回的认证与平台字段，需结合证书或平台原始记录独立核验"
    else:
        capability_title = "平台身份信息线索"
        capability_note = "上游返回的平台/身份字段，仅作信息线索，不代表生产或质量能力"

    sections = [
        {"key": "factory_profile", "title": "工厂概况", "kind": "kv"},
        {"key": "factory_capabilities", "title": capability_title, "kind": "kv", "note": capability_note},
        {"key": "product_stats", "title": "工厂产品类目分布", "kind": "donut", "note": product_rows_note,
         "chart": {"name": "产品类目", "value": "数量"},
         "columns": [("产品类目", "产品类目"), ("数量", "数量")]},
        {"key": "search_records", "title": "工厂检索明细", "kind": "table",
         "note": f"本次检索命中 {total if total is not None else '未知'} 条，展示前 {len(search_rows)} 条；主营产品为上游标签摘要，原文保留在 JSON",
         "columns": [("企业名称", "企业名称"), ("名称含关键词", "名称含关键词"), ("主营产品（标签摘要）", "主营产品"), ("地区/地址", "地区/地址"), ("注册资本", "注册资本"), ("成立日期", "成立日期")]},
    ]

    return {
        "sections": sections,
        "factory_profile": profile_kv,
        "factory_capabilities": capabilities_kv,
        "product_stats": product_rows,
        "search_records": search_rows,
        # raw values for downstream insights
        "main_product_count": _int(ps.get("mainProductCount")),
        "product_category_total": _sum_product_category_values(ps),
        "management_certs": cert_list,
        "account_period_risk": _text(p.get("accountPeriodRisk")),
        "source_status": {
            "factory_profile": _payload_status(profile),
            "factory_capabilities": _payload_status(capabilities),
            "product_stats": _payload_status(product_stats),
            "factory_search": _payload_status(search),
        },
    }


def build_records(core: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in core.get("search_records") or []:
        out.append({
            "企业名称": item.get("企业名称") or "-",
            "主营产品": item.get("主营产品") or "-",
            "注册资本": item.get("注册资本") or "-",
            "成立日期": item.get("成立日期") or "-",
            "地区/地址": item.get("地区/地址") or "-",
        })
    return out[:20]

def build_insights(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    metric_map = {m["label"]: str(m["value"]) for m in metrics}
    if subject.get("mode") == "search":
        rows = core.get("search_records") or []
        if rows:
            auditable = sum(1 for row in rows if row.get("地区/地址") not in (None, "", "-", "上游未返回（不可逐条复核）"))
            insights.append({
                "feature": "工厂检索本次采集样本",
                "evidence": f"本次采集返回 {len(rows)} 条候选记录，其中 {auditable} 条含可逐条复核的地区/地址字段；请求地区={subject.get('address') or []}。",
                "interpretation": "结果仅是上游按关键词与地区筛选的候选样本；缺少地址字段的记录不能在报告内独立复核地区，也不等同于已审核供应商。",
            })
            name_hits = sum(1 for row in rows if row.get("名称含关键词") == "是")
            tag_only = sum(1 for row in rows if row.get("名称含关键词") == "否" and (row.get("主营标签统计") or {}).get("hits"))
            tag_hit_rows = sum(1 for row in rows if (row.get("主营标签统计") or {}).get("hits"))
            multi_tag_rows = sum(1 for row in rows if (row.get("主营标签统计") or {}).get("others"))
            insights.append({
                "feature": "名称与主营标签命中",
                "evidence": f"本次展示 {len(rows)} 条中，企业名称含关键词 {name_hits} 条；主营标签含关键词 {tag_hit_rows} 条，其中仅靠标签命中的 {tag_only} 条；{multi_tag_rows} 条的标签含其他行业词。",
                "interpretation": "名称含关键词不等于同一集团或同一工厂（可能存在“安吉”+“利奥”这类跨词组合）；主营标签是上游标签集合，含跨行业词，不能当主营产品清单或生产证明，需核对注册地、股权与产品证据。",
            })
        else:
            insights.append({
                "feature": "工厂检索数据状态",
                "evidence": "本次检索未返回有效候选记录。",
                "interpretation": "空结果与调用错误应结合 source_status 区分，不推断区域内不存在相关工厂。",
            })
        return insights
    profile_kv = core.get("factory_profile") or {}
    cap_kv = core.get("factory_capabilities") or {}

    if profile_kv.get("工厂规模"):
        insights.append({
            "feature": "工厂规模",
            "evidence": f"工厂规模为“{profile_kv.get('工厂规模')}”。",
            "interpretation": "该值是上游返回的工厂规模标签；不直接证明实际产能、交付能力或采购适配。",
        })
    lines = metric_map.get("生产线数")
    brand = metric_map.get("服务品牌数")
    product = metric_map.get("主营产品数")
    if lines:
        ev = f"拥有生产线 {lines} 条"
        if brand:
            try:
                ln = float(lines)
                bn = float(brand)
                if bn > 0:
                    ev += f"，均摊 {ln / bn:.1f} 条/品牌"
            except (TypeError, ValueError):
                pass
        insights.append({
            "feature": "生产实力",
            "evidence": ev + "。",
            "interpretation": "该项仅描述上游返回的生产线数量；未结合设备状态、班次、稼动率与订单数据，不外推产能或交付能力。",
        })
    if brand and product:
        try:
            bn = float(brand)
            pn = float(product)
            ratio = pn / bn if bn else 0
            insights.append({
                "feature": "产品布局",
                "evidence": f"服务品牌 {brand} 个、主营产品 {product} 项，产品/品牌比 {ratio:.1f}。",
                "interpretation": "该比值仅由上游服务品牌数与主营产品数计算，不直接证明定制化、代工或规模化生产能力。",
            })
        except (TypeError, ValueError):
            pass
    elif brand or product:
        layout_evidence: List[str] = []
        if brand:
            layout_evidence.append(f"服务品牌 {brand} 个")
        if product:
            layout_evidence.append(f"主营产品 {product} 项")
        insights.append({
            "feature": "产品布局",
            "evidence": "、".join(layout_evidence) + "。",
            "interpretation": "以上仅为上游返回的数量字段；字段缺失或分类不足时，不外推产品结构、市场定位或生产能力。",
        })
    product_rows = core.get("product_stats") or []
    if product_rows:
        conc = _concentration(product_rows, "产品类目", "数量", 2)
        if conc:
            if len(product_rows) == 1 and str(conc["top"]) == "其他":
                insights.append({
                    "feature": "产品类目统计范围",
                    "evidence": f"上游产品类目统计仅返回单一“其他”类目，数量 {int(conc['total'])}。",
                    "interpretation": "单一兜底类目不具备结构区分度，不能据此计算有业务意义的集中度，也不能推出实际生产特征、品类布局或周期韧性。",
                })
            else:
                insights.append({
                    "feature": "产品类目样本分布",
                    "evidence": f"“{conc['top']}”类目占比约 {conc['top_share']:.0f}%，前 2 类目合计 {conc['cr']:.0f}%（CR2）。",
                    "interpretation": "该比例仅描述上游已分类记录的当前分布；不直接证明实际生产特征、品类布局或周期韧性。",
                })
    qc_staff = cap_kv.get("检验人数")
    if lines and qc_staff:
        try:
            ln = float(lines)
            qc = float(str(qc_staff).replace("人", ""))
            if ln > 0:
                insights.append({
                    "feature": "质检配置",
                    "evidence": f"生产线 {lines} 条对应质检 {qc_staff} 人，约 {qc / ln:.1f} 人/线。",
                    "interpretation": "该比值仅由上游人数与生产线字段计算；未包含岗位职责、班次或检验流程，不推断品控强度或订单准入能力。",
                })
        except (TypeError, ValueError):
            pass
    if cap_kv.get("管理体系认证") or cap_kv.get("生产质量认证"):
        cert_evidence: List[str] = []
        if cap_kv.get("管理体系认证"):
            cert_evidence.append(str(cap_kv.get("管理体系认证")))
        if cap_kv.get("生产质量认证"):
            cert_evidence.append(str(cap_kv.get("生产质量认证")))
        cert_count = cap_kv.get("管理体系认证数")
        cert_clause = f"（管理体系认证 {cert_count} 项）" if cert_count else ""
        insights.append({
            "feature": "资质认证",
            "evidence": "持有认证：" + "、".join(cert_evidence) + cert_clause + "。",
            "interpretation": "以上仅为上游返回的认证名称字段，需独立核验有效证书、范围与期限；不得替代质量核验、业务审核或风险判断。",
        })
    # 账期风险等级（来源：factory_profile.accountPeriodRisk）
    account_risk = core.get("account_period_risk") or profile_kv.get("账期风险")
    if account_risk:
        risk_norm = account_risk.strip()
        insights.append({
            "feature": "账期风险等级",
            "evidence": f"上游账期风险指标为“{risk_norm}”。",
            "interpretation": "该值仅按上游指标原样展示，不等同于交易事实，不能推出付款条款、回款压力、资金占用、履约表现或长期合作适配。",
        })
    # 数据覆盖度提示：主营产品数远大于已分类类目总量
    main_pc = core.get("main_product_count")
    cat_total = core.get("product_category_total")
    if main_pc and cat_total is not None and main_pc > cat_total * 2 and cat_total >= 0:
        covered_pct = (cat_total / main_pc * 100) if main_pc else 0
        insights.append({
            "feature": "数据覆盖度",
            "evidence": f"主营产品数 {main_pc} 项，但产品类目统计仅覆盖 {cat_total} 项（约 {covered_pct:.0f}%），分类数据存在明显缺口。",
            "interpretation": "产品类目统计覆盖率偏低意味着类目分布图表可能低估真实产品结构；建议结合工厂检索明细与主营产品标签交叉核验，避免以偏概全。",
        })
    if not insights:
        insights.append({
            "feature": "数据完整性",
            "evidence": "部分维度未返回有效数据。",
            "interpretation": "建议核对匹配关键词是否为企业全称，或检查 MCP 连接与上游数据产品覆盖范围。",
        })
    return insights


def build_abstract(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]]) -> str:
    name = subject.get("enterprise") or subject.get("match_raw") or "目标企业"
    if subject.get("mode") == "search":
        rows = core.get("search_records") or []
        return (
            f"本报告以“{name}”为工厂检索关键词，按 keywordType={subject.get('keywordType')}、地区={subject.get('address') or []} 查询。"
            f"本次采集候选样本 {len(rows)} 条；只呈现检索记录与可复核字段，不声称已获得企业工厂概况、产能或产品统计。"
        )
    profile_value = core.get("factory_profile")
    capabilities_value = core.get("factory_capabilities")
    product_stats_value = core.get("product_stats")
    profile: Dict[str, Any] = profile_value if isinstance(profile_value, dict) else {}
    capabilities: Dict[str, Any] = capabilities_value if isinstance(capabilities_value, dict) else {}
    product_stats: List[Any] = product_stats_value if isinstance(product_stats_value, list) else []
    kinds = _capability_kinds(capabilities)
    covered: List[str] = []
    if profile:
        covered.append("工厂概况与上游风险指标")
    if kinds["production"]:
        covered.append("生产相关字段")
    if kinds["certification"]:
        covered.append("管理体系认证字段")
    if kinds["identity"]:
        covered.append("平台身份信息线索")
    if product_stats:
        covered.append("产品类目统计")
    coverage_text = "、".join(covered) if covered else "未返回有效工厂字段"
    parts = [f"本报告以“{name}”为分析对象，仅按实际非空结果呈现：{coverage_text}。"]
    if metrics:
        kv = "、".join(f"{m['label']} {m['value']}" for m in metrics[:5])
        parts.append(f"关键指标包括：{kv}。")
    parts.append("报告仅对上游字段与信息线索作描述；缺失维度不作成功叙述，规模、认证、平台身份和类目标签不直接证明产能、质量或合作适配。")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Dry-run sample
# --------------------------------------------------------------------------- #

def build_dry_run_payload(raw: str, keyword_type: str) -> Dict[str, Any]:
    try:
        sample = load_json_file(SAMPLE_PATH)
    except Exception:
        sample = {}
    sample = sample if isinstance(sample, dict) else {}
    subject = sample.get("subject") or {"enterprise": raw, "matchKeyword": raw, "keywordType": keyword_type, "match_raw": raw}
    subject = {**subject, "match_raw": raw, "keywordType": keyword_type}
    core = sample.get("core_analysis") or {}
    metrics = sample.get("metrics") or []
    return apply_content_review(_assemble(subject, core, metrics, dry_run=True))


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _quality_report(core: Mapping[str, Any]) -> Dict[str, Any]:
    """Section-fill rate from final declared sections and their actual bodies.

    ``0`` is a populated body; None/''/[]/{} is empty. Not an accuracy score.
    """
    ca = core if isinstance(core, dict) else {}
    sections = ca.get("sections")
    if isinstance(sections, list):
        total = len(sections)
        populated = sum(1 for s in sections if isinstance(s, dict) and ca.get(s.get("key")) not in (None, "", [], {}))
    else:
        keys = [k for k in ca if k not in ("sections", "source_status")]
        total = len(keys)
        populated = sum(1 for k in keys if ca.get(k) not in (None, "", [], {}))
    return {
        "total_sections": total,
        "populated_sections": populated,
        "empty_sections": total - populated,
        "coverage_pct": round(populated / max(1, total) * 100),
    }


def _assemble(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]], *, dry_run: bool) -> Dict[str, Any]:
    abstract = build_abstract(subject, core, metrics)
    records = build_records(core)
    insights = build_insights(subject, core, metrics)
    quality_report = _quality_report(core)
    populated = quality_report["populated_sections"]
    if populated == 0:
        import sys
        print("⚠️ 质量门禁警告: 所有核心分析维度均无数据", file=sys.stderr)
    title = (
        f"{subject.get('enterprise') or '目标关键词'} 工厂检索样本报告"
        if subject.get("mode") == "search"
        else f"{subject.get('enterprise') or '目标企业'} 工厂信息分析报告"
    )
    return {
        "report_type": REPORT_TYPE,
        "title": title,
        "banner": REPORT_BANNER,
        "subject": dict(subject),
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": [item["interpretation"] for item in insights][:5] or [abstract[:120]],
        "metrics": list(metrics),
        "caliber": build_caliber(subject, core),
        "core_analysis": dict(core),
        "representative_records": records,
        "insights": insights,
        "data_source": {
            "mcp_server": "factory-insight-mcp-server",
            "products": ([{"name": "工厂检索", "product_id": "66aa4eac4bb1f40b86c46efe"}] if subject.get("mode") == "search" else [
                {"name": "工厂概况", "product_id": "66aa4eac4bb1f40b86c46f0b"},
                {"name": "工厂产能", "product_id": "66aa4eac4bb1f40b86c46ee6"},
                {"name": "工厂产品统计", "product_id": "6725e5b9ba65854594baebd2"},
            ]),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "quality_report": quality_report,
            "source_status": core.get("source_status", {}),
        },
    }


@paid_call_scope
def build_payload_enterprise(raw: str, keyword_type: str, page_size: int) -> Dict[str, Any]:
    resolved = resolve_enterprise_name(raw)
    enterprise = resolved["enterprise"]
    mk_args: Dict[str, Any] = {"matchKeyword": enterprise, "keywordType": keyword_type}
    profile = _safe_call(T_PROFILE, mk_args)
    capabilities = _safe_call(T_CAPABILITIES, mk_args)
    product_stats = _safe_call(T_PRODUCT_STATS, mk_args)
    subject = build_subject(raw, resolved, keyword_type)
    core = build_core_analysis(profile, capabilities, product_stats, None)
    core["source_status"]["factory_search"] = "not_requested"
    metrics = build_metrics(profile if isinstance(profile, dict) else {},
                            capabilities if isinstance(capabilities, dict) else {},
                            product_stats if isinstance(product_stats, dict) else {},
                            None)
    return apply_content_review(_assemble(subject, core, metrics, dry_run=False))


def _parse_addresses(address_args: List[str]) -> List[List[str]]:
    """Parse --address args into the nested list format expected by the MCP.

    Accepts repeated --address "省" or --address "省,市"; groups them into
    [["省"],["省","市"], ...].
    """
    out: List[List[str]] = []
    for arg in address_args or []:
        parts = [p.strip() for p in str(arg).replace("，", ",").split(",") if p.strip()]
        if parts:
            out.append(parts)
    return out


@paid_call_scope
def build_payload_search(keyword: str, keyword_type: str, addresses: List[List[str]], page_size: int, max_pages: int = 1) -> Dict[str, Any]:
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("max_pages 必须为正整数")
    mk = (keyword or "").strip()
    resolved = {"keyword": mk, "enterprise": mk, "resolved": True, "reason": "工厂检索模式：按关键词直查"}
    search_args: Dict[str, Any] = {
        "matchKeyword": mk,
        "keywordType": keyword_type,
        "pageSize": min(page_size, 10) if page_size else 10,
        "address": addresses,
    }
    search = collect_detail_pages(_safe_call, T_FACTORY_SEARCH, search_args,
                                  get_rows=_first_list, get_total=_safe_total, is_error=_is_api_error,
                                  max_pages=max_pages)
    search_total = _safe_total(search) if isinstance(search, dict) else None
    subject = {
        "enterprise": mk,
        "matchKeyword": mk,
        "keywordType": keyword_type,
        "match_raw": mk,
        "resolved": True,
        "resolve_reason": resolved.get("reason", ""),
        "mode": "search",
        "address": addresses,
    }
    core = build_core_analysis({}, {}, {}, search, mk)
    core["source_status"].update({
        "factory_profile": "not_requested",
        "factory_capabilities": "not_requested",
        "product_stats": "not_requested",
    })
    metrics = build_metrics({}, {}, {}, search_total)
    # --- Enterprise profile enrichment (from fuzzy_search) ---
    _enrich_metrics_with_profile(metrics, resolved.get("record") if isinstance(resolved, dict) else None)
    _derive_core_metrics(metrics, core if isinstance(core, dict) else {})
    report = apply_content_review(_assemble(subject, core, metrics, dry_run=False))
    return attach_pagination(report, {"工厂检索": search})


def _review_search_rows(rows: Sequence[Mapping[str, Any]], keyword: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    token = "".join(str(keyword or "").casefold().split())
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        raw_products = row.get("主营产品原文") or row.get("主营产品") or "-"
        if isinstance(raw_products, list):
            raw_products = _join_list(raw_products) or "-"
        row["主营产品原文"] = raw_products
        existing_summary = str(row.get("主营产品") or "")
        existing_meta = row.get("主营标签统计")
        if str(raw_products).strip() in ("", "-"):
            summary, meta = "", {"total": 0, "hits": 0, "others": 0}
        elif existing_summary.startswith("上游标签") and isinstance(existing_meta, dict):
            # Already organised by the current normal generator or a prior
            # review: keep its summary instead of re-tokenising it.
            summary, meta = existing_summary, existing_meta
        else:
            summary, meta = _product_tag_summary(raw_products, keyword)
        row["主营产品"] = summary or "-"
        row["主营标签统计"] = meta
        name = str(row.get("企业名称") or "")
        row["名称含关键词"] = "是" if token and token in "".join(name.casefold().split()) else "否"
        old_cap = str(row.get("注册资本") or "")
        if old_cap and old_cap != "-" and "注册资本原文" not in row:
            row["注册资本原文"] = old_cap
            row["注册资本"] = _reg_capital_text(old_cap) or "-"
        out.append(row)
    return out


def apply_content_review(report: Mapping[str, Any], *, source_sha256: Optional[str] = None,
                         reviewed_at: Optional[str] = None) -> Dict[str, Any]:
    """Rebuild factory-search narrative content offline from an existing payload.

    Uses only fields already present (search records, metrics, subject). No MCP
    call, no new facts. Fixes: raw upstream tag dumps presented as a product
    catalogue, multi-decimal capital strings, and silent name/tag keyword hits
    that made different companies look like the same subject.
    """
    out = copy.deepcopy(dict(report))
    subject = dict(out.get("subject") or {})
    ds = dict(out.get("data_source") or {})
    keyword = str(subject.get("search_keyword") or subject.get("match_raw") or subject.get("matchKeyword") or "")
    core = dict(out.get("core_analysis") or {})
    core["search_records"] = _review_search_rows(core.get("search_records") or [], keyword)
    sections = []
    for spec in core.get("sections") or []:
        if isinstance(spec, dict) and spec.get("key") == "search_records":
            spec = dict(spec)
            spec["columns"] = [("企业名称", "企业名称"), ("名称含关键词", "名称含关键词"),
                               ("主营产品（标签摘要）", "主营产品"), ("地区/地址", "地区/地址"),
                               ("注册资本", "注册资本"), ("成立日期", "成立日期")]
            note = str(spec.get("note") or "")
            if "主营产品为上游标签摘要" not in note:
                spec["note"] = note + "；主营产品为上游标签摘要，原文保留在 JSON"
        sections.append(spec)
    core["sections"] = sections
    metrics = list(out.get("metrics") or [])
    quality = _quality_report(core)
    if quality["populated_sections"] == 0:
        # No business body: keep the assembled empty/failure narrative instead
        # of replacing it with a generic abstract that implies sections exist.
        out["core_analysis"] = core
        out["metrics"] = metrics
        ds["quality_report"] = quality
        ds["content_revision"] = {
            "mode": "offline_source_preserving",
            "source_sha256": source_sha256,
            "original_generated_at": ds.get("generated_at"),
            "reviewed_at": reviewed_at or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "scope": "无有效业务章节：保留原始空结果或调用失败说明，不生成业务结论",
        }
        out["data_source"] = ds
        return out
    insights = build_insights(subject, core, metrics)
    abstract = build_abstract(subject, core, metrics)
    old_abstract = str(out.get("abstract") or "")
    marker = "明细含未完整采集的来源"
    if marker in old_abstract:
        # attach_pagination() appends this disclosure after the review; keep it
        # when an already-attached report is reviewed again offline.
        abstract += old_abstract[old_abstract.index(marker):]
    out["core_analysis"] = core
    out["metrics"] = metrics
    out["insights"] = insights
    out["abstract"] = abstract
    out["summary"] = abstract
    out["executive_summary"] = [i.get("interpretation") for i in insights][:5] or [abstract[:120]]
    out["representative_records"] = build_records(core)
    ds["quality_report"] = _quality_report(core)
    ds["content_revision"] = {
        "mode": "offline_source_preserving",
        "source_sha256": source_sha256,
        "original_generated_at": ds.get("generated_at"),
        "reviewed_at": reviewed_at or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "标签摘要化并保留原文；规范注册资本展示；标注名称/标签命中；未新增查询",
    }
    out["data_source"] = ds
    return out


def build_payload(raw: str, keyword_type: str, page_size: int, *, mode: str, addresses: List[List[str]], max_pages: int = 1) -> Dict[str, Any]:
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("max_pages 必须为正整数")
    if mode == "search":
        return build_payload_search(raw, keyword_type, addresses, page_size, max_pages)
    return build_payload_enterprise(raw, keyword_type, page_size)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a factory-insight big-data report via the factory-insight MCP.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--enterprise", help="企业全称或关键词（关键词将自动模糊补全）")
    mode_group.add_argument("--search", help="工厂检索关键词（配合 --address；按工厂名称/主营产品/产品名称检索）")
    parser.add_argument("--keyword-type", default="name", help="主体类型：name/nameId/regNumber/socialCreditCode（企业模式）；工厂检索模式可为 综合搜索/工厂名称/主营产品/产品名称")
    parser.add_argument("--address", action="append", default=[], help="工厂检索地区，可重复；格式“省”或“省,市”，例如 --address 广东省 --address 广东省,潮州市")
    parser.add_argument("--page-size", type=int, default=10, help="明细分页大小（企业模式最多 50；工厂检索模式最多 10）")
    parser.add_argument("--max-pages", type=int, default=1, help="工厂检索明细翻页预算上限，默认 1；按 total 驱动翻页，超出预算披露未纳入条数而非宣称全量")
    parser.add_argument("--dry-run", action="store_true", help="不调用真实 MCP，使用样例数据组装报告骨架")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    parser.add_argument("--report-output", help="同时输出 HTML 报告（.html）与 Markdown 报告（.md）")
    parser.add_argument("--pdf-output", help="额外输出 PDF 报告（.pdf）；需要 Playwright + Chromium")
    args = parser.parse_args()

    if args.search is not None:
        raw = args.search
        mode = "search"
        keyword_type = args.keyword_type or "综合搜索"
        addresses = _parse_addresses(args.address)
        if not addresses:
            parser.error("工厂检索模式（--search）必须至少提供一个 --address 地区")
    else:
        raw = args.enterprise
        mode = "enterprise"
        keyword_type = args.keyword_type
        addresses = []

    if args.max_pages is not None and args.max_pages < 1:
        raise SystemExit("--max-pages 必须为正整数")

    if args.dry_run:
        payload = build_dry_run_payload(raw, args.keyword_type)
    else:
        payload = build_payload(raw, keyword_type, args.page_size, mode=mode, addresses=addresses, max_pages=args.max_pages)

    payload = prepare_draft(payload)

    if args.output:
        out = pathlib.Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_dumps(payload, pretty=True), encoding="utf-8")
        print_json({"ok": True, "json": str(out), "dry_run": args.dry_run, "mode": mode})
    else:
        print_json(payload)

    if args.report_output:
        base_out = pathlib.Path(args.report_output).expanduser()
        base_out.parent.mkdir(parents=True, exist_ok=True)
        html_path = base_out.with_suffix(".html") if base_out.suffix.lower() not in (".html", ".htm") else base_out
        md_path = html_path.with_suffix(".md")
        html_path.write_text(render_html(payload), encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
        if args.pdf_output:
            pdf_path = pathlib.Path(args.pdf_output).expanduser()
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            html_to_pdf(render_html(payload), str(pdf_path))
        print_json({"ok": True, "html": str(html_path), "markdown": str(md_path), "pdf": str(pdf_path) if args.pdf_output else None, "dry_run": args.dry_run, "mode": mode})


if __name__ == "__main__":
    main()
