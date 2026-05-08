"""
Postprocess for one OpenFAST runaway case
Checks whether the pitch runaway maneuver worked correctly.
"""

import os
import re
import numpy as np
import matplotlib.pyplot as plt
from pyFAST.input_output import FASTOutputFile


def extract_uref_from_filename(outb_file):
    """
    Extract wind speed U from filename like:
    output_U13.0_Seed1_Yaw+10_Inc+8_RunawayB1.outb
    """
    base = os.path.basename(outb_file)
    m = re.search(r"_U([0-9]+(?:\.[0-9]+)?)_", base)
    if m is None:
        raise ValueError(f"Could not extract URef from filename: {base}")
    return float(m.group(1))


def load_ss_reference(this_dir, uref):
    """
    Load steady-state result file corresponding to the same wind speed.
    """
    ss_output_dir = os.path.join(this_dir, "PowerCurve_und_SS_Results")
    ss_output_filename = f"output_U{uref:.1f}.outb"
    ss_output_path = os.path.join(ss_output_dir, ss_output_filename)

    if not os.path.exists(ss_output_path):
        raise FileNotFoundError(f"SS file not found: {ss_output_path}")

    ss_df = FASTOutputFile(ss_output_path).toDataFrame()

    if "RotSpeed_[rpm]" not in ss_df.columns:
        raise KeyError("Column 'RotSpeed_[rpm]' not found in SS output file.")

    t_ss = ss_df["Time_[s]"].values
    rot_ss = ss_df["RotSpeed_[rpm]"].values

    n = len(t_ss)
    last_n = max(1, int(0.05 * n))
    mean_rot_speed_ss = np.mean(rot_ss[-last_n:])

    return mean_rot_speed_ss


def first_index_after(mask):
    idx = np.where(mask)[0]
    return idx[0] if len(idx) > 0 else None


def analyze_runaway_case(
    outb_file,
    fault_time=100.0,
    runaway_blade=1,
    fine_pitch_deg=0.0,
    expected_runaway_rate=10.0,
    rate_tol=0.35,
    pitch_tol_deg=0.1,
    speed_check_window=10.0,
    target_band_deg=0.01,
    make_plots=True,
):
    """
    Analyze one OpenFAST output file and check whether runaway worked.

    Parameters
    ----------
    outb_file : str
        Path to OpenFAST .outb result file
    fault_time : float
        Time when runaway starts [s]
    runaway_blade : int
        Blade number with runaway (1, 2, or 3)
    fine_pitch_deg : float
        Target fine pitch angle [deg]
    expected_runaway_rate : float
        Expected pitch rate magnitude [deg/s]
    rate_tol : float
        Relative tolerance for pitch rate check
    pitch_tol_deg : float
        Tolerance for reaching fine pitch [deg]
    speed_check_window : float
        Time window after fault for speed increase check [s]
    target_band_deg : float
        Band around fine pitch used to detect when target is reached [deg]
    make_plots : bool
        If True, show plots
    """

    if not os.path.exists(outb_file):
        raise FileNotFoundError(f"File not found: {outb_file}")

    this_dir = os.path.dirname(os.path.abspath(__file__))
    uref = extract_uref_from_filename(outb_file)
    mean_rot_speed_ss = load_ss_reference(this_dir, uref)

    df = FASTOutputFile(outb_file).toDataFrame()

    required_cols = ["Time_[s]", "BldPitch1_[deg]"]
    for col in required_cols:
        if col not in df.columns:
            raise KeyError(f"Required column not found: {col}")

    t = df["Time_[s]"].values
    b1 = df["BldPitch1_[deg]"].values
    b2 = df["BldPitch2_[deg]"].values if "BldPitch2_[deg]" in df.columns else None
    b3 = df["BldPitch3_[deg]"].values if "BldPitch3_[deg]" in df.columns else None
    rot_speed = df["RotSpeed_[rpm]"].values if "RotSpeed_[rpm]" in df.columns else None
    gen_speed = df["GenSpeed_[rpm]"].values if "GenSpeed_[rpm]" in df.columns else None

    blade_pitch_map = {1: b1, 2: b2, 3: b3}
    pitch = blade_pitch_map.get(runaway_blade)

    if pitch is None:
        raise ValueError(f"No pitch signal found for blade {runaway_blade}")

    pre_mask = (t >= max(t[0], fault_time - 5.0)) & (t < fault_time)
    post_mask = (t >= fault_time) & (t <= min(t[-1], fault_time + speed_check_window))

    if np.sum(pre_mask) < 3:
        raise ValueError("Not enough pre-fault data to evaluate.")
    if np.sum(post_mask) < 3:
        raise ValueError("Not enough post-fault data to evaluate.")

    pitch_before = np.mean(pitch[pre_mask])
    pitch_final = np.mean(pitch[-max(5, int(0.02 * len(pitch))):])

    pitch_rate = np.gradient(pitch, t)

    start_idx = np.argmin(np.abs(t - fault_time))

    # Start of real motion: first point after fault where pitch changed noticeably
    motion_threshold_deg = 0.2
    move_start_idx = first_index_after(
        (np.arange(len(t)) >= start_idx) & (np.abs(pitch - pitch_before) > motion_threshold_deg)
    )
    if move_start_idx is None:
        move_start_idx = start_idx

    # End of motion: first point after start where pitch reaches fine pitch band
    reach_target_idx = first_index_after(
        (np.arange(len(t)) > move_start_idx) & (np.abs(pitch - fine_pitch_deg) <= target_band_deg)
    )

    if reach_target_idx is None:
        # fallback: use first point where rate becomes very small after motion started
        low_rate_idx = first_index_after(
            (np.arange(len(t)) > move_start_idx) & (np.abs(pitch_rate) < 0.05)
        )
        end_idx = low_rate_idx if low_rate_idx is not None else min(move_start_idx + 1, len(t) - 1)
    else:
        end_idx = reach_target_idx

    t_move_start = t[move_start_idx]
    t_move_end = t[end_idx]

    dt = t_move_end - t_move_start
    dp = pitch[move_start_idx] - pitch[end_idx]

    mean_rate = dp / dt if dt > 0 else 0.0
    peak_rate = np.max(np.abs(pitch_rate[move_start_idx:end_idx + 1])) if end_idx > move_start_idx else 0.0

    results = {}

    results["pitch_started_after_fault"] = t_move_start >= fault_time - 0.05
    results["pitch_moved_to_fine"] = pitch_final < pitch_before - 1.0
    results["pitch_reached_target"] = abs(pitch_final - fine_pitch_deg) <= pitch_tol_deg

    lower = expected_runaway_rate * (1.0 - rate_tol)
    upper = expected_runaway_rate * (1.0 + rate_tol)
    results["pitch_rate_ok"] = lower <= abs(mean_rate) <= upper

    if rot_speed is not None:
        rot_before = np.mean(rot_speed[pre_mask])
        rot_after = np.max(rot_speed[post_mask])
        results["rot_speed_increase"] = rot_after > rot_before + 0.5
    else:
        rot_before = None
        rot_after = None
        results["rot_speed_increase"] = None

    if gen_speed is not None:
        gen_before = np.mean(gen_speed[pre_mask])
        gen_after = np.max(gen_speed[post_mask])
        results["gen_speed_increase"] = gen_after > gen_before + 1.0
    else:
        gen_before = None
        gen_after = None
        results["gen_speed_increase"] = None

    essential_checks = [
        results["pitch_started_after_fault"],
        results["pitch_moved_to_fine"],
        results["pitch_reached_target"],
        results["pitch_rate_ok"],
    ]
    results["overall_pass"] = all(essential_checks)

    print("\n" + "=" * 72)
    print(f"Runaway postprocess for:\n{outb_file}")
    print("=" * 72)
    print(f"URef from filename            : {uref:.1f} m/s")
    print(f"Fault time                    : {fault_time:.3f} s")
    print(f"Detected motion start         : {t_move_start:.3f} s")
    print(f"Detected motion end           : {t_move_end:.3f} s")
    print(f"Motion duration               : {dt:.5f} s")
    print(f"Pitch before fault            : {pitch_before:.3f} deg")
    print(f"Pitch at motion start         : {pitch[move_start_idx]:.3f} deg")
    print(f"Pitch at motion end           : {pitch[end_idx]:.3f} deg")
    print(f"Final pitch                   : {pitch_final:.3f} deg")
    print(f"Target fine pitch             : {fine_pitch_deg:.3f} deg")
    print(f"Mean pitch rate during motion : {mean_rate:.3f} deg/s")
    print(f"Peak abs pitch rate           : {peak_rate:.3f} deg/s")
    print(f"Expected pitch rate           : {expected_runaway_rate:.3f} deg/s")

    if rot_speed is not None:
        print(f"Rotor speed before fault      : {rot_before:.3f} rpm")
        print(f"Max rotor speed after fault   : {rot_after:.3f} rpm")
        print(f"SS reference rotor speed      : {mean_rot_speed_ss:.3f} rpm")

    if gen_speed is not None:
        print(f"Gen speed before fault        : {gen_before:.3f} rpm")
        print(f"Max gen speed after fault     : {gen_after:.3f} rpm")

    print("-" * 72)
    for k, v in results.items():
        print(f"{k:28s}: {v}")
    print("=" * 72 + "\n")

    if make_plots:
        # Plot 1: runaway blade + one healthy blade
        healthy_blade = 2 if runaway_blade != 2 else 3
        healthy_pitch = blade_pitch_map[healthy_blade]

        plt.figure(figsize=(10, 5))
        plt.plot(t, pitch, label=f'Runaway blade {runaway_blade}')
        if healthy_pitch is not None:
            plt.plot(t, healthy_pitch, label=f'Healthy blade {healthy_blade}')
        plt.axvline(fault_time, linestyle='--', label='Fault time')
        plt.axvline(t_move_start, linestyle=':', label='Motion start')
        plt.axvline(t_move_end, linestyle=':', label='Motion end')
        plt.axhline(fine_pitch_deg, linestyle=':', label='Fine pitch target')
        plt.xlabel('Time [s]')
        plt.ylabel('Blade pitch [deg]')
        plt.title('Runaway blade')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
        
        plt.figure(figsize=(10, 5))
        plt.plot(t, pitch_rate, label=f"d(BldPitch{runaway_blade})/dt")
        plt.axvline(fault_time, linestyle="--", label="Fault time")
        plt.axvline(t_move_start, linestyle=":", label="Motion start")
        plt.axvline(t_move_end, linestyle=":", label="Motion end")
        plt.axhline(expected_runaway_rate, linestyle=":", label="Expected +rate")
        plt.axhline(-expected_runaway_rate, linestyle=":", label="Expected -rate")
        plt.xlabel("Time [s]")
        plt.ylabel("Pitch rate [deg/s]")
        plt.title(f"Pitch rate of runaway blade {runaway_blade}")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        plt.figure(figsize=(10, 6))

        plt.subplot(2, 1, 1)
        if rot_speed is not None:
            plt.plot(t, rot_speed, label="RotSpeed [rpm]")
            plt.axhline(mean_rot_speed_ss, linestyle=":", label="SS reference speed")
        plt.axvline(fault_time, linestyle="--", label="Fault")
        plt.ylabel("RotSpeed [rpm]")
        plt.legend()
        plt.grid(True)

        plt.subplot(2, 1, 2)
        if gen_speed is not None:
            plt.plot(t, gen_speed, label="GenSpeed [rpm]")
        plt.axvline(fault_time, linestyle="--")
        plt.xlabel("Time [s]")
        plt.ylabel("GenSpeed [rpm]")
        plt.legend()
        plt.grid(True)

        plt.tight_layout()
        plt.show()

    return results


if __name__ == "__main__":
    this_dir = os.path.dirname(os.path.abspath(__file__))

    outb_file = os.path.join(
        this_dir,
        "DLC2p4_Runaway_OF_results",
        "output_U13.0_Seed1_Yaw+10_Inc+8_RunawayB1.outb",
    )

    analyze_runaway_case(
        outb_file=outb_file,
        fault_time=100.0,
        runaway_blade=1,
        fine_pitch_deg=0.0,
        expected_runaway_rate=10.0,
        rate_tol=0.35,
        pitch_tol_deg=0.1,
        speed_check_window=10.0,
        target_band_deg=0.01,
        make_plots=True,
    )