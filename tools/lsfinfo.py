#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  5 07:17:43 2019

@author: verhager
"""

import subprocess
import sys

def test_if_lsf_installed():
    try:
       subprocess.getoutput("xbhosts -h")
    except:
       sys.exit("LFS is not installed")

def getinfo(command, splitchar):
    z=subprocess.getoutput(command)
    output=[]
    for regel in z.split("\n"):
        if splitchar=="":
            output.append(regel.split())
        else:
            output.append(regel.split(splitchar))
    return(output)

 


def main():
    test_if_lsf_installed()
    bhosts=getinfo("bhosts -w bioinfo", "")
    busers=getinfo("busers all", "")
    bjobs=getinfo("bjobs -u all -o \"JOBID USER STAT QUEUE FROM_HOST EXEC_HOST JOB_NAME   SUBMIT_TIME: delimiter='^'\"", "^")
    lsload=getinfo("lsload -w","")
    #sys.exit(1)
    
    for teller in range(len(bhosts)):
        print(bhosts[teller])

    print()


    for teller in range(len(busers)):
        if busers[teller][3] != "0" and busers[teller][3] != "-":
            print(busers[teller])

    print()
    
    for teller in range(len(bjobs)):
        print(bjobs[teller])

    print()
    
    for teller in range(len(lsload)):
        print(lsload[teller])


if __name__ == '__main__':
    main()
