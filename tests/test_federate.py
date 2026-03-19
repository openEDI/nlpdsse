import json
import os
from importlib.util import find_spec

from nlpdsse.federate.fed import NLPDSSEFederate


def test_federate():
	spec=find_spec('nlpdsse.federate.alg')
	baseDir=os.path.dirname(os.path.abspath(spec.origin))
	config=json.load(open(os.path.join(baseDir,'config.json')))
	inputMapping=json.load(open(os.path.join(baseDir,'input_mapping.json')))
	componentDefinition=json.load(open(os.path.join(baseDir,'component_definition.json')))
	staticInputs=json.load(open(os.path.join(baseDir,'static_inputs.json')))

	dff=NLPDSSEFederate(config,inputMapping,componentDefinition,staticInputs)
	dff.setup(True)
	dff.simulate()
	dff.finalize()
