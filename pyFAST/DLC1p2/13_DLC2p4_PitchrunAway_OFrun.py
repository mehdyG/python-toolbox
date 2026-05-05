"""
Run OpenFAST for DLC 2.4 / pitch runaway cases
- One blade runaway to fine pitch
- 12 seeds
- URefs from 3 to 25 m/s, step 2
- yaw errors: -10, 0, +10 deg
- inclinations: 0, +8 deg

Based on the style of the user's DLC1.2 runner.
"""

import os
import shutil
import numpy as np
from pyFAST.input_output import FASTInputFile, FASTOutputFile
from rosco.toolbox.utilities import run_openfast


def safe_mkdir(path):
    os.makedirs(path, exist_ok=True)


def get_ss_means(ss_output_path):
    """
    Read steady-state output and compute mean values over the last 5%.
    """
    SS_out = FASTOutputFile(ss_output_path).toDataFrame()

    time = SS_out['Time_[s]']
    power = SS_out['GenPwr_[kW]']
    pitch = SS_out['BldPitch1_[deg]']
    gen_speed = SS_out['GenSpeed_[rpm]']
    gen_torque = SS_out['GenTq_[kN-m]']
    OoPDefl = SS_out['OoPDefl1_[m]']
    IPDefl = SS_out['IPDefl1_[m]']
    Rot_speed = SS_out['RotSpeed_[rpm]']

    N = len(time)
    last_n = max(1, int(0.05 * N))

    return {
        'mean_power': np.mean(power[-last_n:]),
        'mean_pitch': np.mean(pitch[-last_n:]),
        'mean_speed': np.mean(gen_speed[-last_n:]),
        'mean_torque': np.mean(gen_torque[-last_n:]),
        'mean_OoPDefl': np.mean(OoPDefl[-last_n:]),
        'mean_IPDefl': np.mean(IPDefl[-last_n:]),
        'mean_Rot_speed': np.mean(Rot_speed[-last_n:]),
    }


def initialize_elastodyn(elastodyn_path, ss_means):
    """
    Set initial conditions from steady-state results.
    """
    ed = FASTInputFile(elastodyn_path)

    ed['OoPDefl'] = ss_means['mean_OoPDefl']
    ed['IPDefl'] = ss_means['mean_IPDefl']
    ed['BlPitch(1)'] = ss_means['mean_pitch']
    ed['BlPitch(2)'] = ss_means['mean_pitch']
    ed['BlPitch(3)'] = ss_means['mean_pitch']
    ed['RotSpeed'] = ss_means['mean_Rot_speed']

    ed.write(elastodyn_path)


def set_inflow_case(inflow_file, bts_path, yaw_deg, incl_deg):
    """
    Modify InflowWind file for one turbulent wind file + yaw error + inclination.
    """
    inflow = FASTInputFile(inflow_file)

    inflow['WindType'] = 3
    inflow['FileName_BTS'] = '"' + bts_path + '"'

    # Yaw misalignment as wind propagation direction offset
    # Check your sign convention once with a quick test.
    if 'PropagationDir' in inflow.keys():
        inflow['PropagationDir'] = float(yaw_deg)
    else:
        print("⚠️ 'PropagationDir' not found in InflowWind file.")

    # Flow inclination angle
    if 'VFlowAng' in inflow.keys():
        inflow['VFlowAng'] = float(incl_deg)
    else:
        print("⚠️ 'VFlowAng' not found in InflowWind file.")

    inflow.write(inflow_file)


def set_runaway_fault(servodyn_file,
                      fault_time=100.0,
                      runaway_rate_deg_s=10.0,
                      fine_pitch_deg=0.0,
                      runaway_blade=1):

    sd = FASTInputFile(servodyn_file)

    # --- Reset all blades ---
    for ib in [1, 2, 3]:
        ks = f'TPitManS({ib})'
        kr = f'PitManRat({ib})'
        kf = f'BlPitchF({ib})'

        if ks in sd.keys():
            sd[ks] = 9999.9   # no maneuver

        if kr in sd.keys():
            sd[kr] = 2.0      # default (safe)

        if kf in sd.keys():
            sd[kf] = sd.get(kf, 0.0)

    # --- Apply runaway ONLY on selected blade ---
    ks = f'TPitManS({runaway_blade})'
    kr = f'PitManRat({runaway_blade})'
    kf = f'BlPitchF({runaway_blade})'

    if ks in sd.keys():
        sd[ks] = fault_time
    else:
        print(f"⚠️ {ks} not found")

    if kr in sd.keys():
        sd[kr] = runaway_rate_deg_s   # 🔥 THIS is the key fix (10 deg/s)
    else:
        print(f"⚠️ {kr} not found")

    if kf in sd.keys():
        sd[kf] = fine_pitch_deg
    else:
        print(f"⚠️ {kf} not found")

    sd.write(servodyn_file)

def restore_inflow_to_uniform(inflow_file):
    """
    Restore a simple default at the end.
    """
    inflow = FASTInputFile(inflow_file)
    inflow['WindType'] = 1
    inflow.write(inflow_file)


def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))

    # ---------------- Paths ----------------
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

    output_dir = os.path.join(this_dir, 'DLC2p4_Runaway_OF_results')
    safe_mkdir(output_dir)

    # ---------------- Case definition ----------------
    URefs = np.arange(3, 26, 2)           # 3,5,...,25
    seeds = list(range(1, 13))            # 12 seeds: 1..12
    yaw_errors = [-10.0, 0.0, 10.0]       # deg
    inclinations = [0.0, 8.0]             # deg

    # ---------------- Fault definition ----------------
    runaway_blade = 1
    fault_time = 100.0
    runaway_rate_deg_s = 10.0             # set to your actuator max pitch rate
    fine_pitch_deg = 0.0                  # adjust if your turbine's fine pitch is different

    # Backup original files once
    inflow_backup = inflow_file + '.bak_dlc24'
    servodyn_backup = servodyn_file + '.bak_dlc24'
    elastodyn_backup = elastodyn_file + '.bak_dlc24'

    if not os.path.exists(inflow_backup):
        shutil.copy2(inflow_file, inflow_backup)
    if not os.path.exists(servodyn_backup):
        shutil.copy2(servodyn_file, servodyn_backup)
    if not os.path.exists(elastodyn_backup):
        shutil.copy2(elastodyn_file, elastodyn_backup)

    try:
        for u in URefs:
            print(f'\n================ URef = {u:.1f} m/s ================\n')

            # ---------- Initialization from SS ----------
            ss_output_filename = f'output_U{u:.1f}.outb'
            ss_output_path = os.path.join(SS_output_dir, ss_output_filename)

            if not os.path.exists(ss_output_path):
                print(f"⚠️ SS file not found: {ss_output_path}")
                continue

            ss_means = get_ss_means(ss_output_path)
            initialize_elastodyn(elastodyn_file, ss_means)

            init_pitch_deg = float(ss_means['mean_pitch'])

            for seed in seeds:
                bts_filename = f'TurbSim_U{u}_Seed{seed}.bts'
                bts_path = os.path.join(wind_dir, bts_filename)

                if not os.path.exists(bts_path):
                    print(f"⚠️ BTS file not found: {bts_path}")
                    continue

                for yaw_deg in yaw_errors:
                    for incl_deg in inclinations:

                        # Restore clean originals before editing each case
                        shutil.copy2(inflow_backup, inflow_file)
                        shutil.copy2(servodyn_backup, servodyn_file)
                        shutil.copy2(elastodyn_backup, elastodyn_file)

                        # Re-apply SS initialization after restore
                        initialize_elastodyn(elastodyn_file, ss_means)

                        # Inflow case
                        set_inflow_case(
                            inflow_file=inflow_file,
                            bts_path=bts_path,
                            yaw_deg=yaw_deg,
                            incl_deg=incl_deg
                        )

                        # Runaway fault case
                        fault_end = set_runaway_fault(
                            servodyn_file=servodyn_file,
                            fault_time=fault_time,
                            runaway_rate_deg_s=runaway_rate_deg_s,
                            fine_pitch_deg=fine_pitch_deg,
                            runaway_blade=runaway_blade
                        )

                        output_filename = (
                            f'output_U{u:.1f}'
                            f'_Seed{seed}'
                            f'_Yaw{yaw_deg:+.0f}'
                            f'_Inc{incl_deg:+.0f}'
                            f'_RunawayB{runaway_blade}.outb'
                        )
                        output_path = os.path.join(output_dir, output_filename)

                        if os.path.exists(output_path):
                            print(f"⏭ Skipping existing case: {output_filename}")
                            continue

                        print(
                            f'➡️ Running OF: U={u:.1f} m/s | Seed={seed:02d} '
                            f'| Yaw={yaw_deg:+.0f}° | Inc={incl_deg:+.0f}° '
                            f'| Runaway blade={runaway_blade} '
                            f'| fault @ {fault_time:.1f}s'
                        )

                        # Run OpenFAST
                        run_openfast(
                            fast_dir,
                            fastfile=fst_file,
                            fastcall=FAST_EXE,
                            chdir=True
                        )

                        out_file = os.path.join(fast_dir, '5MW_Land_DLL_WTurb.outb')
                        if not os.path.exists(out_file):
                            print(f"❌ Output file not found for case: {output_filename}")
                            continue

                        os.rename(out_file, output_path)

    finally:
        # Restore original files at end
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