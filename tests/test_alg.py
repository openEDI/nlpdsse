import json
import os

from nlpdsse.federate.alg import NLPDSSE


def test_alg():
	baseDir=os.path.dirname(os.path.abspath(__file__))
	data=json.load(open(os.path.join(baseDir,'alg_data.json')))

	dsse=NLPDSSE()
	sol=dsse.solve(data)
	assert sol['success']
