import json
import os
import shlex
import subprocess
import uuid
from http import HTTPStatus
from importlib.util import find_spec

import psutil
from flask import Flask, Response, request

from nlpdsse.microservice.data_model import InputMapping, StaticInputs

procMap={}
spec=find_spec('nlpdsse.federate.alg')
baseDir=os.path.dirname(os.path.abspath(spec.origin))


#=======================================================================================================================
def run():
	data=request.json
	assert not set(['static_inputs','input_mapping']).difference(data.keys())
	inputMapping=InputMapping(**data['input_mapping']).model_dump()
	staticInputs=StaticInputs(**data['static_inputs']).model_dump()

	runUUID=uuid.uuid4().hex

	dirPath=f'/tmp/{runUUID}'
	directive=f'mkdir -p {dirPath} && cp -r {baseDir}/* {dirPath}'
	flag=os.system(directive)
	assert flag==0

	# update based on payload
	json.dump(inputMapping,open(os.path.join(dirPath,'input_mapping.json'),'w'))

	runPath=os.path.join(dirPath,'fed.py')
	directive=f'python3 {runPath}'
	proc=subprocess.Popen(shlex.split(directive),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
	procMap[runUUID]=proc.pid

	res=Response(status=HTTPStatus.OK)
	res.mimetype='application/json'
	res.response=json.dumps({"success":True,"uuid":runUUID})
	return res


#=======================================================================================================================
def status():
	runUUID = request.args.get('uuid')
	if runUUID in procMap:
		procStatus='completed'
		procExists=psutil.pid_exists(procMap[runUUID])
		if procExists:
			p=psutil.Process(procMap[runUUID])
			if p.status()!='zombie':
				procStatus='running'
		res=Response(status=HTTPStatus.OK)
		res.mimetype='application/json'
		res.response=json.dumps({"success":True,"status":procStatus})
	else:
		res=Response(status=HTTPStatus.BAD_REQUEST)
		res.mimetype='application/json'
		res.response=json.dumps({"success":False,"error":f"UUID {runUUID} does not exist"})
	return res


#=======================================================================================================================
def results():
	runUUID = request.args.get('uuid')
	if runUUID in procMap:
		res=Response(status=HTTPStatus.OK)
		res.mimetype='application/json'
		res.response=json.dumps({"success":True,"data":{}})
	else:
		res=Response(status=HTTPStatus.BAD_REQUEST)
		res.mimetype='application/json'
		res.response=json.dumps({"success":False,"error":f"UUID {runUUID} does not exist"})
	return res


#=======================================================================================================================
if __name__ == '__main__':
	app = Flask(__name__)
	app.add_url_rule(rule='/run',methods=['POST'],view_func=run)
	app.add_url_rule(rule='/status',methods=['GET'],view_func=status)
	app.add_url_rule(rule='/results',methods=['GET'],view_func=results)
	app.run(host='0.0.0.0',port=5000,debug=False,use_reloader=True,threaded=True)


