#!/usr/bin/env python3
"""Ruft die Preise aller Angebote in monitors.json ab und ergänzt data/prices.json.

Preisquellen pro Seite, in dieser Reihenfolge:
  0. optional "manual": fester Preis, von dir in monitors.json eingetragen
  1. optionaler CSS-Selektor ("selector") aus monitors.json
  2. schema.org-Daten (JSON-LD) mit offers.price
  3. Meta-Tags product:price:amount / og:price:amount
"""
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "monitors.json"
OUT = ROOT / "data" / "prices.json"
UA = "Mozilla/5.0 (compatible; PrivatePriceTracker/1.0)"
HEADERS = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"}
DELAY_SECONDS = 3  # Pause zwischen zwei Abrufen
_robots = {}


def allowed_by_robots(url):
    """Respektiert robots.txt. Ist sie nicht erreichbar, gilt der Abruf als erlaubt."""
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = RobotFileParser(base + "/robots.txt")
        try:
            resp = requests.get(base + "/robots.txt", headers=HEADERS, timeout=10)
            rp.parse(resp.text.splitlines() if resp.ok else [])
        except requests.RequestException:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)


def to_float(value):
    """Wandelt '1.099,00 €', '549' oder 549.0 in eine Zahl um."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d,.]", "", str(value))
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def price_from_jsonld(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        for node in walk(data):
            offers = node.get("offers")
            if not offers:
                continue
            for offer in offers if isinstance(offers, list) else [offers]:
                if isinstance(offer, dict):
                    price = to_float(offer.get("price") or offer.get("lowPrice"))
                    if price:
                        return price
    return None


def price_from_meta(soup):
    for key in ("product:price:amount", "og:price:amount"):
        tag = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
        price = to_float(tag.get("content")) if tag else None
        if price:
            return price
    return None


def fetch_price(offer):
    if "manual" in offer:  # fester Preis, den du selbst in monitors.json einträgst
        price = to_float(offer["manual"])
        if not price or price <= 0:
            raise ValueError("manueller Preis fehlt in monitors.json")
        return price
    url = offer["url"]
    if not allowed_by_robots(url):
        raise PermissionError("robots.txt verbietet den Abruf")
    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    price = None
    if offer.get("selector"):
        el = soup.select_one(offer["selector"])
        price = to_float(el.get_text(" ", strip=True)) if el else None
    price = price or price_from_jsonld(soup) or price_from_meta(soup)
    if not price:
        raise ValueError("kein Preis gefunden (Selektor in monitors.json setzen)")
    return price


def notify(monitor, shop, price):
    """Optionale Push-Nachricht über ntfy.sh, wenn der Zielpreis erreicht ist."""
    topic = os.environ.get("NTFY_TOPIC")
    target = monitor.get("target")
    if topic and target and price <= target:
        text = f"{monitor['name']}: {price:.2f} EUR bei {shop} (Ziel {target} EUR)"
        try:
            requests.post(f"https://ntfy.sh/{topic}", data=text.encode("utf-8"),
                          headers={"Title": "Zielpreis erreicht"}, timeout=10)
        except requests.RequestException:
            pass


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    db = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"history": {}}
    today = dt.date.today().isoformat()
    errors = []

    db["monitors"] = [
        {**{k: m.get(k) for k in ("id", "name", "spec", "target", "pin")},
         "links": {o["shop"]: o["url"] for o in m["offers"]}}
        for m in config
    ]

    for m in config:
        history = db["history"].setdefault(m["id"], {})
        for offer in m["offers"]:
            shop = offer["shop"]
            try:
                price = fetch_price(offer)
                rows = [r for r in history.get(shop, []) if r[0] != today]
                rows.append([today, price])
                history[shop] = rows
                print(f"OK      {m['name']} / {shop}: {price:.2f} EUR")
                notify(m, shop, price)
            except Exception as exc:  # ein kaputter Shop soll den Rest nicht stoppen
                errors.append(f"{m['name']} / {shop}: {exc}")
                print("FEHLER ", errors[-1], file=sys.stderr)
            time.sleep(DELAY_SECONDS)

    db["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    db["errors"] = errors
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
