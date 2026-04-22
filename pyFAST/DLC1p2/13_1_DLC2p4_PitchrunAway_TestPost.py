"""
Postprocess for one OpenFAST runaway case
Checks whether the pitch runaway maneuver worked correctly.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from pyFAST.input_output import FASTOutputFile


def analyze_runaway_case(
    outb_file,
    fault_time=100.0,
    runaway_blade=1,
    fine_pitch_deg=0.0,
    expected_runaway_rate=8.0,
    rate_tol=0.35,
    pitch_tol_deg=1.0,
    speed_check_window=10.0,
    make_plots=True
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
        Blade number with runaway (1,2,3)
    fine_pitch_deg : float
        Target fine pitch angle [deg]
    expected_runaway_rate : float
        Expected pitch rate magnitude [deg/s]
    rate_tol : float
        Relative tolerance for pitch rate check
    pitch_tol_deg : float
        Tolerance for reaching fine pitch
    speed_check_window : float
        Time window after fault for speed increase check [s]
    make_plots : bool
        If True, show plots
    """

    if not os.path.exists(outb_file):
        raise FileNotFoundError(f"File not found: {outb_file}")

    df = FASTOutputFile(outb_file).toDataFrame()

    # -------- column names --------
    t = df['Time_[s]'].values

    b1 = df['BldPitch1_[deg]'].values
    b2 = df['BldPitch2_[deg]'].values if 'BldPitch2_[deg]' in df.columns else None
    b3 = df['BldPitch3_[deg]'].values if 'BldPitch3_[deg]' in df.columns else None

    rot_speed = df['RotSpeed_[rpm]'].values if 'RotSpeed_[rpm]' in df.columns else None
    gen_speed = df['GenSpeed_[rpm]'].values if 'GenSpeed_[rpm]' in df.columns else None

    blade_pitch_map = {
        1: b1,
        2: b2,
        3: b3
    }

    pitch = blade_pitch_map[runaway_blade]
    if pitch is None:
        raise ValueError(f"No pitch signal found for blade {runaway_blade}")

    # -------- basic masks --------
    i_fault = np.argmin(np.abs(t - fault_time))
    t_fault = t[i_fault]

    pre_mask = (t >= max(t[0], fault_time - 5.0)) & (t < fault_time)
    post_mask = (t >= fault_time) & (t <= min(t[-1], fault_time + speed_check_window))

    if np.sum(pre_mask) < 3 or np.sum(post_mask) < 3:
        raise ValueError("Not enough data around fault time to evaluate.")

    # -------- before / after values --------
    pitch_before = np.mean(pitch[pre_mask])

    # compute pitch rate using gradient
    pitch_rate = np.gradient(pitch, t)

    # detect active motion window:
    # when pitch deviates noticeably from pre-fault value
    moving_idx = np.where(np.abs(pitch - pitch_before) > 0.3)[0]

    if len(moving_idx) > 0:
        i_move_start = moving_idx[0]
        i_move_end = moving_idx[-1]
        t_move_start = t[i_move_start]
        t_move_end = t[i_move_end]
        mean_rate = np.mean(np.abs(pitch_rate[i_move_start:i_move_end + 1]))
    else:
        t_move_start = None
        t_move_end = None
        mean_rate = 0.0

    pitch_final = np.mean(pitch[-max(5, int(0.02 * len(pitch))):])

    # -------- checks --------
    results = {}

    # 1) Did pitch start moving after fault?
    results['pitch_started_after_fault'] = (
        t_move_start is not None and t_move_start >= fault_time - 0.5
    )

    # 2) Did pitch go toward fine pitch?
    # For runaway to fine pitch, final pitch should be smaller than pre-fault pitch
    results['pitch_moved_to_fine'] = pitch_final < pitch_before - 1.0

    # 3) Did it roughly reach target?
    results['pitch_reached_target'] = abs(pitch_final - fine_pitch_deg) <= pitch_tol_deg

    # 4) Was pitch rate roughly correct?
    lower = expected_runaway_rate * (1 - rate_tol)
    upper = expected_runaway_rate * (1 + rate_tol)
    results['pitch_rate_ok'] = lower <= mean_rate <= upper

    # 5) Did rotor / generator speed increase after fault?
    if rot_speed is not None:
        rot_before = np.mean(rot_speed[pre_mask])
        rot_after = np.max(rot_speed[post_mask])
        results['rot_speed_increase'] = rot_after > rot_before + 0.5
    else:
        rot_before = None
        rot_after = None
        results['rot_speed_increase'] = None

    if gen_speed is not None:
        gen_before = np.mean(gen_speed[pre_mask])
        gen_after = np.max(gen_speed[post_mask])
        results['gen_speed_increase'] = gen_after > gen_before + 1.0
    else:
        gen_before = None
        gen_after = None
        results['gen_speed_increase'] = None

    # overall assessment
    essential_checks = [
        results['pitch_started_after_fault'],
        results['pitch_moved_to_fine'],
        results['pitch_reached_target'],
        results['pitch_rate_ok']
    ]
    results['overall_pass'] = all(essential_checks)

    # -------- print report --------
    print("\n" + "=" * 70)
    print(f"Runaway postprocess for:\n{outb_file}")
    print("=" * 70)
    print(f"Fault time                    : {fault_time:.2f} s")
    print(f"Detected motion start         : {t_move_start if t_move_start is not None else 'None'}")
    print(f"Detected motion end           : {t_move_end if t_move_end is not None else 'None'}")
    print(f"Pitch before fault            : {pitch_before:.3f} deg")
    print(f"Final pitch                   : {pitch_final:.3f} deg")
    print(f"Target fine pitch             : {fine_pitch_deg:.3f} deg")
    print(f"Mean pitch rate during motion : {mean_rate:.3f} deg/s")
    print(f"Expected pitch rate           : {expected_runaway_rate:.3f} deg/s")

    if rot_speed is not None:
        print(f"Rotor speed before fault      : {rot_before:.3f} rpm")
        print(f"Max rotor speed after fault   : {rot_after:.3f} rpm")

    if gen_speed is not None:
        print(f"Gen speed before fault        : {gen_before:.3f} rpm")
        print(f"Max gen speed after fault     : {gen_after:.3f} rpm")

    print("-" * 70)
    for k, v in results.items():
        print(f"{k:28s}: {v}")
    print("=" * 70 + "\n")

    # -------- plots --------
    if make_plots:
        # Plot 1: blade pitches
        plt.figure(figsize=(10, 5))
        plt.plot(t, b1, label='BldPitch1')
        if b2 is not None:
            plt.plot(t, b2, label='BldPitch2')
        if b3 is not None:
            plt.plot(t, b3, label='BldPitch3')
        plt.axvline(fault_time, linestyle='--', label='Fault time')
        plt.axhline(fine_pitch_deg, linestyle=':', label='Fine pitch target')
        plt.xlabel('Time [s]')
        plt.ylabel('Blade pitch [deg]')
        plt.title('Blade pitch response')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        # Plot 2: runaway blade pitch rate
        plt.figure(figsize=(10, 5))
        plt.plot(t, pitch_rate, label=f'd(BldPitch{runaway_blade})/dt')
        plt.axvline(fault_time, linestyle='--', label='Fault time')
        plt.axhline(expected_runaway_rate, linestyle=':', label='Expected +rate')
        plt.axhline(-expected_runaway_rate, linestyle=':', label='Expected -rate')
        plt.xlabel('Time [s]')
        plt.ylabel('Pitch rate [deg/s]')
        plt.title(f'Pitch rate of runaway blade {runaway_blade}')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        # Plot 3: rotor/gen speed
        plt.figure(figsize=(10, 5))
        if rot_speed is not None:
            plt.plot(t, rot_speed, label='RotSpeed [rpm]')
        if gen_speed is not None:
            plt.plot(t, gen_speed, label='GenSpeed [rpm]')
        plt.axvline(fault_time, linestyle='--', label='Fault time')
        plt.xlabel('Time [s]')
        plt.ylabel('Speed [rpm]')
        plt.title('Rotor / generator speed response')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    return results


if __name__ == "__main__":
    # Example
    this_dir = os.path.dirname(os.path.abspath(__file__))

    outb_file = os.path.join(
        this_dir,
        'DLC2p4_Runaway_OF_results',
        'output_U13.0_Seed1_Yaw+10_Inc+8_RunawayB1.outb'
    )

    analyze_runaway_case(
        outb_file=outb_file,
        fault_time=100.0,
        runaway_blade=1,
        fine_pitch_deg=0.0,
        expected_runaway_rate=8.0,
        rate_tol=0.35,
        pitch_tol_deg=1.0,
        speed_check_window=10.0,
        make_plots=True
    )