import json
import os

from nlpdsse.federate.alg import NLPDSSE


def test_alg():
	baseDir=os.path.dirname(os.path.abspath(__file__))
	dsse=NLPDSSE()
	for item in os.listdir(os.path.join(baseDir,'data')):
		data=json.load(open(os.path.join(baseDir,'data',item)))
		sol=dsse.solve(data)
		assert sol['success']
