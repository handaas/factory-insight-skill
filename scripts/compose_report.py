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
import datetime as dt
import json
import pathlib
import sys
from typing import Any, Dict, List, Mapping, Optional

from common import REPORT_BANNER, REPORT_TYPE, json_dumps, load_json_file, print_json
import mcp_client
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
        for key in ("resultList", "list", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    if value in (None, "", {}):
        return []
    return [value]


def _first_record(value: Any) -> Dict[str, Any]:
    for record in _first_list(value):
        if isinstance(record, dict):
            return record
    if isinstance(value, dict):
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
        result = mcp_client.call_tool(tool, arguments)
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


def _join_list(value: Any) -> str:
    items = _first_list(value)
    return "、".join(_text(t) for t in items if t) if items else ""


import re as _re

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


def _address_text(value: Any) -> str:
    if isinstance(value, dict):
        parts = [value.get("province"), value.get("city"), value.get("district"), value.get("value")]
        return "".join(_text(p) for p in parts if p)
    return _text(value)


def _reg_capital_text(value: Any) -> str:
    if isinstance(value, dict):
        amt = value.get("value")
        coin = value.get("coinType") or ""
        if amt is not None:
            return f"{_text(amt)} {coin}".strip()
    return _text(value)


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
            metrics.append({"label": "账期风险", "value": str(risk), "hint": "账期风险评估等级"})
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


def build_caliber(subject: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "match_target": subject.get("enterprise") or subject.get("match_raw"),
        "match_type": f"工厂概况按企业主体匹配（keywordType={subject.get('keywordType', 'name')}）；工厂检索支持工厂名称/主营产品/产品名称等关键词",
        "data_scope": "工厂概况与风险、工厂产能（产线/人员/设备/质检）、工厂产品统计、工厂检索明细",
        "products": ["工厂概况", "工厂产能", "工厂产品统计", "工厂检索"],
        "limit": "数据来自工厂公开信息与供应商数据库；少量字段可能存在更新延迟。",
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


def build_core_analysis(profile: Mapping[str, Any], capabilities: Mapping[str, Any], product_stats: Mapping[str, Any], search: Any) -> Dict[str, Any]:
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
    addr = _address_text(p.get("factoryAddress"))
    if addr:
        profile_kv["工厂地址"] = addr
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
        capabilities_kv["生产质量认证"] = ec
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
        search_rows.append({
            "企业名称": _text(item.get("name")) or "-",
            "主营产品": _join_list(item.get("mainProducts")) or "-",
            "注册资本": _reg_capital_text(item.get("regCapital")) or "-",
            "成立日期": _text(item.get("foundTime")) or "-",
        })

    sections = [
        {"key": "factory_profile", "title": "工厂概况", "kind": "kv"},
        {"key": "factory_capabilities", "title": "工厂产能", "kind": "kv", "note": "产线/人员/设备/质检等生产实力指标"},
        {"key": "product_stats", "title": "工厂产品类目分布", "kind": "donut", "note": product_rows_note,
         "chart": {"name": "产品类目", "value": "数量"},
         "columns": [("产品类目", "产品类目"), ("数量", "数量")]},
        {"key": "search_records", "title": "工厂检索明细", "kind": "table",
         "note": f"本次检索命中 {total if total is not None else '若干'} 条，展示前 {len(product_rows)} 条",
         "columns": [("企业名称", "企业名称"), ("主营产品", "主营产品"), ("注册资本", "注册资本"), ("成立日期", "成立日期")]},
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
    }


def build_records(core: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in core.get("search_records") or []:
        out.append({
            "企业名称": item.get("企业名称") or "-",
            "主营产品": item.get("主营产品") or "-",
            "注册资本": item.get("注册资本") or "-",
            "成立日期": item.get("成立日期") or "-",
        })
    return out[:20]


def build_insights(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    metric_map = {m["label"]: str(m["value"]) for m in metrics}
    profile_kv = core.get("factory_profile") or {}
    cap_kv = core.get("factory_capabilities") or {}

    if profile_kv.get("工厂规模"):
        insights.append({
            "feature": "工厂规模",
            "evidence": f"工厂规模为“{profile_kv.get('工厂规模')}”。",
            "interpretation": "工厂规模反映企业产能基础，是供应商评估与采购决策的重要参考。",
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
            "interpretation": "生产线数量是衡量工厂生产能力与交付能力的核心指标，结合品牌均摊可评估柔性制造与多客户并行交付能力。",
        })
    if brand and product:
        try:
            bn = float(brand)
            pn = float(product)
            ratio = pn / bn if bn else 0
            insights.append({
                "feature": "产品布局",
                "evidence": f"服务品牌 {brand} 个、主营产品 {product} 项，产品/品牌比 {ratio:.1f}。",
                "interpretation": "产品/品牌比反映工厂的 SKU 广度：比值高通常意味着代工多品类、定制化能力强；比值低则代表专一品类规模化生产。",
            })
        except (TypeError, ValueError):
            pass
    elif brand or product:
        ev = []
        if brand:
            ev.append(f"服务品牌 {brand} 个")
        if product:
            ev.append(f"主营产品 {product} 项")
        insights.append({
            "feature": "产品布局",
            "evidence": "、".join(ev) + "。",
            "interpretation": "服务品牌数与主营产品数反映工厂的产品结构与市场定位，结合类目分布可洞察业务集中度。",
        })
    product_rows = core.get("product_stats") or []
    if product_rows:
        conc = _concentration(product_rows, "产品类目", "数量", 2)
        if conc:
            insights.append({
                "feature": "产品类目集中度",
                "evidence": f"“{conc['top']}”类目占比约 {conc['top_share']:.0f}%，前 2 类目合计 {conc['cr']:.0f}%（CR2）。",
                "interpretation": "类目集中度反映业务聚焦：CR2 偏高意味着以少数核心品类为主、产能专业化；CR2 偏低则代表多品类分散布局、抗周期能力较强。",
            })
    qc_staff = cap_kv.get("检验人数")
    patterning = cap_kv.get("打版人数")
    if lines and qc_staff:
        try:
            ln = float(lines)
            qc = float(str(qc_staff).replace("人", ""))
            if ln > 0:
                insights.append({
                    "feature": "质检配置",
                    "evidence": f"生产线 {lines} 条对应质检 {qc_staff} 人，约 {qc / ln:.1f} 人/线。",
                    "interpretation": "质检人线比反映品质管控密度：比值越高代表品控投入越重，是高客单价/出口订单准入的关键参考。",
                })
        except (TypeError, ValueError):
            pass
    if cap_kv.get("管理体系认证") or cap_kv.get("生产质量认证"):
        ev = []
        if cap_kv.get("管理体系认证"):
            ev.append(cap_kv.get("管理体系认证"))
        if cap_kv.get("生产质量认证"):
            ev.append(cap_kv.get("生产质量认证"))
        cert_count = cap_kv.get("管理体系认证数")
        cert_clause = f"（管理体系认证 {cert_count} 项）" if cert_count else ""
        insights.append({
            "feature": "资质认证",
            "evidence": "持有认证：" + "、".join(ev) + cert_clause + "。",
            "interpretation": "体系与质量认证体现工厂的规范化管理水平，是采购方准入与风险控制的关键依据。",
        })
    # 账期风险等级（来源：factory_profile.accountPeriodRisk）
    account_risk = core.get("account_period_risk") or profile_kv.get("账期风险")
    if account_risk:
        risk_norm = account_risk.strip()
        if risk_norm == "低":
            level, advice = "采购友好", "账期风险低意味着付款条件相对宽松、回款压力小，对采购方而言合作成本与资金占用风险较低，适合长期稳定合作。"
        elif risk_norm == "中":
            level, advice = "需关注", "账期风险中等，建议结合订单规模与结算周期动态评估，合理设置预付款/里程碑付款比例以平衡双方现金流。"
        elif risk_norm == "高":
            level, advice = "风险", "账期风险高提示供应商资金链或回款存在压力，建议缩短账期、提高预付比例并加强履约监控，防范交付与质量风险。"
        else:
            level, advice = risk_norm, "账期风险等级反映付款条件与资金压力，建议结合实际结算条款评估合作风险。"
        insights.append({
            "feature": "账期风险等级",
            "evidence": f"账期风险等级为“{risk_norm}”（{level}）。",
            "interpretation": advice,
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


def build_abstract(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]]) -> str:
    name = subject.get("enterprise") or subject.get("match_raw") or "目标企业"
    parts = [f"本报告以“{name}”为分析对象，基于工厂公开信息，系统呈现企业工厂概况与风险、生产实力（产线/人员/设备/质检）以及工厂产品统计。"]
    if metrics:
        kv = "、".join(f"{m['label']} {m['value']}" for m in metrics[:5])
        parts.append(f"关键指标包括：{kv}。")
    parts.append("报告同时给出工厂规模、生产实力、产品布局与资质认证的结构化解读，便于供应商评估、采购决策与供应链风险管理参考。")
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
    return _assemble(subject, core, metrics, dry_run=True)


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _assemble(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]], *, dry_run: bool) -> Dict[str, Any]:
    abstract = build_abstract(subject, core, metrics)
    records = build_records(core)
    insights = build_insights(subject, core, metrics)
    # Quality gate: count populated core-analysis sections.
    ca = core if isinstance(core, dict) else {}
    secs = ca.get("sections", [])
    if secs:
        total_secs = len(secs)
        populated = sum(1 for s in secs if isinstance(s, dict) and ca.get(s.get("key")) not in (None, "", [], {}))
    else:
        total_secs = max(1, len([k for k in ca if k != "sections"]))
        populated = sum(1 for k in ca if k != "sections" and ca.get(k) not in (None, "", [], {}))
    quality_report = {
        "total_sections": total_secs,
        "populated_sections": populated,
        "empty_sections": total_secs - populated,
        "coverage_pct": round(populated / max(1, total_secs) * 100),
    }
    if populated == 0:
        import sys
        print("⚠️ 质量门禁警告: 所有核心分析维度均无数据", file=sys.stderr)
    title = f"{subject.get('enterprise') or '目标企业'} 工厂信息分析报告"
    return {
        "report_type": REPORT_TYPE,
        "title": title,
        "banner": REPORT_BANNER,
        "subject": dict(subject),
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": [item["interpretation"] for item in insights][:5] or [abstract[:120]],
        "metrics": list(metrics),
        "caliber": build_caliber(subject),
        "core_analysis": dict(core),
        "representative_records": records,
        "insights": insights,
        "data_source": {
            "mcp_server": "factory-insight-mcp-server",
            "products": [
                {"name": "工厂概况", "product_id": "66aa4eac4bb1f40b86c46f0b"},
                {"name": "工厂产能", "product_id": "66aa4eac4bb1f40b86c46ee6"},
                {"name": "工厂产品统计", "product_id": "6725e5b9ba65854594baebd2"},
                {"name": "工厂检索", "product_id": "66aa4eac4bb1f40b86c46efe"},
            ],
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "quality_report": quality_report,
        },
    }


def build_payload_enterprise(raw: str, keyword_type: str, page_size: int) -> Dict[str, Any]:
    resolved = resolve_enterprise_name(raw)
    enterprise = resolved["enterprise"]
    mk_args: Dict[str, Any] = {"matchKeyword": enterprise, "keywordType": keyword_type}
    profile = _safe_call(T_PROFILE, mk_args)
    capabilities = _safe_call(T_CAPABILITIES, mk_args)
    product_stats = _safe_call(T_PRODUCT_STATS, mk_args)
    subject = build_subject(raw, resolved, keyword_type)
    core = build_core_analysis(profile, capabilities, product_stats, None)
    metrics = build_metrics(profile if isinstance(profile, dict) else {},
                            capabilities if isinstance(capabilities, dict) else {},
                            product_stats if isinstance(product_stats, dict) else {},
                            None)
    return _assemble(subject, core, metrics, dry_run=False)


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


def build_payload_search(keyword: str, keyword_type: str, addresses: List[List[str]], page_size: int) -> Dict[str, Any]:
    mk = (keyword or "").strip()
    resolved = {"keyword": mk, "enterprise": mk, "resolved": True, "reason": "工厂检索模式：按关键词直查"}
    search_args: Dict[str, Any] = {
        "matchKeyword": mk,
        "keywordType": keyword_type,
        "pageIndex": 1,
        "pageSize": min(page_size, 10) if page_size else 10,
        "address": addresses,
    }
    search = _safe_call(T_FACTORY_SEARCH, search_args)
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
    core = build_core_analysis({}, {}, {}, search)
    metrics = build_metrics({}, {}, {}, search_total)
    # --- Enterprise profile enrichment (from fuzzy_search) ---
    _enrich_metrics_with_profile(metrics, resolved.get("record") if isinstance(resolved, dict) else None)
    _derive_core_metrics(metrics, core if isinstance(core, dict) else {})
    return _assemble(subject, core, metrics, dry_run=False)


def build_payload(raw: str, keyword_type: str, page_size: int, *, mode: str, addresses: List[List[str]]) -> Dict[str, Any]:
    if mode == "search":
        return build_payload_search(raw, keyword_type, addresses, page_size)
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

    if args.dry_run:
        payload = build_dry_run_payload(raw, args.keyword_type)
    else:
        payload = build_payload(raw, keyword_type, args.page_size, mode=mode, addresses=addresses)

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
