#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 15:23:56 2019

@author: wierinve
"""

from flask import Blueprint, render_template
from flask_login import login_required
import sys
import subprocess

bp = Blueprint('cluster', __name__, url_prefix='/cluster')


def getinfo(command, splitchar):
    z=subprocess.getoutput(command)
    output=[]
    for regel in z.split("\n"):
        if splitchar=="":
            output.append(regel.split())
        else:
            output.append(regel.split(splitchar))
    return(output)

def test_if_lsf_installed():
    try:
        subprocess.getoutput("bhosts -h")
    except:
        sys.exit("LFS is not installed")

@bp.route('/info')
@login_required
def info():
    test_if_lsf_installed()

    bhosts=getinfo("bhosts -w bioinfo", "")
    bhostsh=bhosts[0]
    bhosts.pop(0)

    busers=getinfo("busers all", "")
    busers_active=[]
    for teller in range(len(busers)):
        if busers[teller][3] != "0" and busers[teller][3] != "-":
            busers_active.append((busers[teller]))
    busersh=busers[0]
    busers.pop(0)
    busers_active.pop(0)

    bjobs=getinfo("bjobs -u svc-sscc-irods -o \"JOBID USER STAT QUEUE FROM_HOST EXEC_HOST JOB_NAME   SUBMIT_TIME: delimiter='^'\"", "^")
    bjobsh=bjobs[0]
    bjobs.pop(0)

    lsload=getinfo("lsload -w| grep -e rivm.ssc-campus.nl -e HOST_NAME| sort -n","")
    lsloadh=lsload[0]
    lsload.pop(0)

    return render_template('clusterinfo.html', bhostsh=bhostsh, bhosts=bhosts, busersh=busersh, busers=busers_active, bjobsh=bjobsh, bjobs=bjobs, lsloadh=lsloadh, lsload=lsload, items="all")
