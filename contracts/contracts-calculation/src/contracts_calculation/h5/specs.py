"""H5：apply 型 QA 47 問の計算仕様（1 問 1 ルール。人が書き、機械が検査する）。

- 引用（source.quote）は親の content の単位テキストから逐語で取る（G2 で照合）。
- 定数は const_keys で親の meta.constants と突合する（G4）。
- 表記の往復ができない導出値（表の時刻から計算した時間数など）は derived_params に挙げ、
  レポートに導出注記を付ける。
- 読み方に幅がある前提は flags に挙げる（kind="reading"）。これが「読み幅あり」として人間に残る。
- meta_date_inputs は、値が親の meta.contract_date と一致しなければならない入力
  （契約日は記名押印欄に描かれるが、plain_text の単位としては存在しないため、引用ではなく meta で突合する）。
"""

from __future__ import annotations

ENTRIES: list[dict] = []


def _src(unit: str, quote: str) -> dict:
    return {"unit": unit, "quote": quote}


def lit(v):
    return {"lit": v}


def var(n):
    return {"var": n}


def param(n):
    return {"param": n}


def step(n):
    return {"step": n}


def op(name, *args, **attrs):
    d = {"op": name, "args": list(args)}
    d.update(attrs)
    return d


def P_int(value, unit, surface, uid, quote):
    return {"type": "int", "unit": unit, "value": value, "surface": surface, "source": _src(uid, quote)}


def P_ratio(num, den, surface, uid, quote):
    return {"type": "ratio", "num": num, "den": den, "surface": surface, "source": _src(uid, quote)}


def P_date(value, surface, uid, quote):
    return {"type": "date", "value": value, "surface": surface, "source": _src(uid, quote)}


def IN(type_, unit=None, origin="fact", desc="", **kw):
    d = {"type": type_, "origin": origin, "desc": desc}
    if unit:
        d["unit"] = unit
    d.update(kw)
    return d


def Q(
    cid,
    qid,
    *,
    answer_kind,
    params=None,
    inputs=None,
    steps,
    output,
    given=None,
    const_keys=None,
    derived_params=(),
    flags=(),
    notes=(),
    meta_date_inputs=(),
    parties=None,
    obligations=(),
    title="",
):
    rule = {
        "id": f"{qid}",
        "title": title or f"{cid} {qid}",
        "kind": "calculation",
        "origin": "bound",
        "interface": {"function": f"{qid}_{cid.replace('-', '_')}"},
        "inputs": inputs or {},
        "steps": steps,
        "output": output,
        "obligations": list(obligations),
    }
    if parties:
        rule["parties"] = parties
    ENTRIES.append(
        {
            "cid": cid,
            "qid": qid,
            "answer_kind": answer_kind,
            "given": given or {},
            "const_keys": const_keys or {},
            "derived_params": list(derived_params),
            "flags": [{"kind": "reading", "text": f} for f in flags]
            + [{"kind": "note", "text": n} for n in notes],
            "meta_date_inputs": list(meta_date_inputs),
            "spec": {
                "spec_version": "0.1",
                "document": {"content_id": cid, "doctype": cid.split("-")[0], "calc_seed": 0},
                "params": params or {},
                "tables": {},
                "rules": [rule],
            },
        }
    )


PAYER_KO = {"payer": "甲", "payee": "乙"}
PAYER_OTSU = {"payer": "乙", "payee": "甲"}

# ==== con-0001 =================================================================

Q(
    "con-0001",
    "qa_auth_009",
    answer_kind="percent",
    title="不可抗力の損害の受注者負担（請負代金額比）",
    params={"force_share": P_ratio(1, 10, "１割", "a9_p3", "請負代金の１割に相当する額までは乙が負担し")},
    inputs={"loss_percent": IN("int", "PERCENT", desc="損害の額（請負代金額に対する百分率）")},
    given={"loss_percent": 20},
    const_keys={"force_share": "force_share"},
    steps=[
        {
            "name": "cap_percent",
            "label": "受注者負担の上限（百分率）",
            "expr": op("muldiv", lit(100), param("force_share"), lit(1), rounding="floor"),
        },
        {
            "name": "borne",
            "label": "受注者が負担する割合",
            "expr": op("min", var("loss_percent"), step("cap_percent")),
        },
    ],
    output={"step": "borne", "type": "int", "unit": "PERCENT"},
    obligations=["rounding:exact", "share:contractor_up_to_cap"],
)

Q(
    "con-0001",
    "qa_auth_010",
    answer_kind="percent",
    title="前払金と部分払の合計（請負代金額比）",
    params={
        "advance_rate": P_ratio(3, 10, "３割", "a10_p1", "請負代金の３割に相当する額を前払金として支払う"),
        "partial_each": P_ratio(2, 10, "２割", "tbl_part__r1c2", "２割"),
        "partial_times": P_int(3, "COUNT", "３回", "a10_p2", "３回を限度として部分払を請求することができる"),
    },
    const_keys={"advance_rate": "advance_rate"},
    steps=[
        {
            "name": "advance_pct",
            "label": "前払金の割合",
            "expr": op("muldiv", lit(100), param("advance_rate"), lit(1), rounding="floor"),
        },
        {
            "name": "each_pct",
            "label": "部分払1回の割合",
            "expr": op("muldiv", lit(100), param("partial_each"), lit(1), rounding="floor"),
        },
        {
            "name": "total",
            "label": "支払済みの割合",
            "expr": op("add", step("advance_pct"), op("mul", step("each_pct"), param("partial_times"))),
        },
    ],
    output={"step": "total", "type": "int", "unit": "PERCENT"},
    obligations=["rounding:exact"],
    flags=["第十六条第4項「9割を超えることはできない」の読み（9割ちょうどは可、の読みでよいか）"],
)

# ==== con-0002 =================================================================

Q(
    "con-0002",
    "qa_auth_008",
    answer_kind="amount",
    title="前払金の額",
    params={
        "contract_price": P_int(273_500_000, "JPY", "2億7350万円", "pre_p1", "請負代金額を2億7350万円"),
        "advance_rate": P_ratio(2, 10, "2割", "a10_p1", "請負代金額の2割に相当する額を前払金として支払う"),
    },
    const_keys={"contract_price": "contract_price", "advance_rate": "advance_rate"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "advance",
            "label": "前払金の額",
            "expr": op("muldiv", param("contract_price"), param("advance_rate"), lit(1), rounding="floor"),
        }
    ],
    output={"step": "advance", "type": "int", "unit": "JPY"},
    obligations=["rounding:exact"],
)

Q(
    "con-0002",
    "qa_auth_009",
    answer_kind="percent",
    title="第4回の部分払後に未払として残る割合",
    params={
        "advance_rate": P_ratio(2, 10, "2割", "a10_p1", "請負代金額の2割に相当する額を前払金として支払う"),
        "partial1": P_int(20, "PERCENT", "20パーセント", "tbl_partial__r1c3", "20パーセント"),
        "partial2": P_int(20, "PERCENT", "20パーセント", "tbl_partial__r2c3", "20パーセント"),
        "partial3": P_int(15, "PERCENT", "15パーセント", "tbl_partial__r3c3", "15パーセント"),
        "partial4": P_int(15, "PERCENT", "15パーセント", "tbl_partial__r4c3", "15パーセント"),
    },
    const_keys={"advance_rate": "advance_rate"},
    steps=[
        {
            "name": "advance_pct",
            "label": "前払金の割合",
            "expr": op("muldiv", lit(100), param("advance_rate"), lit(1), rounding="floor"),
        },
        {
            "name": "paid",
            "label": "支払済みの割合",
            "expr": op(
                "add",
                step("advance_pct"),
                param("partial1"),
                param("partial2"),
                param("partial3"),
                param("partial4"),
            ),
        },
        {"name": "remaining", "label": "未払として残る割合", "expr": op("sub", lit(100), step("paid"))},
    ],
    output={"step": "remaining", "type": "int", "unit": "PERCENT"},
    obligations=["rounding:exact"],
    notes=[
        "別紙2 の累計の割合（90パーセント）とも一致することを確認済み（前払金は部分払の割合に含まれない読み）"
    ],
)

Q(
    "con-0002",
    "qa_auth_010",
    answer_kind="date",
    title="完成検査の期限",
    params={"inspect_days": P_int(20, "DAY", "20日", "a11_p2", "通知を受けた日から20日以内に完成検査を行い")},
    inputs={"notify_date": IN("date", desc="完成の通知を受けた日")},
    given={"notify_date": "2032-05-20"},
    const_keys={"inspect_days": "inspect_days"},
    steps=[
        {
            "name": "deadline",
            "label": "完成検査の期限",
            "expr": op("add_days", var("notify_date"), param("inspect_days")),
        }
    ],
    output={"step": "deadline", "type": "date"},
    obligations=["day_count:initial_day_excluded"],
    notes=["「受けた日から20日以内」の満了を通知日＋20日とした（初日不算入の慣行）"],
)

# ==== csl-0001 =================================================================

Q(
    "csl-0001",
    "qa_auth_009",
    answer_kind="date",
    title="更新しない旨の申出の到達期限",
    params={
        "term_years": P_int(1, "YEAR", "１年", "a8_p1", "契約を締結した日から１年とする"),
        "renewal_notice": P_int(3, "MONTH", "３か月", "a8_p2", "期間が満了する３か月前までに"),
    },
    inputs={"contract_date": IN("date", desc="契約締結日")},
    given={"contract_date": "2026-12-14"},
    meta_date_inputs=["contract_date"],
    const_keys={"term_years": "term_years", "renewal_notice": "renewal_notice"},
    steps=[
        {
            "name": "expiry",
            "label": "期間の満了日",
            "expr": op("add_months", var("contract_date"), op("mul", param("term_years"), lit(12))),
        },
        {
            "name": "notify_by",
            "label": "申出の到達期限",
            "expr": op("add_months", step("expiry"), op("sub", lit(0), param("renewal_notice"))),
        },
    ],
    output={"step": "notify_by", "type": "date"},
    obligations=["period_count:anniversary", "notice:arrival_basis"],
    flags=[
        "「締結した日から１年」の満了日を応当日（12/14）と読んだ（前日 12/13 と読む流儀もある）",
        "「満了する３か月前まで」の期限を 9/14 当日を含む読みにした（9/13 と読む流儀もある）",
    ],
)

Q(
    "csl-0001",
    "qa_auth_010",
    answer_kind="amount",
    title="16時間の月の報酬合計",
    params={
        "monthly_fee": P_int(250_000, "JPY", "２５万円", "tbl_fee__r1c1", "２５万円"),
        "included_hours": P_int(
            10, "HOUR", "１０時間", "tbl_fee__r1c2", "１か月あたり１０時間までの助言を含む定額"
        ),
        "hourly_fee": P_int(18_000, "JPY/HOUR", "１万８０００円", "tbl_fee__r2c1", "１万８０００円"),
    },
    inputs={"hours": IN("int", "HOUR", desc="当月に助言に要した時間")},
    given={"hours": 16},
    const_keys={"monthly_fee": "monthly_fee", "included_hours": "included_hours", "hourly_fee": "hourly_fee"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "over_hours",
            "label": "超過時間",
            "expr": op("max", lit(0), op("sub", var("hours"), param("included_hours"))),
        },
        {
            "name": "total",
            "label": "報酬の合計",
            "expr": op("add", param("monthly_fee"), op("mul", step("over_hours"), param("hourly_fee"))),
        },
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["included:monthly_fee_covers_included_hours"],
)

# ==== csl-0002 =================================================================

Q(
    "csl-0002",
    "qa_auth_008",
    answer_kind="amount",
    title="21時間の月の報酬",
    params={
        "monthly_fee": P_int(380_000, "JPY", "38万円", "tbl_fee__r1c1", "38万円"),
        "included_hours": P_int(16, "HOUR", "16時間", "tbl_fee__r1c2", "16時間"),
        "hourly_fee": P_int(24_000, "JPY/HOUR", "2万4000円", "tbl_fee__r2c1", "2万4000円"),
    },
    inputs={"hours": IN("int", "HOUR", desc="定例協議と照会への回答に要した時間")},
    given={"hours": 21},
    const_keys={"monthly_fee": "monthly_fee", "included_hours": "included_hours", "hourly_fee": "hourly_fee"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "over_hours",
            "label": "超過時間",
            "expr": op("max", lit(0), op("sub", var("hours"), param("included_hours"))),
        },
        {
            "name": "total",
            "label": "報酬の額",
            "expr": op("add", param("monthly_fee"), op("mul", step("over_hours"), param("hourly_fee"))),
        },
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["included:monthly_fee_covers_included_hours"],
    notes=[
        "移動の時間を算入しない前提は本文に根拠がある（第5条「移動に要した時間は、前項の時間に算入しない」）"
    ],
)

Q(
    "csl-0002",
    "qa_auth_009",
    answer_kind="date",
    title="更新しない旨の申出の期限",
    params={
        "renewal_notice": P_int(
            2, "MONTH", "2か月", "a9_p2", "期間の満了の2か月前までに更新しない旨を書面により申し出ない"
        )
    },
    inputs={"expiry": IN("date", desc="期間の満了日")},
    given={"expiry": "2031-10-01"},
    const_keys={"renewal_notice": "renewal_notice"},
    steps=[
        {
            "name": "notify_by",
            "label": "申出の期限",
            "expr": op("add_months", var("expiry"), op("sub", lit(0), param("renewal_notice"))),
        }
    ],
    output={"step": "notify_by", "type": "date"},
    obligations=["period_count:anniversary"],
    notes=["「2か月前まで」は応当日（8/1）当日を含む読み（csl-0001 と同じ数え方）"],
)

Q(
    "csl-0002",
    "qa_auth_010",
    answer_kind="amount",
    title="在籍10日（31日の月）の月額報酬の日割",
    params={"monthly_fee": P_int(380_000, "JPY", "38万円", "tbl_fee__r1c1", "38万円")},
    inputs={
        "days_in_office": IN("int", "DAY", desc="在籍した日数"),
        "month_days": IN("int", "DAY", desc="その月の日数", min=28, max=31),
    },
    given={"days_in_office": 10, "month_days": 31},
    const_keys={"monthly_fee": "monthly_fee"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "fee",
            "label": "日割後の月額報酬",
            "expr": op(
                "muldiv", param("monthly_fee"), var("days_in_office"), var("month_days"), rounding="ceil"
            ),
        }
    ],
    output={"step": "fee", "type": "int", "unit": "JPY"},
    obligations=["rounding:ceil_1yen", "proration_basis:days_in_month"],
    notes=["切り上げは本文に根拠がある（a5_p5「円未満の端数は切り上げる」）"],
)

# ==== dlg-0001 =================================================================

Q(
    "dlg-0001",
    "qa_auth_009",
    answer_kind="date",
    title="定期報告の期限",
    params={"report_due_days": P_int(3, "DAY", "３日", "a5_p2", "締めの日から３日以内に書面により行う")},
    inputs={"close_date": IN("date", desc="定期報告の締めの日")},
    given={"close_date": "2027-01-31"},
    const_keys={"report_due_days": "report_due_days"},
    steps=[
        {
            "name": "deadline",
            "label": "報告の期限",
            "expr": op("add_days", var("close_date"), param("report_due_days")),
        }
    ],
    output={"step": "deadline", "type": "date"},
    obligations=["day_count:initial_day_excluded"],
    flags=["「締めの日から３日以内」の起算を締めの日の翌日とする読み（当日起算なら 2/2 になる）"],
)

Q(
    "dlg-0001",
    "qa_auth_010",
    answer_kind="amount",
    title="140時間の月の報酬",
    params={
        "monthly_fee": P_int(960_000, "JPY", "９６万円", "a6_p1", "９６万円"),
        "monthly_hours": P_int(120, "HOUR", "１２０時間", "a3_p2", "１２０時間"),
        "over_rate": P_int(7_000, "JPY/HOUR", "７０００円", "a6_p2", "７０００円"),
    },
    inputs={"hours": IN("int", "HOUR", desc="当月の作業時間")},
    given={"hours": 140},
    const_keys={"monthly_fee": "monthly_fee", "monthly_hours": "monthly_hours", "over_rate": "over_rate"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "over_hours",
            "label": "超過時間",
            "expr": op("max", lit(0), op("sub", var("hours"), param("monthly_hours"))),
        },
        {
            "name": "total",
            "label": "報酬の額",
            "expr": op("add", param("monthly_fee"), op("mul", step("over_hours"), param("over_rate"))),
        },
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["over_hours:prior_consent_assumed_by_question"],
)

# ==== dlg-0002 =================================================================

Q(
    "dlg-0002",
    "qa_auth_008",
    answer_kind="date",
    title="月次報告の期限",
    params={"report_due_days": P_int(5, "DAY", "５日", "a5_p1", "締めの日から５日以内に書面により行う")},
    inputs={"close_date": IN("date", desc="月次報告の締めの日")},
    given={"close_date": "2029-04-30"},
    const_keys={"report_due_days": "report_due_days"},
    steps=[
        {
            "name": "deadline",
            "label": "報告の期限",
            "expr": op("add_days", var("close_date"), param("report_due_days")),
        }
    ],
    output={"step": "deadline", "type": "date"},
    obligations=["day_count:initial_day_excluded"],
    notes=["起算の数え方は dlg-0001 qa_auth_009 と同じ（締めの日の翌日から）"],
)

Q(
    "dlg-0002",
    "qa_auth_009",
    answer_kind="amount",
    title="134時間の月の報酬",
    params={
        "monthly_fee": P_int(420_000, "JPY", "４２万円", "a6_p1", "４２万円"),
        "monthly_hours": P_int(120, "HOUR", "１２０時間", "a2_p2", "１２０時間"),
        "over_rate": P_int(2_800, "JPY/HOUR", "２８００円", "a6_p2", "２８００円"),
    },
    inputs={"hours": IN("int", "HOUR", desc="当月に本件事務に充てた時間")},
    given={"hours": 134},
    const_keys={"monthly_fee": "monthly_fee", "monthly_hours": "monthly_hours", "over_rate": "over_rate"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "over_hours",
            "label": "超過時間",
            "expr": op("max", lit(0), op("sub", var("hours"), param("monthly_hours"))),
        },
        {
            "name": "total",
            "label": "報酬の額",
            "expr": op("add", param("monthly_fee"), op("mul", step("over_hours"), param("over_rate"))),
        },
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["over_hours:prior_consent_assumed_by_question"],
)

Q(
    "dlg-0002",
    "qa_auth_010",
    answer_kind="amount",
    title="開室12日（開室すべき20日）の月の報酬",
    params={"monthly_fee": P_int(420_000, "JPY", "４２万円", "a6_p1", "４２万円")},
    inputs={
        "opened_days": IN("int", "DAY", desc="開室した日数"),
        "scheduled_days": IN("int", "DAY", desc="開室すべき日数", min=1, max=31),
    },
    given={"opened_days": 12, "scheduled_days": 20},
    const_keys={"monthly_fee": "monthly_fee"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "fee",
            "label": "日割後の報酬",
            "expr": op(
                "muldiv", param("monthly_fee"), var("opened_days"), var("scheduled_days"), rounding="floor"
            ),
        }
    ],
    output={"step": "fee", "type": "int", "unit": "JPY"},
    obligations=["rounding:floor_1yen", "proration_basis:scheduled_open_days"],
    notes=["切り捨ては本文に根拠がある（a6_p5「円未満の端数は切り捨てる」）"],
)

# ==== emp-0001 =================================================================

Q(
    "emp-0001",
    "qa_auth_009",
    answer_kind="multiplier_percent",
    title="所定外労働の賃金倍率",
    params={"overtime_rate": P_ratio(27, 100, "２７パーセント", "tbl_wage__r7c1", "２７パーセント")},
    const_keys={"overtime_rate": "overtime_rate"},
    steps=[
        {
            "name": "premium_pct",
            "label": "割増分（百分率）",
            "expr": op("muldiv", lit(100), param("overtime_rate"), lit(1), rounding="floor"),
        },
        {
            "name": "multiplier",
            "label": "基本に対する倍率（百分率）",
            "expr": op("add", lit(100), step("premium_pct")),
        },
    ],
    output={"step": "multiplier", "type": "int", "unit": "PERCENT"},
    obligations=["rounding:exact"],
    flags=["「割増率」を基本に上乗せする率と読んだ（割増賃金の率そのものが 1.27 と読む流儀もある）"],
)

Q(
    "emp-0001",
    "qa_auth_010",
    answer_kind="date",
    title="年次有給休暇が与えられる日",
    params={
        "start_date": P_date("2027-02-01", "２０２７年２月１日", "tbl_term__r2c1", "２０２７年２月１日"),
        "vest_months": P_int(6, "MONTH", "６か月", "c4_a2_p1", "雇入れの日から６か月を継続して勤務し"),
    },
    const_keys={"start_date": "start_date"},
    steps=[
        {
            "name": "vest_date",
            "label": "年休の付与日",
            "expr": op("add_months", param("start_date"), param("vest_months")),
        }
    ],
    output={"step": "vest_date", "type": "date"},
    obligations=["period_count:anniversary"],
    flags=["「６か月を継続して勤務し」た時点を 8/1（応当日）と読んだ（7/31 の経過後と読む流儀もある）"],
)

# ==== emp-0002 =================================================================

Q(
    "emp-0002",
    "qa_auth_008",
    answer_kind="amount",
    title="早番10回の月の基本賃金",
    params={
        "shift_hours": P_int(
            6, "HOUR", "午前7時00分〜午後1時00分（6時間）", "tbl_hours__r1c1", "午前7時00分"
        ),
        "hourly_wage": P_int(1_180, "JPY/HOUR", "1180円", "tbl_wage__r2c1", "1180円"),
    },
    inputs={"shifts": IN("int", "COUNT", desc="早番の勤務回数")},
    given={"shifts": 10},
    const_keys={"hourly_wage": "hourly_wage"},
    derived_params=["shift_hours"],
    parties={"payer": "事業主", "payee": "労働者"},
    steps=[
        {
            "name": "wage",
            "label": "基本賃金の額",
            "expr": op("mul", param("shift_hours"), var("shifts"), param("hourly_wage")),
        }
    ],
    output={"step": "wage", "type": "int", "unit": "JPY"},
    obligations=["shift_duration:derived_from_schedule_table"],
    notes=["早番 6 時間は表3の始終業時刻（7:00〜13:00・休憩なし）から導出した（時刻の差引は演算語彙の外）"],
)

Q(
    "emp-0002",
    "qa_auth_009",
    answer_kind="amount",
    title="夜勤1回の基本賃金と手当の合計（割増を除く）",
    params={
        "worked_hours": P_int(
            15,
            "HOUR",
            "午後4時30分〜翌日の午前9時30分・休憩120分（実働15時間）",
            "tbl_hours__r4c1",
            "午後4時30分",
        ),
        "hourly_wage": P_int(1_180, "JPY/HOUR", "1180円", "tbl_wage__r2c1", "1180円"),
        "night_allow": P_int(2_600, "JPY", "1回あたり2600円", "tbl_wage__r4c1", "1回あたり2600円"),
    },
    const_keys={"hourly_wage": "hourly_wage", "night_allow": "night_allow"},
    derived_params=["worked_hours"],
    parties={"payer": "事業主", "payee": "労働者"},
    steps=[
        {
            "name": "total",
            "label": "基本賃金と手当の合計",
            "expr": op("add", op("mul", param("worked_hours"), param("hourly_wage")), param("night_allow")),
        }
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["shift_duration:derived_from_schedule_table"],
    flags=["深夜の割増（33パーセント）を設問の文で明示的に除く、という除き方が妥当か"],
    notes=["実働 15 時間は表3の時刻（16:30〜翌9:30＝17時間、休憩120分）から導出した"],
)

Q(
    "emp-0002",
    "qa_auth_010",
    answer_kind="date",
    title="賃金の支払日",
    params={"pay_day": P_int(5, "DAY", "翌月5日", "tbl_wage__r11c1", "翌月5日")},
    inputs={"close_date": IN("date", desc="賃金の締切の日")},
    given={"close_date": "2030-08-15"},
    const_keys={"pay_day": "pay_day"},
    steps=[
        {
            "name": "payday",
            "label": "支払の日",
            "expr": op("set_day", op("add_months", var("close_date"), lit(1)), param("pay_day")),
        }
    ],
    output={"step": "payday", "type": "date"},
    obligations=["payday:day_of_next_month"],
    notes=["締切は表4「毎月15日」。設問の期間（7/16〜8/15）の締めは 8/15 で、これと整合する"],
)

# ==== lea-0001 =================================================================

Q(
    "lea-0001",
    "qa_auth_009",
    answer_kind="date",
    title="借主の解約申入れの期限",
    params={
        "end_date": P_date("2030-03-31", "２０３０年３月３１日", "tbl_term__r2c1", "２０３０年３月３１日"),
        "notice_months": P_int(6, "MONTH", "６か月", "a2_p4", "６か月"),
    },
    const_keys={"end_date": "end_date", "notice_months": "notice_months"},
    steps=[
        {
            "name": "notify_by",
            "label": "申入れの期限",
            "expr": op("add_months", param("end_date"), op("sub", lit(0), param("notice_months"))),
        }
    ],
    output={"step": "notify_by", "type": "date"},
    obligations=["period_count:anniversary"],
    flags=["「６か月前まで」を応当日（9/30）当日を含む読みにした（10/1 と読む流儀もある）"],
)

Q(
    "lea-0001",
    "qa_auth_010",
    answer_kind="amount",
    title="賃料と共益費の1か月分の合計",
    params={
        "rent": P_int(285_000, "JPY", "２８万５０００円", "tbl_rent__r1c1", "２８万５０００円"),
        "common_fee": P_int(32_000, "JPY", "３万２０００円", "tbl_rent__r2c1", "３万２０００円"),
    },
    parties=PAYER_OTSU,
    steps=[
        {"name": "total", "label": "1か月分の合計", "expr": op("add", param("rent"), param("common_fee"))}
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["source:head_matter_rows"],
)

# ==== lea-0002 =================================================================

Q(
    "lea-0002",
    "qa_auth_007",
    answer_kind="amount",
    title="月の途中（6/10）で終わった月の賃料等",
    params={
        "rent": P_int(194_000, "JPY", "19万4000円", "tbl_rent__r1c1", "19万4000円"),
        "common_fee": P_int(21_000, "JPY", "2万1000円", "tbl_rent__r2c1", "2万1000円"),
    },
    inputs={
        "usage_days": IN("int", "DAY", desc="その月に契約が存続した日数"),
        "month_days": IN("int", "DAY", desc="その月の日数", min=28, max=31),
    },
    given={"usage_days": 10, "month_days": 30},
    const_keys={"rent": "rent", "common_fee": "common_fee"},
    parties=PAYER_OTSU,
    steps=[
        {"name": "monthly", "label": "賃料等の月額", "expr": op("add", param("rent"), param("common_fee"))},
        {
            "name": "fee",
            "label": "日割後の賃料等",
            "expr": op("muldiv", step("monthly"), var("usage_days"), var("month_days"), rounding="floor"),
        },
    ],
    output={"step": "fee", "type": "int", "unit": "JPY"},
    obligations=["rounding:floor_1yen", "proration_basis:days_in_month"],
    notes=["切り捨ては本文に根拠がある（a3_p2「円未満の端数は切り捨てる」）。6/10 終了＝10日分・6月は30日"],
)

Q(
    "lea-0002",
    "qa_auth_008",
    answer_kind="amount",
    title="返還する保証金の額",
    params={
        "deposit": P_int(776_000, "JPY", "77万6000円", "tbl_rent__r3c1", "77万6000円"),
        "rent": P_int(194_000, "JPY", "19万4000円", "tbl_rent__r1c1", "19万4000円"),
        "common_fee": P_int(21_000, "JPY", "2万1000円", "tbl_rent__r2c1", "2万1000円"),
    },
    inputs={"restoration_cost": IN("int", "JPY", desc="原状回復に要した費用")},
    given={"restoration_cost": 180_000},
    const_keys={"deposit": "deposit", "rent": "rent", "common_fee": "common_fee"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "unpaid",
            "label": "未払の賃料等（1か月分）",
            "expr": op("add", param("rent"), param("common_fee")),
        },
        {
            "name": "refund",
            "label": "返還する保証金の額",
            "expr": op("sub", param("deposit"), op("add", step("unpaid"), var("restoration_cost"))),
        },
    ],
    output={"step": "refund", "type": "int", "unit": "JPY"},
    obligations=["deduction:unpaid_and_restoration"],
    notes=[
        "未払の賃料等1か月分は賃料＋共益費の合計と読んだ（a4_p4「未払の賃料等および原状回復に要した費用を差し引いた額」）"
    ],
)

Q(
    "lea-0002",
    "qa_auth_009",
    answer_kind="date",
    title="原状回復の内容を示す期限",
    params={"restore_days": P_int(14, "DAY", "14日", "a8_p3", "明渡しの14日前までに")},
    inputs={"handover_date": IN("date", desc="明渡しの日")},
    given={"handover_date": "2032-10-31"},
    const_keys={"restore_days": "restore_days"},
    steps=[
        {
            "name": "deadline",
            "label": "示す期限",
            "expr": op("add_days", var("handover_date"), op("sub", lit(0), param("restore_days"))),
        }
    ],
    output={"step": "deadline", "type": "date"},
    obligations=["day_count:days_before_event"],
    notes=["「14日前まで」＝明渡しの日の14日前（10/17）当日を含む読み"],
)

# ==== lic-0001 =================================================================

_LIC1_TIER_PARAMS = {
    "rate1": P_ratio(4, 100, "４パーセント", "tbl_rate__r1c2", "４パーセント"),
    "rate2": P_ratio(3, 100, "３パーセント", "tbl_rate__r2c2", "３パーセント"),
    "rate3": P_ratio(2, 100, "２パーセント", "tbl_rate__r3c2", "２パーセント"),
    "band1": P_int(50_000_000, "JPY", "５０００万円", "tbl_rate__r1c1", "５０００万円まで"),
    "band2": P_int(100_000_000, "JPY", "１億円", "tbl_rate__r2c1", "５０００万円を超え１億円まで"),
}
_LIC1_TIER_STEPS = [
    {"name": "t1_base", "label": "第一区分の対象額", "expr": op("min", var("sales"), param("band1"))},
    {
        "name": "t1",
        "label": "第一区分の実施料",
        "expr": op("muldiv", step("t1_base"), param("rate1"), lit(1), rounding="floor"),
    },
    {
        "name": "t2_base",
        "label": "第二区分の対象額",
        "expr": op(
            "min",
            op("max", lit(0), op("sub", var("sales"), param("band1"))),
            op("sub", param("band2"), param("band1")),
        ),
    },
    {
        "name": "t2",
        "label": "第二区分の実施料",
        "expr": op("muldiv", step("t2_base"), param("rate2"), lit(1), rounding="floor"),
    },
    {
        "name": "t3_base",
        "label": "第三区分の対象額",
        "expr": op("max", lit(0), op("sub", var("sales"), param("band2"))),
    },
    {
        "name": "t3",
        "label": "第三区分の実施料",
        "expr": op("muldiv", step("t3_base"), param("rate3"), lit(1), rounding="floor"),
    },
    {"name": "running", "label": "ランニング実施料", "expr": op("add", step("t1"), step("t2"), step("t3"))},
]

Q(
    "lic-0001",
    "qa_auth_009",
    answer_kind="amount",
    title="正味販売価格1億2000万円のランニング実施料",
    params=dict(_LIC1_TIER_PARAMS),
    inputs={"sales": IN("int", "JPY", desc="報告期間の正味販売価格の合計", min=0, max=200_000_000)},
    given={"sales": 120_000_000},
    parties=PAYER_OTSU,
    steps=list(_LIC1_TIER_STEPS),
    output={"step": "running", "type": "int", "unit": "JPY"},
    obligations=["rounding:exact", "tier_basis:per_band_sum"],
    notes=["区分ごとに分けて計算する方式は本文に根拠がある（a3_p4「区分ごとに分けて計算した額の合計」）"],
)

Q(
    "lic-0001",
    "qa_auth_010",
    answer_kind="amount",
    title="正味販売価格2000万円のときに支払うべき実施料",
    params={
        **_LIC1_TIER_PARAMS,
        "minimum_royalty": P_int(1_200_000, "JPY", "１２０万円", "a3_p5", "１２０万円に満たないときは"),
    },
    inputs={"sales": IN("int", "JPY", desc="報告期間の正味販売価格の合計", min=0, max=200_000_000)},
    given={"sales": 20_000_000},
    const_keys={"minimum_royalty": "minimum_royalty"},
    parties=PAYER_OTSU,
    steps=list(_LIC1_TIER_STEPS)
    + [
        {
            "name": "payable",
            "label": "支払うべき実施料",
            "expr": op("max", step("running"), param("minimum_royalty")),
        },
    ],
    output={"step": "payable", "type": "int", "unit": "JPY"},
    obligations=["rounding:exact", "minimum:difference_topped_up"],
    notes=["「差額を最低実施料として支払う」＝合計で最低実施料額になる読み（設問の答えもこの読み）"],
)

# ==== lic-0002 =================================================================

_LIC2_PARAMS = {
    "rate": P_ratio(25, 1000, "2.5パーセント", "a4_p2", "2.5パーセント"),
    "min_royalty": P_int(300_000, "JPY", "30万円", "a4_p3", "30万円"),
}

Q(
    "lic-0002",
    "qa_auth_009",
    answer_kind="amount",
    title="純売上高800万円のときの使用料",
    params=dict(_LIC2_PARAMS),
    inputs={"sales": IN("int", "JPY", desc="報告期間の純売上高", min=0, max=1_000_000_000)},
    given={"sales": 8_000_000},
    const_keys={"rate": "rate", "min_royalty": "min_royalty"},
    parties=PAYER_OTSU,
    steps=[
        {
            "name": "base",
            "label": "料率による使用料",
            "expr": op("muldiv", var("sales"), param("rate"), lit(1), rounding="floor"),
        },
        {
            "name": "payable",
            "label": "支払うべき使用料",
            "expr": op("max", step("base"), param("min_royalty")),
        },
    ],
    output={"step": "payable", "type": "int", "unit": "JPY"},
    obligations=["rounding:exact", "minimum:difference_topped_up"],
)

Q(
    "lic-0002",
    "qa_auth_010",
    answer_kind="amount",
    title="純売上高2000万円のときの使用料",
    params=dict(_LIC2_PARAMS),
    inputs={"sales": IN("int", "JPY", desc="報告期間の純売上高", min=0, max=1_000_000_000)},
    given={"sales": 20_000_000},
    const_keys={"rate": "rate", "min_royalty": "min_royalty"},
    parties=PAYER_OTSU,
    steps=[
        {
            "name": "base",
            "label": "料率による使用料",
            "expr": op("muldiv", var("sales"), param("rate"), lit(1), rounding="floor"),
        },
        {
            "name": "payable",
            "label": "支払うべき使用料",
            "expr": op("max", step("base"), param("min_royalty")),
        },
    ],
    output={"step": "payable", "type": "int", "unit": "JPY"},
    obligations=["rounding:exact", "minimum:difference_topped_up"],
)

# ==== nda-0001 =================================================================

Q(
    "nda-0001",
    "qa_auth_008",
    answer_kind="date",
    title="秘密保持義務が終わる日",
    params={
        "term_years": P_int(2, "YEAR", "２年", "a6_p1", "契約を締結した日から２年とする"),
        "survival_years": P_int(5, "YEAR", "５年", "a6_p3", "本契約が終了した日から５年存続する"),
    },
    inputs={"contract_date": IN("date", desc="契約締結日")},
    given={"contract_date": "2026-05-18"},
    meta_date_inputs=["contract_date"],
    const_keys={"term_years": "term_years", "survival_years": "survival_years"},
    steps=[
        {
            "name": "end_date",
            "label": "契約の終了日",
            "expr": op("add_months", var("contract_date"), op("mul", param("term_years"), lit(12))),
        },
        {
            "name": "survive_until",
            "label": "義務が終わる日",
            "expr": op("add_months", step("end_date"), op("mul", param("survival_years"), lit(12))),
        },
    ],
    output={"step": "survive_until", "type": "date"},
    obligations=["period_count:anniversary"],
    flags=[
        "第7条に自動更新の定めがあり、設問は「期間の満了により終了した場合」と固定している。この前提の書きぶりで曖昧さが残らないか",
        "「締結した日から２年」の満了を応当日（5/18）と読んだ（前日と読む流儀もある）",
    ],
)

Q(
    "nda-0001",
    "qa_auth_009",
    answer_kind="day_ordinal",
    title="廃棄報告の期限（請求日から何日目か）",
    params={
        "return_days": P_int(
            10,
            "DAY",
            "１０日",
            "a5_p1",
            "請求を受けた日のいずれか早い日から１０日以内に、記録媒体を返還し、または廃棄する",
        ),
        "report_days": P_int(7, "DAY", "７日", "a5_p2", "廃棄を完了した日から７日以内に"),
    },
    const_keys={"return_days": "return_days", "report_days": "report_days"},
    steps=[
        {
            "name": "total_days",
            "label": "請求日から報告期限までの日数",
            "expr": op("add", param("return_days"), param("report_days")),
        }
    ],
    output={"step": "total_days", "type": "int", "unit": "DAY"},
    obligations=["worst_case:destroy_on_last_day"],
    flags=["「期限どおりに廃棄した場合」という最悪ケースを答えにしている点の是非"],
)

# ==== nda-0002 =================================================================

Q(
    "nda-0002",
    "qa_auth_009",
    answer_kind="date",
    title="秘密を守る義務が終わる日",
    params={
        "purpose_months": P_int(8, "MONTH", "８か月", "a7_p1", "契約を締結した日から８か月とする"),
        "survival_years": P_int(7, "YEAR", "７年", "a7_p2", "本契約が終了した日から７年存続する"),
    },
    inputs={"contract_date": IN("date", desc="契約締結日")},
    given={"contract_date": "2028-06-05"},
    meta_date_inputs=["contract_date"],
    const_keys={"purpose_months": "purpose_months", "survival_years": "survival_years"},
    steps=[
        {
            "name": "end_date",
            "label": "契約の終了日",
            "expr": op("add_months", var("contract_date"), param("purpose_months")),
        },
        {
            "name": "survive_until",
            "label": "義務が終わる日",
            "expr": op("add_months", step("end_date"), op("mul", param("survival_years"), lit(12))),
        },
    ],
    output={"step": "survive_until", "type": "date"},
    obligations=["period_count:anniversary"],
    notes=["満了＝応当日の読みは nda-0001 と同じ"],
)

Q(
    "nda-0002",
    "qa_auth_010",
    answer_kind="day_ordinal",
    title="廃棄報告の期限（求めの日から何日目か）",
    params={
        "return_days": P_int(21, "DAY", "２１日", "a6_p1", "２１日以内に保存媒体を返還し、または廃棄する"),
        "destroy_report_days": P_int(10, "DAY", "１０日", "a6_p3", "廃棄を完了した日から１０日以内に"),
    },
    const_keys={"return_days": "return_days", "destroy_report_days": "destroy_report_days"},
    steps=[
        {
            "name": "total_days",
            "label": "求めの日から報告期限までの日数",
            "expr": op("add", param("return_days"), param("destroy_report_days")),
        }
    ],
    output={"step": "total_days", "type": "int", "unit": "DAY"},
    obligations=["worst_case:destroy_on_last_day"],
    flags=["「期限どおりに廃棄した」最悪ケースを答えにしている点の是非（nda-0001 と同じ考え方）"],
)

# ==== ots-0001 =================================================================

Q(
    "ots-0001",
    "qa_auth_009",
    answer_kind="day_ordinal",
    title="みなし合格の成立日（引渡しの日から何日目か）",
    params={"accept_days": P_int(10, "DAY", "10日", "a4_p2", "引渡しを受けた日から10日以内に検査を行い")},
    const_keys={"accept_days": "accept_days"},
    steps=[
        {
            "name": "deemed_day",
            "label": "みなし合格の日（引渡しの日から数えた日数）",
            "expr": param("accept_days"),
        }
    ],
    output={"step": "deemed_day", "type": "int", "unit": "DAY"},
    obligations=["deemed:at_period_expiry"],
    flags=[
        "「10日以内」の期間の満了を「10日目」と数えてよいか（a4_p3「その期間の満了の時に検査に合格したものとみなす」）"
    ],
)

Q(
    "ots-0001",
    "qa_auth_010",
    answer_kind="day_ordinal",
    title="補正後の再引渡しの日（最初の引渡しから何日目か）",
    params={
        "redeliver_days": P_int(
            14, "DAY", "14日", "a4_p4", "求めを受けた日から14日以内に補正したものを引き渡し"
        )
    },
    const_keys={"redeliver_days": "redeliver_days"},
    steps=[
        {
            "name": "redeliver_day",
            "label": "再引渡しの日（最初の引渡しから数えた日数）",
            "expr": param("redeliver_days"),
        }
    ],
    output={"step": "redeliver_day", "type": "int", "unit": "DAY"},
    obligations=["scenario:correction_requested_same_day"],
    flags=[
        "「引渡しの当日に補正を求め」という条件の固定が設問文で十分に明示できているか（検査に10日かけると24日目になる）"
    ],
)

# ==== ots-0002 =================================================================

Q(
    "ots-0002",
    "qa_auth_009",
    answer_kind="date",
    title="実施計画の提出期限",
    params={"plan_days": P_int(45, "DAY", "４５日", "a2_p1", "本件公演の４５日前までに実施計画を作成し")},
    inputs={"performance_date": IN("date", desc="公演の日")},
    given={"performance_date": "2029-03-21"},
    const_keys={"plan_days": "plan_days"},
    steps=[
        {
            "name": "deadline",
            "label": "提出期限",
            "expr": op("add_days", var("performance_date"), op("sub", lit(0), param("plan_days"))),
        }
    ],
    output={"step": "deadline", "type": "date"},
    obligations=["day_count:days_before_event"],
    notes=["2029年2月は28日（うるう年でない）。暦の引き算で機械的に確かめた"],
)

Q(
    "ots-0002",
    "qa_auth_010",
    answer_kind="amount",
    title="実施計画の承認時に支払う前払の額",
    params={
        "total_fee": P_int(4_200_000, "JPY", "４２０万円", "a6_p1", "総額は４２０万円とする"),
        "advance_rate": P_ratio(4, 10, "４割", "a6_p2", "委託料の４割に相当する額を前払として支払う"),
    },
    const_keys={"total_fee": "total_fee", "advance_rate": "advance_rate"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "advance",
            "label": "前払の額",
            "expr": op("muldiv", param("total_fee"), param("advance_rate"), lit(1), rounding="floor"),
        }
    ],
    output={"step": "advance", "type": "int", "unit": "JPY"},
    obligations=["rounding:exact"],
)

# ==== pur-0001 =================================================================

Q(
    "pur-0001",
    "qa_auth_009",
    answer_kind="date",
    title="みなし合格の日",
    params={"inspect_days": P_int(14, "DAY", "１４日", "a4_p1", "納入を受けた日から１４日以内に検査を行い")},
    inputs={"delivery_date": IN("date", desc="納入を受けた日")},
    given={"delivery_date": "2027-02-26"},
    const_keys={"inspect_days": "inspect_days"},
    steps=[
        {
            "name": "deemed_date",
            "label": "みなし合格の日",
            "expr": op("add_days", var("delivery_date"), param("inspect_days")),
        }
    ],
    output={"step": "deemed_date", "type": "date"},
    obligations=["day_count:initial_day_excluded", "deemed:at_period_expiry"],
    flags=["起算を納入日の翌日とする読みを採った（当日起算なら 3/11 になる）"],
)

Q(
    "pur-0001",
    "qa_auth_010",
    answer_kind="number_plain",
    title="表1の小計＋消費税等と契約金額の一致",
    params={
        "subtotal": P_int(7_465_000, "JPY", "７，４６５，０００", "tbl_inv__r7c4", "７，４６５，０００"),
        "tax": P_int(400_000, "JPY", "４００，０００", "tbl_inv__r8c4", "４００，０００"),
        "head_total": P_int(7_865_000, "JPY", "７８６万５０００円", "head_i4_d", "７８６万５０００円"),
    },
    const_keys={"head_total": "total_price"},
    parties=PAYER_KO,
    steps=[
        {"name": "total", "label": "小計と消費税等の合計", "expr": op("add", param("subtotal"), param("tax"))}
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["crosscheck:equals_head_matter_total"],
    notes=[
        "合計が頭書の契約金額（786万5000円）と一致することは verify が突合する（L11 は表の中の加算を見ない）"
    ],
)

# ==== pur-0002 =================================================================

Q(
    "pur-0002",
    "qa_auth_008",
    answer_kind="date",
    title="性能確認試験の期限",
    params={"inspect_days": P_int(10, "DAY", "10日", "a4_p1", "通知を受けた日から10日以内")},
    inputs={"notify_date": IN("date", desc="据付工事の完了の通知を受けた日")},
    given={"notify_date": "2029-03-02"},
    const_keys={"inspect_days": "inspect_days"},
    steps=[
        {
            "name": "deadline",
            "label": "試験の期限",
            "expr": op("add_days", var("notify_date"), param("inspect_days")),
        }
    ],
    output={"step": "deadline", "type": "date"},
    obligations=["day_count:initial_day_excluded"],
)

Q(
    "pur-0002",
    "qa_auth_009",
    answer_kind="amount",
    title="請求から25日以内に支払う額（留保を控除）",
    params={
        "total_price": P_int(12_648_000, "JPY", "1264万8000円", "head_i5_d", "1264万8000円"),
        "retention_rate": P_ratio(1, 10, "1割", "a6_p3", "契約金額の1割を留保し"),
    },
    const_keys={"total_price": "total_price", "retention_rate": "retention_rate"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "retention",
            "label": "留保の額",
            "expr": op("muldiv", param("total_price"), param("retention_rate"), lit(1), rounding="floor"),
        },
        {"name": "payment", "label": "支払う額", "expr": op("sub", param("total_price"), step("retention"))},
    ],
    output={"step": "payment", "type": "int", "unit": "JPY"},
    obligations=["rounding:exact"],
)

Q(
    "pur-0002",
    "qa_auth_010",
    answer_kind="date",
    title="留保した額を支払う日",
    params={"defect_months": P_int(18, "MONTH", "18か月", "a7_p1", "引取りの日から18か月以内に限り")},
    inputs={"pickup_date": IN("date", desc="引取りの日")},
    given={"pickup_date": "2029-03-20"},
    const_keys={"defect_months": "defect_months"},
    steps=[
        {
            "name": "period_end_date",
            "label": "契約不適合責任の期間の満了日",
            "expr": op("add_months", var("pickup_date"), param("defect_months")),
        },
        {"name": "payday", "label": "留保額の支払日", "expr": op("end_of_month", step("period_end_date"))},
    ],
    output={"step": "payday", "type": "date"},
    obligations=["period_count:anniversary", "payday:end_of_month_of_expiry"],
    notes=["「満了した日の属する月の末日」は本文に根拠がある（a6_p3）。満了＝応当日（2030/9/20）の読み"],
)

# ==== sys-0001 =================================================================

Q(
    "sys-0001",
    "qa_auth_009",
    answer_kind="day_ordinal",
    title="みなし検収の成立日（納入の日から何日目か）",
    params={
        "deemed_days": P_int(
            20, "DAY", "２０日", "ch2_a2_p4", "納入の日から２０日を経過しても通知を発しないとき"
        )
    },
    const_keys={"deemed_days": "deemed_days"},
    steps=[
        {
            "name": "deemed_day",
            "label": "みなし検収の日（納入の日から数えた日数）",
            "expr": param("deemed_days"),
        }
    ],
    output={"step": "deemed_day", "type": "int", "unit": "DAY"},
    obligations=["deemed:after_elapsed_days"],
    flags=[
        "検収の期限（14日）とみなし検収（20日）が別の数である関係が、読み手に伝わる書きぶりになっているか"
    ],
)

Q(
    "sys-0001",
    "qa_auth_010",
    answer_kind="day_ordinal",
    title="個別契約のみなし成立日（注文書を発した日から何日目か）",
    params={
        "order_reply_days": P_int(
            7, "DAY", "７日", "ch1_a3_p2", "注文書を受け取った日から７日以内に諾否を示さないとき"
        )
    },
    const_keys={"order_reply_days": "order_reply_days"},
    steps=[
        {
            "name": "deemed_day",
            "label": "みなし成立の日（発した日から数えた日数）",
            "expr": param("order_reply_days"),
        }
    ],
    output={"step": "deemed_day", "type": "int", "unit": "DAY"},
    obligations=["scenario:dispatch_equals_receipt"],
    flags=[
        "条文の起算は「受け取った日」だが設問は「発した日」を起点にしている。発送と受領が同日という前提に本文上の根拠がない"
    ],
)

# ==== sys-0002 =================================================================

Q(
    "sys-0002",
    "qa_auth_008",
    answer_kind="date",
    title="みなし受入れの日",
    params={
        "deemed_days": P_int(
            10, "DAY", "10日", "ch2_a2_p4", "反復レビューの日から10日を経た日に受け入れたものとみなす"
        )
    },
    inputs={"review_date": IN("date", desc="反復レビューの日")},
    given={"review_date": "2033-05-12"},
    const_keys={"deemed_days": "deemed_days"},
    steps=[
        {
            "name": "deemed_date",
            "label": "みなし受入れの日",
            "expr": op("add_days", var("review_date"), param("deemed_days")),
        }
    ],
    output={"step": "deemed_date", "type": "date"},
    obligations=["day_count:elapsed_from_review"],
    notes=["通知の期限（4日）とは別の日数であることを確認済み（ch2_a2_p3）"],
)

Q(
    "sys-0002",
    "qa_auth_009",
    answer_kind="amount",
    title="リリース物を作る反復1回の対価",
    params={
        "unit_price": P_int(4_180_000, "JPY", "1反復あたり418万円", "tbl_price__r1c1", "1反復あたり418万円"),
        "release_add": P_int(620_000, "JPY", "62万円", "tbl_price__r2c1", "418万円に62万円を加えた額"),
    },
    const_keys={"unit_price": "unit_price"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "price",
            "label": "リリース反復1回の対価",
            "expr": op("add", param("unit_price"), param("release_add")),
        }
    ],
    output={"step": "price", "type": "int", "unit": "JPY"},
    obligations=["source:price_table"],
)

Q(
    "sys-0002",
    "qa_auth_010",
    answer_kind="amount",
    title="上限回数までの反復の対価の合計（税抜）",
    params={
        "unit_price": P_int(4_180_000, "JPY", "1反復あたり418万円", "tbl_price__r1c1", "1反復あたり418万円"),
        "release_add": P_int(620_000, "JPY", "62万円", "tbl_price__r2c1", "418万円に62万円を加えた額"),
        "iterations": P_int(12, "COUNT", "12回", "ch2_a1_p1", "12回を上限とする"),
    },
    inputs={"release_count": IN("int", "COUNT", desc="リリース物を作る反復の回数", min=0, max=12)},
    given={"release_count": 2},
    const_keys={"unit_price": "unit_price", "iterations": "iterations"},
    parties=PAYER_KO,
    steps=[
        {
            "name": "base_total",
            "label": "基本の対価の合計",
            "expr": op("mul", param("unit_price"), param("iterations")),
        },
        {
            "name": "release_total",
            "label": "リリース加算の合計",
            "expr": op("mul", param("release_add"), var("release_count")),
        },
        {
            "name": "total",
            "label": "対価の合計（消費税に相当する額を含まない）",
            "expr": op("add", step("base_total"), step("release_total")),
        },
    ],
    output={"step": "total", "type": "int", "unit": "JPY"},
    obligations=["tax:excluded_by_question"],
)
