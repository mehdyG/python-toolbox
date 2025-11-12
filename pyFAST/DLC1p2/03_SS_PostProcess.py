#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vergleicht User-CSV (OpenFAST-Resultate) mit NREL-Referenzdaten (ODS).
Erzeugt drei PNGs:
  - PowerCurve_with_NREL.png
  - GenSpeedCurve_with_NREL.png
  - PitchCurve_with_NREL.png

Beispielaufruf:
  python 03_SS_PostProcess.py \
    --user_csv PowerCurve_und_SS_Results/PowerCurve_und_SS_Results.csv \
    --nrel_pow NREL_Ref_Results/Rotor_Gen_P_Thrust_.ods \
    --nrel_tpt NREL_Ref_Results/TorquePitchTSROmega.ods \
    --nrel_def NREL_Ref_Results/Deflections.ods \
    --outdir ./plots
"""

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt

# WEA Parameter Definition
Gearbox_ratio = 97          # Gearbox Ratio = R_Gen/R_Rotor

# ---- Standard-Spaltennamen (kannst du per CLI überschreiben) ----
USER_COLS_DEFAULT = {
    "ws":  "WindSpeed (m/s)",
    "pow": "MeanPower (kW)",
    "rpm": "MeanGenSpeed (rpm)",
    "pit": "MeanPitch (deg)",
}

NREL_POW_EXPECT = {
    "ws":  "Wind_Speed_Pow",   # wird aus erster Spalte erzeugt
    "pow": "GenPow[kW]",
}

NREL_TPT_EXPECT = {
    "ws":   "Wind_Speed_TPT",  # wird aus erster Spalte erzeugt
    "rpm":  "OmegaR",
    "pit":  "BlPitch",
}

def read_ods_with_firstcol_rename(path: str, first_col_name: str) -> pd.DataFrame:
    df = pd.read_excel(path, engine="odf")
    if df.empty:
        raise ValueError(f"ODS leer: {path}")
    # erste Spalte eindeutig benennen
    df = df.rename(columns={df.columns[0]: first_col_name})
    return df

def coerce_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def ensure_columns(df: pd.DataFrame, need, tag):
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"{tag}: folgende Spalten fehlen: {missing}")

def load_user_csv(path: str, user_cols: dict) -> pd.DataFrame:
    df = pd.read_csv(path)
    ensure_columns(df, user_cols.values(), "User CSV")
    df = df.sort_values(user_cols["ws"])
    # numerisch
    df = coerce_numeric(df, user_cols.values())
    return df

def load_nrel(pow_path: str, tpt_path: str, def_path: str | None = None):
    df_pow = read_ods_with_firstcol_rename(pow_path, NREL_POW_EXPECT["ws"])
    df_tpt = read_ods_with_firstcol_rename(tpt_path, NREL_TPT_EXPECT["ws"])
    # numerisch
    df_pow = coerce_numeric(df_pow, [NREL_POW_EXPECT["ws"], NREL_POW_EXPECT["pow"]])
    df_tpt = coerce_numeric(df_tpt, [NREL_TPT_EXPECT["ws"], NREL_TPT_EXPECT["rpm"], NREL_TPT_EXPECT["pit"]])
    # sortieren
    df_pow = df_pow.dropna(subset=[NREL_POW_EXPECT["ws"]]).sort_values(NREL_POW_EXPECT["ws"])
    df_tpt = df_tpt.dropna(subset=[NREL_TPT_EXPECT["ws"]]).sort_values(NREL_TPT_EXPECT["ws"])
    return df_pow, df_tpt

def save_plot(figpath: str):
    os.makedirs(os.path.dirname(figpath), exist_ok=True)
    plt.tight_layout()
    plt.savefig(figpath, dpi=150)
    print(f"✅ Saved: {figpath}")

def plot_power(user_df, nrel_pow_df, user_cols, outdir):
    plt.figure(figsize=(8,5))
    if user_df is not None:
        plt.plot(user_df[user_cols["ws"]], user_df[user_cols["pow"]],
                 marker='o', linestyle='-', label='User OpenFAST')
    plt.plot(nrel_pow_df[NREL_POW_EXPECT["ws"]], nrel_pow_df[NREL_POW_EXPECT["pow"]],
             marker='s', linestyle='--', label='NREL 5MW Reference')
    plt.xlabel("Wind Speed (m/s)")
    plt.ylabel("Power Output (kW)")
    plt.title("Power Curve Comparison")
    plt.grid(True)
    plt.legend()
    save_plot(os.path.join(outdir, "PowerCurve_with_NREL.png"))
    plt.show()

def plot_rpm(user_df, nrel_tpt_df, user_cols, outdir):
    need = {NREL_TPT_EXPECT["ws"], NREL_TPT_EXPECT["rpm"]}
    if not need.issubset(nrel_tpt_df.columns):
        print("⚠️  Generator-Speed-Plot übersprungen (Spalten fehlen in NREL TPT).")
        return
    plt.figure(figsize=(8,5))
    if user_df is not None:
        plt.plot(user_df[user_cols["ws"]], user_df[user_cols["rpm"]],
                 marker='o', linestyle='-', label='User OpenFAST')
    plt.plot(nrel_tpt_df[NREL_TPT_EXPECT["ws"]], nrel_tpt_df[NREL_TPT_EXPECT["rpm"]]*Gearbox_ratio,
             marker='s', linestyle='--', label='NREL 5MW Reference')
    plt.xlabel("Wind Speed (m/s)")
    plt.ylabel("Generator Speed (rpm)")
    plt.title("Generator Speed Comparison")
    plt.grid(True)
    plt.legend()
    save_plot(os.path.join(outdir, "GenSpeedCurve_with_NREL.png"))
    plt.show()

def plot_pitch(user_df, nrel_tpt_df, user_cols, outdir):
    need = {NREL_TPT_EXPECT["ws"], NREL_TPT_EXPECT["pit"]}
    if not need.issubset(nrel_tpt_df.columns):
        print("⚠️  Pitch-Plot übersprungen (Spalten fehlen in NREL TPT).")
        return
    plt.figure(figsize=(8,5))
    if user_df is not None:
        plt.plot(user_df[user_cols["ws"]], user_df[user_cols["pit"]],
                 marker='o', linestyle='-', label='User OpenFAST')
    plt.plot(nrel_tpt_df[NREL_TPT_EXPECT["ws"]], nrel_tpt_df[NREL_TPT_EXPECT["pit"]],
             marker='s', linestyle='--', label='NREL 5MW Reference')
    plt.xlabel("Wind Speed (m/s)")
    plt.ylabel("Blade Pitch (deg)")
    plt.title("Blade Pitch Comparison")
    plt.grid(True)
    plt.legend()
    save_plot(os.path.join(outdir, "PitchCurve_with_NREL.png"))
    plt.show()

def main():
    ap = argparse.ArgumentParser(description="Vergleich User-CSV mit NREL-ODS")
    ap.add_argument("--user_csv", type=str, required=True, help="Pfad zur User-CSV (PowerCurve_und_SS_Results.csv)")
    ap.add_argument("--nrel_pow", type=str, required=True, help="ODS mit Power/Thrust (z.B. Rotor_Gen_P_Thrust_.ods)")
    ap.add_argument("--nrel_tpt", type=str, required=True, help="ODS mit Torque/Pitch/TSR (z.B. TorquPitchTSR.ods)")
    ap.add_argument("--nrel_def", type=str, default=None, help="ODS mit Deflections (optional)")
    ap.add_argument("--outdir", type=str, default=".", help="Ausgabeordner für PNGs")

    # Optional: Spalten der User-CSV überschreiben (falls anders benannt)
    ap.add_argument("--user_ws",  type=str, default=USER_COLS_DEFAULT["ws"])
    ap.add_argument("--user_pow", type=str, default=USER_COLS_DEFAULT["pow"])
    ap.add_argument("--user_rpm", type=str, default=USER_COLS_DEFAULT["rpm"])
    ap.add_argument("--user_pit", type=str, default=USER_COLS_DEFAULT["pit"])

    args = ap.parse_args()

    user_cols = {"ws": args.user_ws, "pow": args.user_pow, "rpm": args.user_rpm, "pit": args.user_pit}

    # Laden
    print("📥 Lade User-CSV:", args.user_csv)
    user_df = load_user_csv(args.user_csv, user_cols)

    print("📥 Lade NREL ODS (Power):", args.nrel_pow)
    print("📥 Lade NREL ODS (Torque/Pitch/TSR):", args.nrel_tpt)
    nrel_pow_df, nrel_tpt_df = load_nrel(args.nrel_pow, args.nrel_tpt, args.nrel_def)

    # Kurzer Überblick
    print("\n🔎 User-CSV Spalten:", list(user_df.columns))
    print("🔎 NREL Power Spalten:", list(nrel_pow_df.columns))
    print("🔎 NREL TPT Spalten:", list(nrel_tpt_df.columns), "\n")

    # Plots
    plot_power(user_df, nrel_pow_df, user_cols, args.outdir)
    plot_rpm(user_df, nrel_tpt_df, user_cols, args.outdir)
    plot_pitch(user_df, nrel_tpt_df, user_cols, args.outdir)

    print("\n✨ Fertig.")

if __name__ == "__main__":
    main()
