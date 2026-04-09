import json
import logging
import os
import sys

import helics as h
import numpy as np
import oedisi.types.data_types as OEDISITypes

from nlpdsse.federate.alg import NLPDSSE

formatStr='%(asctime)s::%(name)s::%(filename)s::%(funcName)s::'+\
	'%(levelname)s::%(message)s::%(threadName)s::%(process)d'
logging.basicConfig(stream=sys.stdout,level=logging.INFO,format=formatStr)
logger=logging.getLogger(__name__)


class NLPDSSEFederate:

	def __init__(self,config,inputMapping,componentDefinition,staticInputs,federate_name='nlpdsse',dt=1):
		self.dsse=NLPDSSE()
		self.dsseInputData={}
		self.config=config
		self.staticInputs=staticInputs
		self.inputMapping=inputMapping
		self.config['federate_config']['name']=federate_name
		self.config['federate_config']['subscriptions']=[]
		self.config['federate_config']['publications']=[]
		self.config['simulation_config'].update(staticInputs)

		if 'broker_address' in staticInputs:
			self.config['federate_config']['broker_address']=staticInputs['broker_address']
		if 'port' in staticInputs:
			self.config['federate_config']['port']=staticInputs['port']


		for entry in inputMapping:
			self.config['federate_config']['subscriptions'].append(\
				{'global':True,'type':'string','key':inputMapping[entry]})

		# mapping
		self.mapping={'subid2type':{},'pubid2type':{},'subFunc':{},'pubFunc':{}}

		for entry in componentDefinition['dynamic_inputs']:
			key=inputMapping[entry['port_id']]
			assert entry['type'] in OEDISITypes.__dict__,f'The following type is unavailable {entry["type"]}'
			self.mapping['subid2type'][key]=entry['type']
			self.mapping['subFunc'][key]=OEDISITypes.__dict__[entry['type']]

		for entry in componentDefinition['dynamic_outputs']:
			key=f'{federate_name}/{entry["port_id"]}'
			assert entry['type'] in OEDISITypes.__dict__,f'The following type is unavailable {entry["type"]}'
			self.mapping['pubid2type'][key]=entry['type']
			self.mapping['pubFunc'][key]=OEDISITypes.__dict__[entry['type']]
			self.config['federate_config']['publications'].append({'global':True,'type':'string','key':key})

		self.federate_name = federate_name

		self.dt=dt
		logger.info('completed init')
		logger.info(f'federate_config::::{self.config["federate_config"]}')


#=======================================================================================================================
	def setup(self,testMode=False):
		logger.info('creating federate')
		if testMode:
			logger.info('in testMode')
			self.start_broker(1)
		self.federate=h.helicsCreateValueFederateFromConfig(json.dumps(self.config['federate_config']))
		self.pub=self.federate.publications
		self.sub=self.federate.subscriptions
		logger.info('completed setup')


#=======================================================================================================================
	def simulate(self,simEndTime=None):
		if not simEndTime:
			simEndTime=self.config['simulation_config']['end_time']
		self.federate.enter_executing_mode()
		logger.info('entered execution mode')

		grantedTime=0
		grantedTime = h.helicsFederateRequestTime(self.federate,grantedTime)

		while grantedTime<simEndTime:
			# get subscriptions
			subs=self.get_sub(checkForUpdate=True,returnAsDict=True)
			logger.info(f'Received subscription')

			data=self.alg(subs)
			if data:
				missingPubKeys=set(self.pub.keys()).difference(data.keys())
				assert not missingPubKeys, f'missing the following pub keys:{missingPubKeys}'

				# set publications
				self.set_pub(data,timestamp=subs[self.inputMapping['powers_real']]['time'])
				logger.info(f'Sent Publication::::{data.keys()}')

			grantedTime = h.helicsFederateRequestTime(self.federate,grantedTime+1)
			logger.info(f'grantedTime::::{grantedTime}')

		logger.info('completed simulation')


#=======================================================================================================================
	def start_broker(self,nFeds):
		logger.info('starting broker')
		initstring = "-f {} --name=mainbroker".format(nFeds)
		self.broker = h.helicsCreateBroker("zmq", "", initstring)
		assert h.helicsBrokerIsConnected(self.broker)==1,"broker connection failed"
		logger.info('created broker')


#=======================================================================================================================
	def get_sub(self,checkForUpdate=False,returnAsDict=True):
		data={}
		for entry in self.sub:
			data[entry]={}
			typeFunc=self.mapping['subFunc'][entry]
			if checkForUpdate:
				if self.sub[entry].is_updated():
					temp=typeFunc.model_validate(self.sub[entry].json) # validate
					data[entry]=self.sub[entry].json if returnAsDict else temp
			else:
				temp=typeFunc.model_validate(self.sub[entry].json) # validate
				data[entry]=self.sub[entry].json if returnAsDict else temp
		return data


#=======================================================================================================================
	def set_pub(self,data:dict,timestamp:str):
		for entry in self.pub:
			typeFunc=self.mapping['pubFunc'][entry]
			if data[entry]:
				data[entry]['time']=timestamp
				self.pub[entry].publish(typeFunc(**data[entry]).model_dump_json())


#=======================================================================================================================
	def alg(self,subData):
		if self.inputMapping['powers_real'] in subData and subData[self.inputMapping['powers_real']]:
			self.dsseInputData['measurement']={'pinj':subData[self.inputMapping['powers_real']]['values'],\
				'qinj':subData[self.inputMapping['powers_imaginary']]['values'],\
				'sinj_nodeOrder':subData[self.inputMapping['powers_imaginary']]['ids']}

		if self.inputMapping['topology'] in subData and subData[self.inputMapping['topology']]:
			topo=subData[self.inputMapping['topology']]
			self.dsseInputData['vm0']=topo['base_voltage_magnitudes']['values']
			self.dsseInputData['x0']=topo['base_voltage_magnitudes']['values']+topo['base_voltage_angles']['values']
			names=topo['base_voltage_magnitudes']['ids']
			self.dsseInputData['nodeOrder']={'names':names}
			self.dsseInputData['nodeOrder']['name2ind']={names[n]:n for n in range(len(names))}
			self.dsseInputData['nodeOrder']['ind2name']={n:names[n] for n in range(len(names))}

			#### TODO: submit PR to add ybus (with no assets disabled) to feeder publication + add SFlow to publications
			#### See tests/alg_data.json for reference
			if 'from_equipment' in topo['admittance']:
				name2ind=self.dsseInputData['nodeOrder']['name2ind']
				from_equipment=[name2ind[name] for name in topo['admittance']['from_equipment']]
				to_equipment=[name2ind[name] for name in topo['admittance']['to_equipment']]
				self.dsseInputData['ybus']={'r':from_equipment,\
					'c':to_equipment,'vr':[val[0] for val in topo['admittance']['admittance_list']],\
					'vi':[val[1] for val in topo['admittance']['admittance_list']]}
			elif 'admittance_matrix' in topo['admittance']:
				ybus=np.array(topo['admittance']['admittance_matrix'])
				ybus=ybus[:,:,0]+1j*ybus[:,:,1]
				r,c=np.where(ybus!=0)
				val=ybus[r,c]
				self.dsseInputData['ybus']={'r':r.tolist(),'c':c.tolist(),'vr':val.real.tolist(),'vi':val.imag.tolist()}

		data=None
		if 'ybus' in self.dsseInputData and 'measurement' in self.dsseInputData:
			sol=self.dsse.solve(self.dsseInputData)
			data={}
			data[f'{self.federate_name}/voltage_mag']=\
				OEDISITypes.VoltagesMagnitude(ids=sol['ids'],values=sol['vm']).model_dump()
			data[f'{self.federate_name}/voltage_angle']=\
				OEDISITypes.VoltagesAngle(ids=sol['ids'],values=sol['va']).model_dump()

		return data

#=======================================================================================================================
	def finalize(self):
		h.helicsFederateFree(self.federate)
		h.helicsCloseLibrary()
		logger.info('Finalized -- objects released')


#=======================================================================================================================
if __name__=='__main__':
	baseDir=os.path.dirname(os.path.abspath(__file__))
	config=json.load(open(os.path.join(baseDir,'config.json')))
	inputMapping=json.load(open(os.path.join(baseDir,'input_mapping.json')))
	componentDefinition=json.load(open(os.path.join(baseDir,'component_definition.json')))
	staticInputs=json.load(open(os.path.join(baseDir,'static_inputs.json')))

	fed=NLPDSSEFederate(config,inputMapping,componentDefinition,staticInputs)
	fed.setup()
	fed.simulate()
	fed.finalize()

