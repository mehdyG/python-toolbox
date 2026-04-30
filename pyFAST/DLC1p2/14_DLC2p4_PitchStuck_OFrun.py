"""
Run OpenFAST for DLC 2.4 / Pitch stuck fault
Prepared for all cases, but currently runs only one test case:
U = 13 m/s, Seed = 1, Yaw = 0 deg, Inclination = 0 deg
"""

import os
import shutil
import numpy as np
from pyFAST.input_output import FASTInputFile, FASTOutputFile
from rosco.toolbox.utilities import run_openfast


def safe_mkdir(path):
    os.makedirs(path, exist_ok=True)


def get_ss_means(ss_output_path):
    SS_out = FASTOutputFile(ss_output_path).toDataFrame()

    time = SS_out['Time_[s]']
    pitch = SS_out['BldPitch1_[deg]']
    OoPDefl = SS_out['OoPDefl1_[m]']
    IPDefl = SS_out['IPDefl1_[m]']
    Rot_speed = SS_out['RotSpeed_[rpm]']

    N = len(time)
    last_n = max(1, int(0.05 * N))

    return {
        'mean_pitch': np.mean(pitch[-last_n:]),
        'mean_OoPDefl': np.mean(OoPDefl[-last_n:]),
        'mean_IPDefl': np.mean(IPDefl[-last_n:]),
        'mean_Rot_speed': np.mean(Rot_speed[-last_n:]),
    }


def initialize_elastodyn(elastodyn_path, ss_means):
    ed = FASTInputFile(elastodyn_path)

    ed['OoPDefl'] = ss_means['mean_OoPDefl']
    ed['IPDefl'] = ss_means['mean_IPDefl']
    ed['BlPitch(1)'] = ss_means['mean_pitch']
    ed['BlPitch(2)'] = ss_means['mean_pitch']
    ed['BlPitch(3)'] = ss_means['mean_pitch']
    ed['RotSpeed'] = ss_means['mean_Rot_speed']

    ed.write(elastodyn_path)


def set_inflow_case(inflow_file, bts_path, yaw_deg, incl_deg):
    inflow = FASTInputFile(inflow_file)

    inflow['WindType'] = 3
    inflow['FileName_BTS'] = '"' + bts_path + '"'

    if 'PropagationDir' in inflow.keys():
        inflow['PropagationDir'] = float(yaw_deg)

    if 'VFlowAng' in inflow.keys():
        inflow['VFlowAng'] = float(incl_deg)

    inflow.write(inflow_file)


def set_pitch_stuck_fault(
    servodyn_file,
    fault_time=100.0,
    stuck_blade=1,
    stuck_pitch_deg=None,
):
    """
    Pitch stuck fault:
    selected blade is fixed at stuck_pitch_deg from fault_time onward.

    Important:
    PitManRat = 0 means no movement after the maneuver starts.
    BlPitchF should be equal to the stuck pitch angle.
    """

    sd = FASTInputFile(servodyn_file)

    # Reset all blades: no pitch maneuver
    for ib in [1, 2, 3]:
        ks = f'TPitManS({ib})'
        kr = f'PitManRat({ib})'
        kf = f'BlPitchF({ib})'

        if ks in sd.keys():
            sd[ks] = 9999.9

        if kr in sd.keys():
            sd[kr] = 2.0

        if kf in sd.keys():
            sd[kf] = 0.0

    # Apply stuck fault to one blade
    ks = f'TPitManS({stuck_blade})'
    kr = f'PitManRat({stuck_blade})'
    kf = f'BlPitchF({stuck_blade})'

    if stuck_pitch_deg is None:
        raise ValueError("stuck_pitch_deg must be given.")

    if ks in sd.keys():
        sd[ks] = fault_time

    if kr in sd.keys():
        sd[kr] = 10.0      # key point: fixed pitch, no movement, it should not be 0, it will be null after stuck pitch degree

    if kf in sd.keys():
        sd[kf] = stuck_pitch_deg

    sd.write(servodyn_file)


def restore_inflow_to_uniform(inflow_file):
    inflow = FASTInputFile(inflow_file)
    inflow['WindType'] = 1
    inflow.write(inflow_file)

def ensure_outlist_channels(input_file, channels):
    """
    Add output channels to an OpenFAST module OutList if missing.
    Inserts before END in the OutList section.
    """
    with open(input_file, "r") as f:
        lines = f.readlines()

    existing_text = "".join(lines)

    missing = []
    for ch in channels:
        if f'"{ch}"' not in existing_text:
            missing.append(ch)

    if not missing:
        return

    # find END of OutList
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("END"):
            end_idx = i
            break

    if end_idx is None:
        raise RuntimeError(f"Could not find END in OutList of {input_file}")

    new_lines = [f'"{ch}"\n' for ch in missing]
    lines = lines[:end_idx] + new_lines + lines[end_idx:]

    with open(input_file, "w") as f:
        f.writelines(lines)

    print(f"Added channels to {input_file}: {missing}")


def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    fast_dir = os.path.join(this_dir, '_NREL5MW_FASTfiles/5MW_Land_DLL_WTurb')
    fst_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.fst')
    inflow_file = os.path.join(fast_dir, '../5MW_Baseline/NRELOffshrBsline5MW_InflowWind.dat')
    servodyn_file = os.path.join(fast_dir, 'NRELOffshrBsline5MW_Onshore_ServoDyn.dat')
    elastodyn_file = os.path.join(fast_dir, 'NRELOffshrBsline5MW_Onshore_ElastoDyn.dat')

    wind_dir = os.path.join(this_dir, 'Test_Cases/Wind/')
    SS_output_dir = os.path.join(this_dir, 'PowerCurve_und_SS_Results')

    FAST_EXE = os.path.join(
        this_dir,
        '../../../miniconda3/envs/openfast_env/bin/openfast'
    )

    output_dir = os.path.join(this_dir, 'DLC2p4_PitchStuck_OF_results')
    safe_mkdir(output_dir)

    # --------------------------------------------------
    # full matrix, replace these lines with:
    URefs = np.arange(3, 26, 2)
    seeds = list(range(1, 13))
    yaw_errors = [-10.0, 0.0, 10.0]
    inclinations = [0.0, 8.0]
    # --------------------------------------------------
    # Test mode: only one case 
    # URefs = [13.0]
    # seeds = [1]
    # yaw_errors = [0.0]
    # inclinations = [0.0]

    fault_time = 100.0
    stuck_blade = 1

    inflow_backup = inflow_file + '.bak_pitchstuck'
    servodyn_backup = servodyn_file + '.bak_pitchstuck'
    elastodyn_backup = elastodyn_file + '.bak_pitchstuck'

    if not os.path.exists(inflow_backup):
        shutil.copy2(inflow_file, inflow_backup)
    if not os.path.exists(servodyn_backup):
        shutil.copy2(servodyn_file, servodyn_backup)
    if not os.path.exists(elastodyn_backup):
        shutil.copy2(elastodyn_file, elastodyn_backup)

    try:
        for u in URefs:
            ss_output_filename = f'output_U{u:.1f}.outb'
            ss_output_path = os.path.join(SS_output_dir, ss_output_filename)

            if not os.path.exists(ss_output_path):
                print(f"⚠️ SS file not found: {ss_output_path}")
                continue

            ss_means = get_ss_means(ss_output_path)

            # Important:
            # For pitch stuck, stuck angle is usually the current pitch at fault time / operating point.
            stuck_pitch_deg = float(ss_means['mean_pitch'])  #float(ss_means['mean_pitch'])

            for seed in seeds:
                bts_filename = f'TurbSim_U{int(u)}_Seed{seed}.bts'
                bts_path = os.path.join(wind_dir, bts_filename)

                if not os.path.exists(bts_path):
                    print(f"⚠️ BTS file not found: {bts_path}")
                    continue

                for yaw_deg in yaw_errors:
                    for incl_deg in inclinations:

                        shutil.copy2(inflow_backup, inflow_file)
                        shutil.copy2(servodyn_backup, servodyn_file)
                        shutil.copy2(elastodyn_backup, elastodyn_file)

                        ensure_outlist_channels(
                            elastodyn_file,
                            ["BldPitch1", "BldPitch2", "BldPitch3", "RotSpeed"]
                        )

                        ensure_outlist_channels(
                            servodyn_file,
                            ["GenPwr"]
                        )

                        initialize_elastodyn(elastodyn_file, ss_means)

                        set_inflow_case(
                            inflow_file=inflow_file,
                            bts_path=bts_path,
                            yaw_deg=yaw_deg,
                            incl_deg=incl_deg
                        )

                        set_pitch_stuck_fault(
                            servodyn_file=servodyn_file,
                            fault_time=fault_time,
                            stuck_blade=stuck_blade,
                            stuck_pitch_deg=stuck_pitch_deg,
                        )

                        output_filename = (
                            f'output_U{u:.1f}'
                            f'_Seed{seed}'
                            f'_Yaw{yaw_deg:+.0f}'
                            f'_Inc{incl_deg:+.0f}'
                            f'_PitchStuckB{stuck_blade}.outb'
                        )

                        output_path = os.path.join(output_dir, output_filename)

                        if os.path.exists(output_path):
                            print(f"⏭ Skipping existing case: {output_filename}")
                            continue

                        print(
                            f"➡️ Running Pitch Stuck: U={u:.1f} m/s | Seed={seed} "
                            f"| Yaw={yaw_deg:+.0f}° | Inc={incl_deg:+.0f}° "
                            f"| Blade={stuck_blade} stuck at {stuck_pitch_deg:.3f} deg "
                            f"| fault @ {fault_time:.1f}s"
                        )

                        run_openfast(
                            fast_dir,
                            fastfile=fst_file,
                            fastcall=FAST_EXE,
                            chdir=True
                        )

                        out_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.outb')

                        if not os.path.exists(out_file):
                            print(f"❌ Output file not found: {output_filename}")
                            continue

                        os.rename(out_file, output_path)

    finally:
        if os.path.exists(inflow_backup):
            shutil.copy2(inflow_backup, inflow_file)
        if os.path.exists(servodyn_backup):
            shutil.copy2(servodyn_backup, servodyn_file)
        if os.path.exists(elastodyn_backup):
            shutil.copy2(elastodyn_backup, elastodyn_file)

        restore_inflow_to_uniform(inflow_file)
        print("\n✅ Original input files restored.\n")


if __name__ == "__main__":
    main()