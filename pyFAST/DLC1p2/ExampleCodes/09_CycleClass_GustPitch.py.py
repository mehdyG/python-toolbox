# -*- coding: utf-8 -*-
"""
Cycle classification (start): Gust vs Pitch events
- Reads OpenFAST .outb
- Detects major events in a load time series (tower or blade moment)
- Uses pitch_rate + dM/dt to label events as:
    - "pitch"
    - "gust"
    - "other"

Output:
- Event table (U, seed, time, range_est, peak_dMdt, peak_pitchrate, label)
- Summary per wind speed: how many gust/pitch events + their damage proxy share
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyFAST.input_output import FASTOutputFile

# =========================
# USER SETTINGS
# =========================
RESULTS_DIR = r"/home/Mehdy/python-toolbox/pyFAST/DLC1p2/DLC1p2_OF_results"
URefs = np.arange(3, 26, 2)
seeds = [1, 2, 3, 4, 5, 6]

TIME_CH = "Time_[s]"
# Choose ONE signal to classify events on (start with Tower base):
LOAD_CH = "TwrBsMyt_[kN-m]"         # or "RootMyb1_[kN-m]"

# Pitch channels (choose what exists in your outputs):
# Often: "BldPitch1_[deg]" (and 2/3), or "Pitch_[deg]" depending on output list.
PITCH_CH = "BldPitch1_[deg]"        # if not found, change to your actual pitch angle channel

# transient cut
t_start = 30.0

# Event detection tuning
# We detect "major peaks/valleys" using a threshold on absolute load.
EVENT_STD_MULT = 3.0    # event if |M| > mean + EVENT_STD_MULT*std

# Classification thresholds
# Gust: high |dM/dt| but little pitch motion
DM_DT_GUST = 300.0      # [kN-m/s] threshold (tune!)
PITCHRATE_SMALL = 0.2   # [deg/s]    "no pitch action"

# Pitch event: pitch_rate spike
PITCHRATE_PITCH = 1.0   # [deg/s] threshold (tune!)

# For “damage proxy” we use range_est^m (not full rainflow yet)
m_damage_proxy = 4.0    # use 4 for tower, 10 for blade if LOAD_CH is blade

# Window for estimating range around event peak (seconds)
WIN = 2.0  # +/- seconds

# --- Demo / inspection settings ---
DEMO_U = 15.0
DEMO_SEED = 1

# show detailed plots for the TOP event of each label (gust/pitch) at DEMO_U/DEMO_SEED
SHOW_DEMO = True


# =========================
# HELPERS
# =========================
def central_diff(y, t):
    """dy/dt with simple central differences."""
    y = np.asarray(y, float)
    t = np.asarray(t, float)
    dydt = np.zeros_like(y)
    dt = np.diff(t)
    dydt[1:-1] = (y[2:] - y[:-2]) / (t[2:] - t[:-2])
    dydt[0] = (y[1] - y[0]) / (t[1] - t[0])
    dydt[-1] = (y[-1] - y[-2]) / (t[-1] - t[-2])
    return dydt

def find_event_indices(signal, thr):
    """
    Return indices where |signal| exceeds thr, but keep only isolated maxima
    (simple peak picking).
    """
    s = np.asarray(signal)
    idx = np.where(np.abs(s) > thr)[0]
    if len(idx) == 0:
        return []

    # Group consecutive indices and pick the max-|s| point in each group
    groups = []
    start = idx[0]
    prev = idx[0]
    for i in idx[1:]:
        if i == prev + 1:
            prev = i
        else:
            groups.append((start, prev))
            start = i
            prev = i
    groups.append((start, prev))

    peaks = []
    for a, b in groups:
        j = a + np.argmax(np.abs(s[a:b+1]))
        peaks.append(j)
    return peaks

def classify_event(dMdt_peak, pitchrate_peak):
    """
    Classification rules:
    - pitch if pitch_rate large
    - gust if dM/dt large AND pitch_rate small
    - else other
    """
    if abs(pitchrate_peak) >= PITCHRATE_PITCH:
        return "pitch"
    if abs(dMdt_peak) >= DM_DT_GUST and abs(pitchrate_peak) <= PITCHRATE_SMALL:
        return "gust"
    return "other"

def range_estimate(time, signal, idx_peak, win_s):
    """Estimate local range in a +/- window around idx_peak."""
    t0 = time[idx_peak]
    mask = (time >= t0 - win_s) & (time <= t0 + win_s)
    seg = signal[mask]
    if len(seg) < 5:
        return np.nan
    return float(np.max(seg) - np.min(seg))

# =========================
# MAIN
# =========================
def main():
    events = []

    demo_time = None
    demo_load = None
    demo_pitch = None
    demo_dMdt = None
    demo_pitchrate = None
    demo_event_rows = []   # store events only for DEMO_U/DEMO_SEED

    for U in URefs:
        for seed in seeds:
            fn = os.path.join(RESULTS_DIR, f"output_U{U:.1f}_Seed{seed}.outb")
            if not os.path.exists(fn):
                continue

            df = FASTOutputFile(fn).toDataFrame()

            # Channel check
            for ch in [TIME_CH, LOAD_CH, PITCH_CH]:
                if ch not in df.columns:
                    raise RuntimeError(
                        f"\nChannel '{ch}' not found in {os.path.basename(fn)}.\n"
                        f"Fix TIME_CH / LOAD_CH / PITCH_CH.\n"
                        f"Tip: open one file and run print(df.columns)."
                    )

            time = df[TIME_CH].values
            mask = time >= t_start
            time = time[mask]

            load = df[LOAD_CH].values[mask]
            pitch = df[PITCH_CH].values[mask]

            # Remove mean from load (focus on fluctuations)
            load = load - np.mean(load)

            # Derivatives
            dMdt = central_diff(load, time)           # kN-m/s
            pitch_rate = central_diff(pitch, time)    # deg/s

            # Save the full signals for demo case
            if SHOW_DEMO and abs(U - DEMO_U) < 1e-9 and seed == DEMO_SEED:
                demo_time = time.copy()
                demo_load = load.copy()
                demo_pitch = pitch.copy()
                demo_dMdt = dMdt.copy()
                demo_pitchrate = pitch_rate.copy()

            # Event threshold based on std
            thr = np.mean(np.abs(load)) + EVENT_STD_MULT * np.std(load)
            peak_idx = find_event_indices(load, thr)

            for idxp in peak_idx:
                dMdt_p = float(dMdt[idxp])
                pr_p = float(pitch_rate[idxp])
                label = classify_event(dMdt_p, pr_p)

                rng = range_estimate(time, load, idxp, WIN)  # local range estimate
                dmg_proxy = (rng ** m_damage_proxy) if np.isfinite(rng) else np.nan

                events.append({
                    "U": U,
                    "seed": seed,
                    "t_peak_s": float(time[idxp]),
                    "load_peak": float(load[idxp]),
                    "dMdt_peak": dMdt_p,
                    "pitch_rate_peak": pr_p,
                    "range_est": rng,
                    "damage_proxy": dmg_proxy,
                    "label": label,
                })

                if SHOW_DEMO and abs(U - DEMO_U) < 1e-9 and seed == DEMO_SEED:
                    demo_event_rows.append(events[-1])


    dfE = pd.DataFrame(events)
    if dfE.empty:
        print("No events found. Try lowering EVENT_STD_MULT or check channels.")
        return

    # Print top events by damage_proxy
    print("\n===== Top events (by damage proxy) =====")
    print(dfE.sort_values("damage_proxy", ascending=False).head(20).to_string(index=False))

    # Summary per wind speed
    grp = dfE.groupby(["U", "label"]).agg(
        n_events=("label", "count"),
        dmg_sum=("damage_proxy", "sum")
    ).reset_index()

    # Compute shares within each U
    grp["dmg_share_in_U_%"] = grp.groupby("U")["dmg_sum"].transform(
        lambda x: 100.0 * x / np.nansum(x) if np.nansum(x) > 0 else 0.0
    )

    print("\n===== Summary per wind speed (counts + damage-proxy shares) =====")
    print(grp.sort_values(["U", "label"]).to_string(index=False))

    # Plot: for each U, show damage proxy share by label (gust/pitch/other)
    labels = ["gust", "pitch", "other"]
    Uvals = np.sort(dfE["U"].unique())

    shares = {lab: [] for lab in labels}
    for U in Uvals:
        sub = grp[grp["U"] == U]
        tot = np.nansum(sub["dmg_sum"].values)
        for lab in labels:
            v = sub[sub["label"] == lab]["dmg_sum"].values
            shares[lab].append(100.0 * v[0] / tot if (len(v) == 1 and tot > 0) else 0.0)

    # Stacked bar plot
    plt.figure()
    bottom = np.zeros(len(Uvals))
    for lab in labels:
        plt.bar(Uvals, shares[lab], bottom=bottom, label=lab)
        bottom += np.array(shares[lab])

    plt.xlabel("Wind speed U [m/s]")
    plt.ylabel("Damage-proxy share within U [%]")
    plt.title(f"Event classification shares (based on {LOAD_CH})")
    plt.legend()
    plt.tight_layout()

        # ---------------------------------------------------------
    # DEMO: show how events are classified at one wind speed
    # ---------------------------------------------------------
    if SHOW_DEMO and demo_time is not None and len(demo_event_rows) > 0:
        df_demo = pd.DataFrame(demo_event_rows).sort_values("damage_proxy", ascending=False)

        print(f"\n===== DEMO events for U={DEMO_U} m/s, Seed={DEMO_SEED} (top by damage_proxy) =====")
        print(df_demo[["t_peak_s", "label", "range_est", "dMdt_peak", "pitch_rate_peak", "damage_proxy"]].head(15).to_string(index=False))

        # ---- Plot A: Full time series with event markers ----
        plt.figure()
        plt.plot(demo_time, demo_load, label=f"Load: {LOAD_CH}")
        for lab in ["gust", "pitch", "other"]:
            sub = df_demo[df_demo["label"] == lab].head(20)  # avoid too many markers
            plt.scatter(sub["t_peak_s"], sub["load_peak"], label=f"{lab} events", s=20)
        plt.xlabel("Time [s]")
        plt.ylabel("Load (mean removed)")
        plt.title(f"Events on load time series (U={DEMO_U}, Seed={DEMO_SEED})")
        plt.legend()
        plt.tight_layout()

        # ---- Plot B: Pitch angle and pitch rate ----
        plt.figure()
        plt.plot(demo_time, demo_pitch, label=f"Pitch angle: {PITCH_CH}")
        plt.xlabel("Time [s]")
        plt.ylabel("Pitch [deg]")
        plt.title(f"Pitch angle (U={DEMO_U}, Seed={DEMO_SEED})")
        plt.tight_layout()

        plt.figure()
        plt.plot(demo_time, demo_pitchrate, label="Pitch rate [deg/s]")
        # mark event times
        plt.scatter(df_demo["t_peak_s"], df_demo["pitch_rate_peak"], s=15, label="event pitch_rate")
        plt.xlabel("Time [s]")
        plt.ylabel("Pitch rate [deg/s]")
        plt.title(f"Pitch rate with event markers (U={DEMO_U}, Seed={DEMO_SEED})")
        plt.legend()
        plt.tight_layout()

        # ---- Plot C: Detailed window around top gust and top pitch event ----
        def _inspect_one_event(row, title):
            t0 = float(row["t_peak_s"])
            idx0 = int(np.argmin(np.abs(demo_time - t0)))

            # window mask
            maskw = (demo_time >= t0 - WIN) & (demo_time <= t0 + WIN)
            tw = demo_time[maskw]
            Mw = demo_load[maskw]
            dMw = demo_dMdt[maskw]
            prw = demo_pitchrate[maskw]

            # estimate "event frequency" using nearest local valley around the peak
            # (simple and intuitive: find min in window and compute dt between peak and min)
            j_peak_local = int(np.argmax(np.abs(Mw)))
            t_peak_local = tw[j_peak_local]
            # valley defined as opposite extreme
            if Mw[j_peak_local] >= 0:
                j_val = int(np.argmin(Mw))
            else:
                j_val = int(np.argmax(Mw))
            t_val = tw[j_val]
            dt = abs(t_peak_local - t_val)
            f_est = (1.0 / (2.0 * dt)) if dt > 1e-6 else np.nan

            plt.figure(figsize=(9, 5))
            plt.plot(tw, Mw, label="Load (window)")
            plt.axvline(t0, linestyle="--", label="event time")
            plt.xlabel("Time [s]")
            plt.ylabel("Load (mean removed)")
            plt.title(title)
            plt.legend()
            plt.tight_layout()

            print(f"\n--- {title} ---")
            print(f"label = {row['label']}")
            print(f"t_peak = {t0:.3f} s")
            print(f"range_est (±{WIN}s) = {row['range_est']:.3f}")
            print(f"dM/dt at peak = {row['dMdt_peak']:.3f} kN-m/s")
            print(f"pitch_rate at peak = {row['pitch_rate_peak']:.3f} deg/s")
            print(f"estimated local frequency f_est ≈ {f_est:.3f} Hz  (from peak↔valley timing)")

            # also show pitch rate in same window
            plt.figure(figsize=(9, 3.5))
            plt.plot(tw, prw, label="Pitch rate [deg/s]")
            plt.axvline(t0, linestyle="--", label="event time")
            plt.xlabel("Time [s]")
            plt.ylabel("Pitch rate [deg/s]")
            plt.title(title + " – pitch rate")
            plt.legend()
            plt.tight_layout()

        # pick top gust and top pitch
        top_gust = df_demo[df_demo["label"] == "gust"].head(1)
        top_pitch = df_demo[df_demo["label"] == "pitch"].head(1)

        if len(top_gust) == 1:
            _inspect_one_event(top_gust.iloc[0], f"TOP GUST event (U={DEMO_U}, Seed={DEMO_SEED})")

        if len(top_pitch) == 1:
            _inspect_one_event(top_pitch.iloc[0], f"TOP PITCH event (U={DEMO_U}, Seed={DEMO_SEED})")


    plt.show()


if __name__ == "__main__":
    main()
