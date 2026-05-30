from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd


TEXT_DTYPES = {
    "cust_number": "string",
    "business_code": "string",
    "name_customer": "string",
    "cust_payment_terms": "string",
    "cust_payment_terms_grp": "string",
}
DATE_COLS = ["baseline_create_date", "due_in_date", "clear_date"]
LATE_BUSINESS_DAYS = 5
RECENT_HISTORY_WINDOWS = [5, 10, 20]
TIME_DECAY_LAMBDA = 0.8
EXCLUDED_MARKET_MACRO_PREFIXES = ("vix", "hy_spread")
RAW_DROP_COLS = [
    "doc_id",
    "invoice_currency",
    "document type",
    "area_business",
    "isOpen",
    "invoice_id",
    "document_create_date",
    "document_create_date.1",
    "posting_date",
    "total_open_amount",
]


@dataclass(frozen=True)
class PipelinePaths:
    data_dir: Path
    dataset: Path
    macro_quarter: Path
    macro_market: Path
    train_out: Path
    test_out: Path


def default_data_dir() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "data"


def make_paths(data_dir: Path | None = None, output_dir: Path | None = None) -> PipelinePaths:
    data_dir = (data_dir or default_data_dir()).resolve()
    output_dir = (output_dir or data_dir).resolve()
    return PipelinePaths(
        data_dir=data_dir,
        dataset=data_dir / "dataset.csv",
        macro_quarter=data_dir / "macro_variable.csv",
        macro_market=data_dir / "market_macro_monthly.csv",
        train_out=output_dir / "train_eda_fixed.csv",
        test_out=output_dir / "test_eda_fixed.csv",
    )


def load_and_split_raw(dataset_path: Path, train_ratio: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(dataset_path)
    df = raw[raw["isOpen"] == 0].copy()

    df["clear_date"] = pd.to_datetime(df["clear_date"], errors="coerce")
    df["due_in_date"] = pd.to_datetime(
        df["due_in_date"].astype(int).astype(str),
        format="%Y%m%d",
        errors="coerce",
    )
    df["target"] = (df["clear_date"] > df["due_in_date"]).astype(int)

    before_rows = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Removed duplicate rows: {before_rows - len(df):,}")
    print(f"Remaining rows: {len(df):,}")

    df = df.sort_values("baseline_create_date").reset_index(drop=True)
    split_idx = int(len(df) * train_ratio)
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def clean_cust_number(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cust_number_stripped = df["cust_number"].astype(str).str.strip()
    is_9_digit = cust_number_stripped.str.fullmatch(r"\d{9}")
    df["cust_number"] = cust_number_stripped.where(
        ~is_9_digit,
        cust_number_stripped.str.zfill(10),
    )
    return df


def clean_basic_features(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = train.copy()
    test = test.copy()

    for df in [train, test]:
        df["amount_in_usd"] = df.apply(
            lambda row: row["total_open_amount"] * 0.75
            if row["invoice_currency"] == "CAD"
            else row["total_open_amount"],
            axis=1,
        )
        df["amount_in_usd"] = np.log1p(df["amount_in_usd"])

    term_counts = train["cust_payment_terms"].value_counts()
    train["cust_payment_terms_grp"] = train["cust_payment_terms"].where(
        train["cust_payment_terms"].map(term_counts) > 30,
        "Other",
    )
    test["cust_payment_terms_grp"] = test["cust_payment_terms"].where(
        test["cust_payment_terms"].map(term_counts) > 30,
        "Other",
    )

    for df in [train, test]:
        df["baseline_create_date"] = pd.to_datetime(
            df["baseline_create_date"],
            format="%Y%m%d",
            errors="coerce",
        )
        df["baseline_month"] = df["baseline_create_date"].dt.month
        df["baseline_day"] = df["baseline_create_date"].dt.day
        df["baseline_dayofweek"] = df["baseline_create_date"].dt.dayofweek
        df["due_in_date"] = pd.to_datetime(df["due_in_date"], errors="coerce")
        df["Allowed_Pay_Days"] = (df["due_in_date"] - df["baseline_create_date"]).dt.days

    train = clean_cust_number(train)
    test = clean_cust_number(test)

    train = train.drop(columns=RAW_DROP_COLS)
    test = test.drop(columns=RAW_DROP_COLS)
    return train, test


def prepare_invoice_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "target" in df.columns:
        df = df.rename(columns={"target": "target_old"})
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def csv_roundtrip(df: pd.DataFrame) -> pd.DataFrame:
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return pd.read_csv(buffer, dtype=TEXT_DTYPES)


def business_days_between(start_dates, end_dates) -> pd.Series:
    start_dates = pd.to_datetime(start_dates, errors="coerce")
    if not isinstance(end_dates, pd.Series):
        end_dates = pd.Series(end_dates, index=start_dates.index)
    end_dates = pd.to_datetime(end_dates, errors="coerce")

    result = pd.Series(np.nan, index=start_dates.index, dtype="float")
    valid = start_dates.notna() & end_dates.notna()
    if valid.any():
        start_np = start_dates.loc[valid].values.astype("datetime64[D]")
        end_np = end_dates.loc[valid].values.astype("datetime64[D]")
        result.loc[valid] = np.busday_count(start_np, end_np)
    return result


def add_business_days_late(df: pd.DataFrame) -> None:
    df["business_days_late"] = business_days_between(df["due_in_date"], df["clear_date"]).astype(int)


def add_basic_features(train_df: pd.DataFrame, test_df: pd.DataFrame) -> np.ndarray:
    for df in [train_df, test_df]:
        add_business_days_late(df)
        df["target"] = (df["business_days_late"] > LATE_BUSINESS_DAYS).astype(int)
        df["due_weekend_flag"] = df["due_in_date"].dt.weekday.isin([5, 6]).astype(int)

    _, raw_bins = pd.qcut(train_df["amount_in_usd"], q=4, labels=False, retbins=True, duplicates="drop")
    amount_bins = np.r_[-np.inf, raw_bins[1:-1], np.inf]
    amount_labels = list(range(len(amount_bins) - 1))

    for df in [train_df, test_df]:
        df["amount_bin"] = pd.cut(
            df["amount_in_usd"],
            bins=amount_bins,
            labels=amount_labels,
            include_lowest=True,
        ).astype("int64")
    return amount_bins


def add_business_days(start_dates, n_business_days: int) -> pd.Series:
    start_dates = pd.to_datetime(start_dates, errors="coerce")
    result = pd.Series(pd.NaT, index=start_dates.index)
    valid = start_dates.notna()
    if valid.any():
        start_np = start_dates.loc[valid].values.astype("datetime64[D]")
        result.loc[valid] = pd.to_datetime(np.busday_offset(start_np, n_business_days, roll="forward"))
    return result


def known_history_for_date(customer_history: pd.DataFrame, current_date) -> pd.DataFrame:
    prior = customer_history[customer_history["baseline_create_date"] < current_date].copy()
    if prior.empty:
        return prior

    paid_before_current = prior["clear_date"].notna() & (prior["clear_date"] < current_date)
    unpaid_as_of_current = prior["clear_date"].isna() | (prior["clear_date"] >= current_date)
    unpaid_late_days = business_days_between(prior["due_in_date"], current_date)
    known_late_unpaid = unpaid_as_of_current & (unpaid_late_days > LATE_BUSINESS_DAYS)

    known = prior[paid_before_current | known_late_unpaid].copy()
    if known.empty:
        return known

    paid_late_days = business_days_between(known["due_in_date"], known["clear_date"])
    known_late_unpaid = known_late_unpaid.reindex(known.index).fillna(False)

    known["_known_late_target"] = np.where(
        known_late_unpaid,
        1.0,
        known["target"].astype(float),
    )
    known["_known_late"] = np.where(
        known_late_unpaid,
        1.0,
        (paid_late_days > LATE_BUSINESS_DAYS).astype(float),
    )
    known["_days_late_as_of_current"] = np.where(
        known_late_unpaid,
        unpaid_late_days.reindex(known.index),
        paid_late_days,
    )

    known["_known_event_date"] = known["clear_date"]
    known.loc[known_late_unpaid, "_known_event_date"] = add_business_days(
        known.loc[known_late_unpaid, "due_in_date"],
        LATE_BUSINESS_DAYS + 1,
    )
    return known


def weighted_late_rate(known: pd.DataFrame, current_date) -> float:
    event_month = known["_known_event_date"].dt.to_period("M")
    current_month = pd.Period(current_date, freq="M")
    month_gap = np.array([current_month.ordinal - month.ordinal for month in event_month], dtype=float)
    weights = TIME_DECAY_LAMBDA ** month_gap
    return float(np.average(known["_known_late"].astype(float), weights=weights))


def add_customer_history_features(current_df: pd.DataFrame, history_df: pd.DataFrame) -> pd.DataFrame:
    features = [
        "cust_allowed_pay_days_late_rate_past",
        "ratio_paid_invoices_late_past",
        "avg_days_late_paid_late_past",
        "sum_outstanding_amount_past",
        "recent_5_late_rate",
        "recent_10_late_rate",
        "recent_20_late_rate",
        "late_rate_time_decay_lambda_0_8",
    ]
    current_df = current_df.copy()
    current_df[features] = 0.0

    for cust, current_rows_for_customer in current_df.groupby("cust_number", sort=False):
        customer_history = history_df[history_df["cust_number"].eq(cust)]

        for current_date, current_rows in current_rows_for_customer.groupby("baseline_create_date", sort=True):
            known = known_history_for_date(customer_history, current_date)
            if not known.empty:
                rate_by_allowed_days = known.groupby("Allowed_Pay_Days")["_known_late_target"].mean()
                current_df.loc[current_rows.index, "cust_allowed_pay_days_late_rate_past"] = (
                    current_rows["Allowed_Pay_Days"].map(rate_by_allowed_days).fillna(0.0).astype(float)
                )
                current_df.loc[current_rows.index, "ratio_paid_invoices_late_past"] = float(known["_known_late"].mean())

                known_late = known[known["_known_late"].eq(1.0)]
                if not known_late.empty:
                    current_df.loc[current_rows.index, "avg_days_late_paid_late_past"] = float(
                        known_late["_days_late_as_of_current"].mean()
                    )

                known_sorted = known.sort_values(["_known_event_date", "baseline_create_date", "due_in_date", "clear_date"])
                for window in RECENT_HISTORY_WINDOWS:
                    current_df.loc[current_rows.index, f"recent_{window}_late_rate"] = float(
                        known_sorted.tail(window)["_known_late"].mean()
                    )
                current_df.loc[current_rows.index, "late_rate_time_decay_lambda_0_8"] = weighted_late_rate(
                    known_sorted,
                    current_date,
                )

            outstanding = customer_history[
                (customer_history["baseline_create_date"] < current_date)
                & (customer_history["clear_date"].isna() | (customer_history["clear_date"] >= current_date))
            ]
            current_df.loc[current_rows.index, "sum_outstanding_amount_past"] = max(
                float(outstanding["amount_in_usd"].sum()),
                0.0,
            )

    return current_df


def first_transaction_late_rate(train_df: pd.DataFrame) -> float:
    train_sorted = train_df.sort_values(["cust_number", "baseline_create_date", "due_in_date", "clear_date"])
    first_rows = train_sorted.groupby("cust_number", sort=False).head(1)
    return float(first_rows["target"].mean())


def add_cleared_customer_features(
    current_df: pd.DataFrame,
    history_df: pd.DataFrame,
    baseline_late_rate: float,
) -> pd.DataFrame:
    features = [
        "current_transaction_count",
        "cleared_count",
        "is_new_customer",
        "is_last_late",
        "recent_3_late_rate",
    ]
    current_df = current_df.copy()
    current_df[features] = 0.0

    for cust, current_rows_for_customer in current_df.groupby("cust_number", sort=False):
        customer_history = history_df[history_df["cust_number"].eq(cust)].copy()

        for current_date, current_rows in current_rows_for_customer.groupby("baseline_create_date", sort=True):
            prior_issued = customer_history[customer_history["baseline_create_date"] < current_date]
            current_df.loc[current_rows.index, "current_transaction_count"] = np.arange(
                len(prior_issued) + 1,
                len(prior_issued) + len(current_rows) + 1,
            )

            prior_cleared = customer_history[
                customer_history["clear_date"].notna() & (customer_history["clear_date"] < current_date)
            ].sort_values(["clear_date", "baseline_create_date", "due_in_date"])

            cleared_count = len(prior_cleared)
            current_df.loc[current_rows.index, "cleared_count"] = cleared_count
            current_df.loc[current_rows.index, "is_new_customer"] = int(cleared_count < 3)

            if prior_cleared.empty:
                current_df.loc[current_rows.index, "is_last_late"] = baseline_late_rate
                current_df.loc[current_rows.index, "recent_3_late_rate"] = baseline_late_rate
            else:
                current_df.loc[current_rows.index, "is_last_late"] = float(prior_cleared["target"].iloc[-1])
                current_df.loc[current_rows.index, "recent_3_late_rate"] = float(prior_cleared["target"].tail(3).mean())

    current_df["current_transaction_count"] = current_df["current_transaction_count"].astype(int)
    current_df["cleared_count"] = current_df["cleared_count"].astype(int)
    current_df["is_new_customer"] = current_df["is_new_customer"].astype(int)
    return current_df


def add_market_macro_features(train_df: pd.DataFrame, test_df: pd.DataFrame, macro_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    macro = pd.read_csv(macro_path)
    excluded_market_cols = [
        col for col in macro.columns if col.startswith(EXCLUDED_MARKET_MACRO_PREFIXES)
    ]
    macro = macro.drop(columns=excluded_market_cols)
    market_cols = [col for col in macro.columns if col != "year_month"]
    drop_cols = ["year_month", *market_cols, *excluded_market_cols]

    result = []
    for df in [train_df, test_df]:
        featured = df.drop(columns=[col for col in drop_cols if col in df.columns]).copy()
        featured["year_month"] = featured["baseline_create_date"].dt.to_period("M").astype(str)
        featured = featured.merge(macro, on="year_month", how="left")
        result.append(featured)
    return result[0], result[1]


def add_quarterly_macro_features(train_df: pd.DataFrame, test_df: pd.DataFrame, macro_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    macro = pd.read_csv(macro_path)
    macro["year_quarter"] = macro["year_quarter"].astype(str)
    quarter_cols = [col for col in macro.columns if col not in ["quarter_end_date"]]

    result = []
    for df in [train_df, test_df]:
        featured = df.drop(columns=[col for col in quarter_cols if col in df.columns]).copy()
        featured["year_quarter"] = featured["baseline_create_date"].dt.to_period("Q").astype(str)
        featured = featured.merge(macro[quarter_cols], on="year_quarter", how="left")
        result.append(featured)
    return result[0], result[1]


def add_feature_engineering(
    train: pd.DataFrame,
    test: pd.DataFrame,
    macro_market_path: Path,
    macro_quarter_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_eda = prepare_invoice_data(train)
    test_eda = prepare_invoice_data(test)

    add_basic_features(train_eda, test_eda)

    train_eda = add_customer_history_features(train_eda, train_eda)
    test_eda = add_customer_history_features(test_eda, train_eda.copy())

    new_customer_baseline = first_transaction_late_rate(train_eda)
    train_eda = add_cleared_customer_features(train_eda, train_eda, new_customer_baseline)
    test_eda = add_cleared_customer_features(test_eda, train_eda.copy(), new_customer_baseline)

    train_eda, test_eda = add_market_macro_features(train_eda, test_eda, macro_market_path)
    train_eda, test_eda = add_quarterly_macro_features(train_eda, test_eda, macro_quarter_path)
    return train_eda, test_eda


def build_fixed_datasets(paths: PipelinePaths) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_raw, test_raw = load_and_split_raw(paths.dataset)
    train_clean, test_clean = clean_basic_features(train_raw, test_raw)
    train_clean = csv_roundtrip(train_clean)
    test_clean = csv_roundtrip(test_clean)
    return add_feature_engineering(
        train_clean,
        test_clean,
        macro_market_path=paths.macro_market,
        macro_quarter_path=paths.macro_quarter,
    )


def write_fixed_datasets(paths: PipelinePaths) -> tuple[pd.DataFrame, pd.DataFrame]:
    paths.train_out.parent.mkdir(parents=True, exist_ok=True)
    paths.test_out.parent.mkdir(parents=True, exist_ok=True)
    train_fixed, test_fixed = build_fixed_datasets(paths)
    train_fixed.to_csv(paths.train_out, index=False)
    test_fixed.to_csv(paths.test_out, index=False)
    print(f"Saved train: {paths.train_out} rows={len(train_fixed):,}, cols={len(train_fixed.columns)}")
    print(f"Saved test : {paths.test_out} rows={len(test_fixed):,}, cols={len(test_fixed.columns)}")
    return train_fixed, test_fixed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixed invoice modeling datasets.")
    parser.add_argument("--data-dir", type=Path, default=None, help="Directory containing dataset and macro CSV files.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for final fixed CSV outputs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = make_paths(data_dir=args.data_dir, output_dir=args.output_dir)
    write_fixed_datasets(paths)


if __name__ == "__main__":
    main()
