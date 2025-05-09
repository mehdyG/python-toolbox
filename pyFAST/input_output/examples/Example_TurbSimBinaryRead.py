"""Read a TurbSim binary file
print keys of Turbsim File

"""


import os

from pyFAST.input_output import TurbSimFile
ts = TurbSimFile('TurbSim_FAST.bts')
print(ts.keys())
print(ts['u'].shape)  
print(ts['info'])
