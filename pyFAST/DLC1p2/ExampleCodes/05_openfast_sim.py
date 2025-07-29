"""
05_openfast_sim
---------------
Load a turbine, tune a controller, run OpenFAST simulation 
In this example:

* Load a turbine from OpenFAST
* Tune a controller
* Run an OpenFAST simulation

Note

* you will need to have a compiled controller in ROSCO/build/ 
"""

# Python Modules
#import yaml
import os
import numpy as np
import matplotlib.pyplot as plt
from pyFAST.input_output import FASTOutputFile

# ROSCO toolbox modules 
from rosco.toolbox import controller as ROSCO_controller
from rosco.toolbox import turbine as ROSCO_turbine
from rosco.toolbox.utilities import write_DISCON, run_openfast
from rosco.toolbox.inputs.validation import load_rosco_yaml
from rosco import discon_lib_path

def main():
    this_dir = os.path.dirname(os.path.abspath(__file__))
    tune_dir =  os.path.join(this_dir,'Tune_Cases')
    example_out_dir = os.path.join(this_dir,'examples_out')

    # Load yaml file 
    parameter_filename = os.path.join(tune_dir, 'NREL5MW.yaml') 
    inps = load_rosco_yaml(parameter_filename)
    path_params         = inps['path_params']
    turbine_params      = inps['turbine_params']
    controller_params   = inps['controller_params']

    # Instantiate turbine, controller, and file processing classes
    turbine         = ROSCO_turbine.Turbine(turbine_params)
    controller      = ROSCO_controller.Controller(controller_params)

    # Load turbine data from OpenFAST and rotor performance text file
    turbine.load_from_fast(
    path_params['FAST_InputFile'],
        os.path.join(tune_dir,path_params['FAST_directory']),
        rot_source='txt',
        txt_filename=os.path.join(tune_dir,path_params['rotor_performance_filename'])
        )

    # Setting up the location of ROSCO library
    turbine.fast.fst_vt['ServoDyn']['DLL_FileName'] = discon_lib_path

    # Tune controller 
    controller.tune_controller(turbine)

    # Write parameter input file
    param_file = os.path.join(this_dir,'DISCON.IN')   # This must be named DISCON.IN to be seen by the compiled controller binary. 
    write_DISCON(turbine,controller,param_file=param_file, txt_filename=path_params['rotor_performance_filename'])

    # Run OpenFAST
    # --- May need to change fastcall if you use a non-standard, conda-installed command to call openfast
    # If you run the `fastcall` from the command line where you run this script, it should run OpenFAST

    #print(os.path.join(tune_dir,path_params['FAST_directory'],'/NREL-5MW.outb'))
    #print("path_params['FAST_directory'] = ")
    #print( path_params['FAST_directory'] )

    #name = input()

    if not(os.path.exists( 'Test_Cases/NREL-5MW/NREL-5MW.outb' ) ) :
        fastcall = 'openfast'
        run_openfast(
        os.path.join(tune_dir,path_params['FAST_directory']),
        fastcall=fastcall, 
        fastfile=path_params['FAST_InputFile'], 
        chdir=True
        )

    fastoutFilename = os.path.join('Test_Cases/NREL-5MW/NREL-5MW.outb')
    df = FASTOutputFile(fastoutFilename).toDataFrame()
    print(df.keys())
    time  = df['Time_[s]']
    Omega = df['RotSpeed_[rpm]']
    V_wind = df['Wind1VelX_[m/s]']
    Theta = df['BldPitch1_[deg]']
    x_T = df['TTDspFA_[m]']
    Gen_Power = df['GenPwr_[kW]']


    fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5)
    fig.suptitle('Control System Test')
    ax1.plot(time, V_wind)
    ax2.plot(time, Omega)
    ax3.plot(time, Theta)
    ax4.plot(time, x_T)
    ax5.plot(time, Gen_Power)


    #plt.plot(time, Omega)
    #plt.xlabel('Time [s]')
    #plt.ylabel('RotSpeed [rpm]')
    ax1.set(xlabel='Time [s]', ylabel='V_wind [m/s]')
    ax2.set(xlabel='Time [s]', ylabel='RotSpeed [rpm]')
    ax3.set(xlabel='Time [s]', ylabel='Theta [deg]')
    ax4.set(xlabel='Time [s]', ylabel='x_T [m]')
    ax5.set(xlabel='Time [s]', ylabel='GenPwr [kW]')


if __name__ == "__main__":
    main()
    plt.show()