"""Sheet-level comparison logic (ported from legacy sanityscript)."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import textdistance as td

from sanitycheck.models import ComparisonResult

logger = logging.getLogger(__name__)

STATUS_FACTOR = pd.CategoricalDtype(
    ["Removed", "Modified", "Added", "Unchanged"], ordered=True
)


def tabulate(
    input_feed: list[pd.DataFrame],
    output_feed: dict[str, pd.DataFrame | None],
    starting_value: str,
    starting_column: int,
) -> None:
    for table, key in zip(input_feed, output_feed.keys()):
        sc_start = table.index[table.iloc[:, starting_column] == starting_value].to_list()[0]
        sc_col_names = table.iloc[sc_start, :].to_list()
        sc_feed = table.iloc[sc_start + 1 :, :].reset_index(drop=True)
        sc_feed.columns = sc_col_names
        output_feed[key] = sc_feed


def run_name_smry_table(name_test: str, name_feed: str, result: ComparisonResult) -> None:
    result.tbl_filenames = pd.DataFrame(
        [["Original File", name_feed], ["Test File", name_test]],
        columns=["Compare", "File Name"],
    )


def get_sheets_table(
    wk_test: dict[str, pd.DataFrame], wk: dict[str, pd.DataFrame], result: ComparisonResult
) -> None:
    test_sheets = set(wk_test.keys())
    feed_sheets = set(wk.keys())
    result.additional_sheets = test_sheets.difference(feed_sheets)
    result.removed_sheets = feed_sheets.difference(test_sheets)
    result.paired_sheets = test_sheets.intersection(feed_sheets)
    result.tbl_avail_sheets = pd.DataFrame(
        [result.paired_sheets, result.additional_sheets, result.removed_sheets]
    ).T.fillna("")
    result.tbl_avail_sheets.columns = [
        "Paired sheets",
        "Additional sheets",
        "Removed sheets",
    ]


def _df_has_change_status(df: pd.DataFrame | None, col: str = "Status") -> bool:
    if df is None or df.empty or col not in df.columns:
        return False
    return df[col].isin(["Modified", "Added", "Removed"]).any()


def get_overall_change_summary(
    wk_test: dict[str, pd.DataFrame], wk: dict[str, pd.DataFrame], result: ComparisonResult
) -> None:
    test_sheets = set(wk_test.keys())
    feed_sheets = set(wk.keys())
    possible_sheets = [
        "Data Feed Setup",
        "Subsidiary Mapping",
        "Screen Criteria",
        "Factor List",
        "APL Definition",
    ]
    additional_sheets = test_sheets.difference(feed_sheets)
    removed_sheets = feed_sheets.difference(test_sheets)
    paired_sheets = test_sheets.intersection(feed_sheets)
    available_sheets = test_sheets.union(feed_sheets)

    def validate(name: str, df: pd.DataFrame | None, col_name: str = "Status") -> bool:
        if name not in paired_sheets:
            return False
        return _df_has_change_status(df, col_name)

    modified_flags = [
        validate("Data Feed Setup", result.feed_differences),
        validate("Subsidiary Mapping", result.tbl_smry_val_comparison),
        validate("Screen Criteria", result.tbl_screening_changes, "Logic Change"),
        validate("Factor List", result.tbl_factor_list_merge),
        validate("APL Definition", result.tbl_first_apl)
        or validate("APL Definition", result.tbl_second_apl_smry),
    ]

    modified_sheets = pd.DataFrame(
        {"Worksheet": possible_sheets, "Modified": modified_flags}
    ).assign(Status="")
    modified_sheets.loc[modified_sheets["Modified"] == True, "Status"] = "Modified"
    modified_sheets.set_index("Worksheet", inplace=True)
    modified_sheets.loc[list(additional_sheets), "Status"] = "Added"
    modified_sheets.loc[list(removed_sheets), "Status"] = "Removed"
    idx = modified_sheets.index.intersection(set(available_sheets))
    modified_sheets = modified_sheets.loc[idx, :]
    modified_sheets.loc[modified_sheets["Status"] == "", "Status"] = "Unchanged"
    result.tbl_overall_change = modified_sheets.reset_index().drop(columns="Modified")


def run_sc_datafeedsetup(
    wk_test: dict[str, pd.DataFrame],
    wk: dict[str, pd.DataFrame],
    filetype: str,
    result: ComparisonResult,
) -> None:
    test_feed = wk_test["Data Feed Setup"].copy()
    feed = wk["Data Feed Setup"].copy()

    std_feed_report_cols = [
        "Zip Results",
        "Universe Type",
        "Screen Name",
        "Factor List Name",
        "Subsidiary Mapping",
        "Multiple Security",
    ] + [
        "Standard Report Options - " + j
        for j in [
            "Horizontal",
            "Vertical",
            "APL",
            "Cases",
            "Security Identifiers",
            "Security Factors To Add",
        ]
    ]
    fund_feed_report_cols = [
        "Screen Name:",
        "Factor List Name:",
        "Workflow Batch:",
        "Region:",
        "Product:",
        "Zip Results:",
        "Location Realm:",
    ] + [
        "Report Options -" + j + ":"
        for j in [
            "Universe Type",
            "Portfolio",
            "Portfolio Idents",
            "Report types",
            "Identifiers",
            "License Only",
            "Options",
        ]
    ]

    test_feed.columns, feed.columns = [["Columns", "Value1", "Value2"]] * 2

    test_feed = test_feed[~(test_feed.isna().sum(axis=1) == 3)]
    feed = feed[~(feed.isna().sum(axis=1) == 3)]
    test_feed.loc[:, "Columns"] = test_feed.loc[:, "Columns"].ffill()
    feed.loc[:, "Columns"] = feed.loc[:, "Columns"].ffill()

    feed_list: list[pd.DataFrame] = [test_feed, feed]
    use_fund = filetype.strip().lower().startswith("fund")

    for i, table in enumerate(feed_list):
        std_rep_opts = table["Columns"] == "Standard Report Options"
        table.loc[std_rep_opts, "Columns"] = (
            table["Columns"] + " - " + table["Value1"].astype(str)
        )[std_rep_opts]
        table.loc[std_rep_opts, "Value1"] = table["Value2"][std_rep_opts]
        table.loc[:, "Columns"] = table["Columns"].str.replace(":", "", regex=False)
        table.drop(columns="Value2", inplace=True)
        table.fillna("", inplace=True)
        if not use_fund:
            feed_list[i] = table.loc[table["Columns"].isin(std_feed_report_cols), :]
        else:
            feed_list[i] = table.loc[table["Columns"].isin(fund_feed_report_cols), :]

    feed_comparison = feed_list[0].merge(
        feed_list[1], on="Columns", how="left", suffixes=("_test", "")
    ).assign(Diff=lambda x: x["Value1_test"] != x["Value1"])
    feed_differences = feed_comparison[feed_comparison["Diff"] == True].drop(
        columns="Diff"
    )
    feed_differences.columns = ["Fields", "New value", "Old Value"]
    result.feed_differences = feed_differences.assign(Status="Modified").loc[
        :, ["Fields", "Status", "New value", "Old Value"]
    ]


def run_sc_screencriteria(
    wk_test: dict[str, pd.DataFrame],
    wk: dict[str, pd.DataFrame],
    result: ComparisonResult,
) -> None:
    test_feed = wk_test["Screen Criteria"]
    feed = wk["Screen Criteria"]
    sc_list: dict[str, pd.DataFrame | None] = {"Test": None, "Feed": None}
    tabulate([test_feed, feed], sc_list, "Category Path", 0)
    assert sc_list["Test"] is not None and sc_list["Feed"] is not None
    sc_list["Test"] = sc_list["Test"].fillna("")
    sc_list["Feed"] = sc_list["Feed"].fillna("")

    def concatenate_params(df: pd.DataFrame) -> pd.Series:
        x = df.loc[:, ["Not", "(", "Operator", "Criteria", ")", "And/Or"]]
        return (
            pd.Series([*map(lambda row: ", ".join('"' + row + '"'), x.values)])
            .str.replace('"", ', "", regex=False)
            .str.replace(', ""', "", regex=False)
        )

    sc_list["Feed"]["FullCriteria"] = concatenate_params(sc_list["Feed"])
    sc_list["Test"]["FullCriteria"] = concatenate_params(sc_list["Test"])

    # Align rows with duplicate Column Header by sheet row order (1st with 1st, 2nd with 2nd).
    # Merging on Column Header alone creates a Cartesian product and false "Modified" rows.
    _t = sc_list["Test"].reset_index()
    _t["_hdr_occ"] = _t.groupby("Column Header", sort=False).cumcount()
    _f = sc_list["Feed"].reset_index()
    _f["_hdr_occ"] = _f.groupby("Column Header", sort=False).cumcount()

    df_output_format = (
        _t[["Column Header", "FullCriteria", "index", "_hdr_occ"]]
        .merge(
            _f[["Column Header", "FullCriteria", "index", "_hdr_occ"]],
            on=["Column Header", "_hdr_occ"],
            how="outer",
            suffixes=("", "_feed"),
        )
        .rename(
            columns={"FullCriteria_feed": "Old value", "FullCriteria": "New value"},
        )
        .drop(columns=["_hdr_occ"])
    )
    df_output_format[["index", "index_feed"]] = (
        df_output_format[["index", "index_feed"]] + 1
    ).copy()

    sc_changing_col_headers = (
        df_output_format.where(lambda x: x["New value"] != x["Old value"])
        .dropna()
        .drop(columns=["index_feed"])
        .assign(Status="Modified")
        .rename(columns={"index": "Row"})
    )
    sc_additional_col_headers = (
        df_output_format.where(lambda x: x["Old value"].isna())
        .dropna(subset=["Column Header"])
        .drop(columns=["index_feed"])
        .assign(Status="Added")
        .rename(columns={"index": "Row"})
    )
    sc_removed_col_headers = (
        df_output_format.where(lambda x: x["New value"].isna())
        .dropna(subset=["Column Header"])
        .drop(columns=["index"])
        .assign(Status="Removed")
        .rename(columns={"index_feed": "Row"})
    )

    df_screening_changes = pd.concat(
        [sc_changing_col_headers, sc_additional_col_headers, sc_removed_col_headers]
    ).fillna("")
    df_screening_changes["Row"] = df_screening_changes["Row"].astype(int)
    df_screening_changes["Td"] = [
        *map(
            lambda t: td.levenshtein(t[0], t[1]),
            zip(df_screening_changes["New value"], df_screening_changes["Old value"]),
        )
    ]

    tbl_screening_changes = (
        df_screening_changes.merge(
            df_screening_changes.groupby(["Column Header", "New value", "Row"], sort=False)[
                "Td"
            ]
            .min()
            .to_frame()
            .reset_index(),
            on=["Column Header", "New value", "Row"],
            suffixes=("", "_min"),
        )
        .where(lambda x: x["Td"] == x["Td_min"])
        .dropna(subset=["Column Header"])
        .drop(columns=["Td_min", "Td"])
        .sort_values(by=["Status"])
        .rename(columns={"Status": "Logic Change"})
    )
    tbl_screening_changes = tbl_screening_changes[
        ["Column Header", "Logic Change", "New value", "Old value", "Row"]
    ]
    tbl_screening_changes["Row"] = (
        tbl_screening_changes["Row"].astype(int).astype(str)
    )

    result.tbl_screening_changes = tbl_screening_changes


def run_sc_factorlist(
    wk_test: dict[str, pd.DataFrame],
    wk: dict[str, pd.DataFrame],
    result: ComparisonResult,
) -> None:
    test_feed = wk_test["Factor List"]
    feed = wk["Factor List"]
    sc_list: dict[str, pd.DataFrame | None] = {"Test": None, "Feed": None}
    tabulate([test_feed, feed], sc_list, "Category Path", 0)
    assert sc_list["Test"] is not None and sc_list["Feed"] is not None

    _cols = ["Column Header", "Factor Name", "Data Type"]
    _flt = sc_list["Test"].loc[:, _cols].reset_index()
    _flt = _flt.sort_values(
        by=["Column Header", "Factor Name", "Data Type", "index"],
        kind="mergesort",
    )
    _flt["_ch_occ"] = _flt.groupby("Column Header", sort=False).cumcount()
    _flf = sc_list["Feed"].loc[:, _cols].reset_index()
    _flf = _flf.sort_values(
        by=["Column Header", "Factor Name", "Data Type", "index"],
        kind="mergesort",
    )
    _flf["_ch_occ"] = _flf.groupby("Column Header", sort=False).cumcount()
    df_factor_list_merge = (
        _flt.merge(
            _flf,
            on=["Column Header", "_ch_occ"],
            how="outer",
            suffixes=("", "_old"),
        )
        .drop(columns=["_ch_occ"])
        .assign(
            index_old=lambda x: x["index_old"] + 1,
            index=lambda x: x["index"] + 1,
        )
    )

    _ix = df_factor_list_merge["index"]
    _ixo = df_factor_list_merge["index_old"]
    _fn_eq = df_factor_list_merge["Factor Name"].fillna("").astype(str).eq(
        df_factor_list_merge["Factor Name_old"].fillna("").astype(str)
    )
    _dt_eq = df_factor_list_merge["Data Type"].fillna("").astype(str).eq(
        df_factor_list_merge["Data Type_old"].fillna("").astype(str)
    )
    _content_unchanged = _fn_eq & _dt_eq
    _t_miss = _ix.isna()
    _f_miss = _ixo.isna()
    df_factor_list_merge["Status"] = np.where(
        _t_miss,
        "Removed",
        np.where(_f_miss, "Added", np.where(_content_unchanged, "Unchanged", "Modified")),
    )

    df_factor_list_print = df_factor_list_merge.rename(
        columns={"index": "Row_Test", "index_old": "Row_Feed"}
    )[["Column Header", "Status", "Row_Test", "Row_Feed"]].copy()

    tbl_factor_list_merge = (
        df_factor_list_print.loc[df_factor_list_print["Status"] != "Unchanged", :]
        .assign(Status=lambda x: x["Status"].astype(STATUS_FACTOR))
        .sort_values(by=["Status", "Row_Test"])
        .assign(Status=lambda x: x["Status"].astype(str))
        .where(lambda x: x["Status"] != "Unchanged")
        .dropna(subset=["Status"])
        .reset_index(drop=True)
    )
    tbl_factor_list_merge[["Row_Test", "Row_Feed"]] = (
        tbl_factor_list_merge[["Row_Test", "Row_Feed"]]
        .fillna(0)
        .apply(lambda x: x.astype(int, errors="ignore"))
        .apply(lambda x: x.astype(str))
        .apply(lambda x: x.str.replace("^0", "", regex=True))
    ).copy()
    tbl_factor_list_merge.drop(columns=["Row_Feed"], inplace=True)
    result.tbl_factor_list_merge = tbl_factor_list_merge


def run_sc_subsidiarymapping(
    wk_test: dict[str, pd.DataFrame],
    wk: dict[str, pd.DataFrame],
    result: ComparisonResult,
) -> None:
    test_feed = wk_test["Subsidiary Mapping"]
    feed = wk["Subsidiary Mapping"]

    ias_test_index = test_feed.index[
        test_feed.iloc[:, 0] == "Include Additional Subsidiaries:"
    ].to_list()[0]
    ias_feed_index = feed.index[
        feed.iloc[:, 0] == "Include Additional Subsidiaries:"
    ].to_list()[0]

    val_test = test_feed.iloc[ias_test_index, 1]
    val_feed = feed.iloc[ias_feed_index, 1]
    fact_check_ias = val_test != val_feed

    tbl_ias = pd.DataFrame({"Fields": "Include Additional Subsidiaries"}, index=[0])
    tbl_ias["Status"] = "Modified" if fact_check_ias else "Unchanged"
    tbl_ias["Data Change"] = "True" if fact_check_ias else ""

    sc_list: dict[str, pd.DataFrame | None] = {"Test": None, "Feed": None}
    tabulate([test_feed, feed], sc_list, "Copy Value", 0)
    assert sc_list["Test"] is not None and sc_list["Feed"] is not None

    sm_fields = ["Copy Value", "Column Header", "Level", "Issuer Name", "Issuer ID"]

    def _sm_row_signature(row: pd.Series) -> str:
        # iterrows values can be float/NA; astype(str) is not always all-str for join()
        vals = row.reindex(sm_fields)
        parts: list[str] = []
        for v in vals.tolist():
            parts.append("" if pd.isna(v) else str(v))
        return "-".join(parts)

    clps_rows_sm_test = pd.Series(
        [_sm_row_signature(row) for _, row in sc_list["Test"].iterrows()],
        index=range(0, sc_list["Test"].shape[0]),
    )
    clps_rows_sm_feed = pd.Series(
        [_sm_row_signature(row) for _, row in sc_list["Feed"].iterrows()],
        index=range(0, sc_list["Feed"].shape[0]),
    )

    clps_rows_sm_test_changes = clps_rows_sm_test[~clps_rows_sm_test.isin(clps_rows_sm_feed)]
    sm_changes = sc_list["Test"].loc[clps_rows_sm_test_changes.index].reset_index(drop=True)
    sm_changes["Factor_IsNew"] = ~sm_changes["Column Header"].isin(
        sc_list["Feed"]["Column Header"]
    )

    sm_changes_existing = (
        sm_changes[sm_changes["Factor_IsNew"] == False]
        .fillna("")
        .merge(
            sc_list["Feed"]
            .drop(columns=["Used In Screen", "Column Header"])
            .fillna(""),
            how="left",
            on="Factor Name",
            suffixes=("", "_feed"),
        )
    )

    tbl_sm_order = np.sort(sm_changes_existing.columns.values)
    tbl_sm_changes_existingfactors = sm_changes_existing.loc[:, tbl_sm_order]

    sm_val_comparison = tbl_sm_changes_existingfactors.assign(
        Copy_Value=lambda x: x["Copy Value"] != x["Copy Value_feed"],
        Level_Value=lambda x: x["Level"] != x["Level_feed"],
        Issuer_Name=lambda x: x["Issuer Name"] != x["Issuer Name_feed"],
        Issuer_Id=lambda x: x["Issuer ID"] != x["Issuer ID_feed"],
    )
    smry_val_comparison = dict(
        sm_val_comparison.loc[:, "Copy_Value":].apply(np.sum)
    )
    sm_factorchanges_copyvalue = ",".join(
        sm_val_comparison.loc[sm_val_comparison["Copy_Value"] == True, "Column Header"].values
    )
    sm_factorchanges_levelvalue = ",".join(
        sm_val_comparison.loc[sm_val_comparison["Level_Value"] == True, "Column Header"].values
    )
    sm_factorchanges_issuername = ",".join(
        sm_val_comparison.loc[sm_val_comparison["Issuer_Name"] == True, "Column Header"].values
    )
    sm_factorchanges_issuerid = ",".join(
        sm_val_comparison.loc[sm_val_comparison["Issuer_Id"] == True, "Column Header"].values
    )

    df_smry_val_comparison = pd.DataFrame(
        pd.Series(smry_val_comparison), columns=["Row changes"]
    )
    sm_factorchanges_details = pd.Series(
        [
            sm_factorchanges_copyvalue,
            sm_factorchanges_levelvalue,
            sm_factorchanges_issuername,
            sm_factorchanges_issuerid,
        ],
        index=["Copy_Value", "Level_Value", "Issuer_Name", "Issuer_Id"],
        name="Column Headers",
    )
    df_smry_val_comparison_counting = (
        df_smry_val_comparison.merge(
            sm_factorchanges_details,
            left_index=True,
            right_index=True,
            how="left",
        )
        .reset_index(drop=False)
        .rename(columns={"index": "Fields", "Column Headers": "Data Change"})
    )
    df_smry_val_comparison_counting["Status"] = [
        "Modified" if val >= 1 else "Unchanged"
        for val in df_smry_val_comparison_counting["Row changes"]
    ]
    tbl_smry_val_comparison = (
        pd.concat(
            [tbl_ias, df_smry_val_comparison_counting.loc[:, ["Fields", "Status", "Data Change"]]]
        )
        .reset_index(drop=True)
        .where(lambda x: x["Status"] != "Unchanged")
        .dropna()
    )
    result.tbl_smry_val_comparison = tbl_smry_val_comparison


def run_sc_apl(
    wk_test: dict[str, pd.DataFrame],
    wk: dict[str, pd.DataFrame],
    result: ComparisonResult,
) -> None:
    test_feed = wk_test["APL Definition"]
    feed = wk["APL Definition"]

    sc_list: dict[str, pd.DataFrame | None] = {"Test": None, "Feed": None}
    tabulate([test_feed, feed], sc_list, "New Value", 3)
    assert sc_list["Test"] is not None and sc_list["Feed"] is not None
    sc_list["Test"] = sc_list["Test"].dropna(subset=["New Value"]).iloc[:, 3:]
    sc_list["Feed"] = sc_list["Feed"].dropna(subset=["New Value"]).iloc[:, 3:]

    par_list: dict[str, pd.DataFrame | None] = {"Test": None, "Feed": None}
    tabulate([test_feed, feed], par_list, "Date Format:", 0)
    assert par_list["Test"] is not None and par_list["Feed"] is not None
    par_test = par_list["Test"].iloc[0, 0:2]
    par_test_data = pd.DataFrame(
        [par_test.index.values, par_test.values], columns=["Columns", "Values"]
    )
    par_feed = par_list["Feed"].iloc[0, 0:2]
    par_feed_data = pd.DataFrame(
        [par_feed.index.values, par_feed.values], columns=["Columns", "Values"]
    )
    par_comparison = par_test_data.merge(
        par_feed_data, on="Columns", how="left", suffixes=("_test", "_feed")
    )
    par_changes = par_comparison.loc[
        par_comparison["Values_test"] != par_comparison["Values_feed"], :
    ]
    logger.info(
        "APL settings changed: %s",
        (par_comparison["Values_test"] != par_comparison["Values_feed"]).any(),
    )
    par_changes.columns = ["Fields", "New Value", "Old Value"]
    tbl_par_changes = par_changes.assign(
        Status=lambda x: (x["New Value"] == x["Old Value"]).astype(str)
    )
    tbl_par_changes["Status"] = tbl_par_changes["Status"].map(
        {"False": "Modified", "True": "Unchanged"}
    )
    tbl_par_changes.loc[tbl_par_changes["Status"] == "Unchanged", ["New Value", "Old Value"]] = (
        tbl_par_changes.loc[
            tbl_par_changes["Status"] == "Unchanged", ["New Value", "Old Value"]
        ].replace(regex=".*", value="")
    )

    tag_list: dict[str, pd.DataFrame | None] = {"Test": None, "Feed": None}
    tabulate([test_feed, feed], tag_list, "Tag", 0)
    assert tag_list["Test"] is not None and tag_list["Feed"] is not None
    tag_list["Test"] = tag_list["Test"][["Tag", "Header"]].dropna()
    tag_list["Feed"] = tag_list["Feed"][["Tag", "Header"]].dropna()

    tag_sym_diff = set(tag_list["Test"]["Tag"]).symmetric_difference(
        set(tag_list["Feed"]["Tag"])
    )
    header_sym_diff = set(tag_list["Test"]["Header"]).symmetric_difference(
        set(tag_list["Feed"]["Header"])
    )

    tbl_tag_header = pd.DataFrame(
        {
            "Fields": ["Column Definition - Tag", "Column Definition - Header"],
            "Status": [
                "Modified" if len(tag_sym_diff) > 0 else "Unchanged",
                "Modified" if len(header_sym_diff) > 0 else "Unchanged",
            ],
            "Old Value": [
                ", ".join(tag_list["Feed"]["Tag"]),
                ", ".join(tag_list["Feed"]["Header"]),
            ],
            "New Value": [
                ", ".join(tag_list["Test"]["Tag"]),
                ", ".join(tag_list["Test"]["Header"]),
            ],
        }
    )
    tbl_tag_header.loc[
        tbl_tag_header["Status"] == "Unchanged", ["Old Value", "New Value"]
    ] = ""

    tbl_first_apl = (
        pd.concat([tbl_par_changes, tbl_tag_header])[["Fields", "Status", "Old Value", "New Value"]]
        .where(lambda x: x["Status"] != "Unchanged")
        .dropna()
    )
    result.tbl_first_apl = tbl_first_apl

    rescod_comparison = (
        sc_list["Test"]
        .merge(
            sc_list["Feed"],
            on="Conditional Value",
            how="outer",
            suffixes=("_test", "_feed"),
        )
        .fillna("")
        .assign(Comparison=lambda x: x["New Value_test"] == x["New Value_feed"])
    )

    rescod_new = set(sc_list["Test"]["Conditional Value"])
    rescod_old = set(sc_list["Feed"]["Conditional Value"])
    rescod_additions = rescod_new.difference(rescod_old)
    rescod_deletions = rescod_old.difference(rescod_new)

    rescod_comparison["Status"] = [
        "Added" if val in rescod_additions
        else (
            "Removed"
            if val in rescod_deletions
            else ("Unchanged" if com else "Modified")
        )
        for val, com in zip(
            rescod_comparison["Conditional Value"], rescod_comparison["Comparison"]
        )
    ]
    rescod_comparison.set_index("Status", inplace=True)
    rescod_comparison.loc["Unchanged", "New Value_test"] = ""
    rescod_comparison.loc["Unchanged", "New Value_feed"] = ""

    tbl_second_apl_smry = (
        rescod_comparison.reset_index()[
            ["Conditional Value", "Status", "New Value_test", "New Value_feed"]
        ]
        .rename(columns={"New Value_test": "New Value", "New Value_feed": "Old Value"})
        .assign(Status=lambda x: x["Status"].astype(STATUS_FACTOR))
        .sort_values(by="Status")
        .assign(Status=lambda x: x["Status"].astype(str))
        .where(lambda x: x["Status"] != "Unchanged")
        .dropna()
    )
    result.tbl_second_apl_smry = tbl_second_apl_smry
