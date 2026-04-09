import os
import shlex
import signal
import subprocess
import time
from importlib.util import find_spec

import pytest
import requests


@pytest.fixture
def init():
	spec=find_spec('nlpdsse.microservice.server')
	proc=subprocess.Popen(shlex.split(f'python3 {spec.origin}'),preexec_fn=os.setpgrp)
	time.sleep(3)
	yield
	# better than proc.kill()
	os.killpg(os.getpgid(proc.pid), signal.SIGTERM)


def test_nlpdsse(init):
	payload={'static_inputs':{},'input_mapping':{}}
	payload['input_mapping']={"powers_real": "sensor_power_real/publication",\
		"powers_imaginary": "sensor_power_imaginary/publication", "topology":"feeder/topology"}

	url='http://127.0.0.1:5000'
	res=requests.post(url=url+'/run',json=payload)
	assert res.status_code==200
	data=res.json()

	res=requests.get(url=url+'/status',params={'uuid':data['uuid']})
	assert res.status_code==200

	res=requests.get(url=url+'/logs',params={'uuid':data['uuid']})
	assert res.status_code==200

	res=requests.get(url=url+'/results',params={'uuid':data['uuid']})
	assert res.status_code==200

