import logging
import sys

import casadi as c
import numpy as np
from scipy.sparse import coo_matrix

from nlpdsse.federate.data_model import DSSEDataModel

formatStr='%(asctime)s::%(name)s::%(filename)s::%(funcName)s::'+\
	'%(levelname)s::%(message)s::%(threadName)s::%(process)d'
logging.basicConfig(stream=sys.stdout,level=logging.INFO,format=formatStr)

logger=logging.getLogger(__name__)


class NLPDSSE:

	def solve(self,data):
		data=DSSEDataModel(**data).model_dump()
		nNodes=len(data['nodeOrder']['names'])

		if data['measurement']['sinj_nodeOrder']!=data['nodeOrder']['names']:
			pinj,qinj=[0]*nNodes,[0]*nNodes
			for n in range(len(data['measurement']['sinj_nodeOrder'])):
				name=data['measurement']['sinj_nodeOrder'][n]
				ind=data['nodeOrder']['name2ind'][name]
				pinj[ind]=data['measurement']['pinj'][n]
				qinj[ind]=data['measurement']['qinj'][n]
			data['measurement']['pinj']=pinj
			data['measurement']['qinj']=qinj

		vm0=data['x0'][0:nNodes]
		va0=data['x0'][nNodes:2*nNodes]
		v0=vm0*(np.cos(va0)+1j*np.sin(va0))
		data['x0']=v0.real.tolist()+v0.imag.tolist()

		rr,cc=np.array(data['ybus']['r']),np.array(data['ybus']['c'])
		vr,vi=np.array(data['ybus']['vr']),np.array(data['ybus']['vi'])

		row=np.vstack((rr,rr,rr+nNodes,rr+nNodes)).flatten()
		col=np.vstack((cc,cc+nNodes,cc,cc+nNodes)).flatten()
		val=np.vstack((vr,-vi,vi,vr)).flatten()

		ybusRect=c.SX(coo_matrix((val,(row,col)),shape=(2*nNodes,2*nNodes)))
		x = c.SX.sym('x',2*nNodes)

		data['measurement']['pinj']=np.array(data['measurement']['pinj'])
		data['measurement']['qinj']=np.array(data['measurement']['qinj'])

		a,b=data['measurement']['pinj'],data['measurement']['qinj']

		c2=x[0:nNodes]**2
		d2=x[nNodes:2*nNodes]**2
		fvr=(a*x[0:nNodes]+b*x[nNodes:2*nNodes])/(c2+d2)
		fvi=(b*x[0:nNodes]-a*x[nNodes:2*nNodes])/(c2+d2)
		fv=c.vertcat(fvr,-fvi)

		cons=ybusRect @ x + fv 
		consProb=c.vertcat(cons[3:nNodes],cons[nNodes+3::])
		xProb=c.vertcat(x[3:nNodes],x[nNodes+3::])
		p= c.vertcat(x[0:3],x[nNodes:nNodes+3])
		p0=data['x0'][0:3]+data['x0'][nNodes:nNodes+3]
		x0=np.array(data['x0'])
		x0=np.vstack((x0[3:nNodes],x0[nNodes+3:2*nNodes])).flatten()

		x,g=xProb,consProb
		rNodeInj=c.SX.sym('rNodeInj',x.shape[0]) 
		x0=np.hstack((x0,np.zeros(rNodeInj.shape[0]))).flatten()
		g+=rNodeInj

		nodeNames=data['nodeOrder']['names']
		nNodes=len(nodeNames)
		nNodesVar=nNodes-3

		vm0=data['vm0'][3::]
		lbx=np.array(vm0*4)*-2
		ubx=np.array(vm0*4)*2

		ind={'vars':{}}
		ind['vars']['vr']=np.arange(0,nNodesVar)
		ind['vars']['vi']=np.arange(nNodesVar,2*nNodesVar)
		ind['vars']['residualIrInj']=np.arange(2*nNodesVar,3*nNodesVar)
		ind['vars']['residualIiInj']=np.arange(3*nNodesVar,4*nNodesVar)

		xExtended=c.vertcat(p0[0:3],x[0:nNodesVar],p0[3:6],x[nNodesVar:2*nNodesVar])
		cons=g
		x=c.vertcat(x,rNodeInj)
		f=c.sum1(rNodeInj**2)

		if 'sflow_real' in data['measurement'] and data['measurement']['sflow_real']:
			ybr=data['branch_flow']['y']
			ybrcoo=coo_matrix((np.array(ybr['vr'])+1j*np.array(ybr['vi']),(ybr['r'],ybr['c'])),\
				shape=(max(ybr['r'])+1,max(ybr['c'])+1))
			ybr=c.SX(self.complex_matrix_to_real(ybrcoo))

			sFlow=np.array(data['measurement']['sflow_real'])+\
				1j*np.array(data['measurement']['sflow_imag'])
			nLines=sFlow.shape[0]
			brNodeInd=np.array(data['branch_flow']['nodeInd'])

			c2=xExtended[brNodeInd]**2
			d2=xExtended[nNodes+brNodeInd]**2
			a,b=sFlow.real,sFlow.imag
			sFlowr=(a*xExtended[brNodeInd]+b*xExtended[nNodes+brNodeInd])/(c2+d2)
			sFlowi=(b*xExtended[brNodeInd]-a*xExtended[nNodes+brNodeInd])/(c2+d2)
			sFlow=c.vertcat(sFlowr,-sFlowi)

			brNodeInd=np.hstack((brNodeInd,brNodeInd+nNodes)).flatten()

			rSFlow=c.SX.sym('rSFlow',brNodeInd.shape[0])
			gSFlow= ybr @ xExtended[brNodeInd] - sFlow + rSFlow
			cons=c.vertcat(cons,gSFlow)
			x=c.vertcat(x,rSFlow)
			f+=c.sum1(rSFlow**2)

			x0=np.hstack((x0,np.zeros(rSFlow.shape[0]))).flatten()
			lbx=np.hstack((lbx,np.ones(rSFlow.shape[0])*-1e6)).flatten()
			ubx=np.hstack((ubx,np.ones(rSFlow.shape[0])*1e6)).flatten()

			ind['vars']['residualSrFlow']=np.arange(4*nNodesVar,4*nNodesVar+nLines)
			ind['vars']['residualSiFlow']=np.arange(4*nNodesVar+nLines,4*nNodesVar+2*nLines)

		opts={"ipopt":{"acceptable_tol":1e-3,"dual_inf_tol":1e-3,'acceptable_constr_viol_tol':1e-3}}
		prob={'x':x,'p':p,'g':cons,'f':f}
		logger.info('building solver')
		solver=c.nlpsol("solver","ipopt",prob,opts)
		logger.info('completed building solver')

		assert lbx.shape==ubx.shape and lbx.shape==x0.shape, 'variable dimension mismatch'
		lbg=np.zeros(cons.shape[0])
		ubg=np.zeros(cons.shape[0])
		assert lbg.shape==ubg.shape and lbg.shape[0]==cons.shape[0], 'constraint dimension mismatch'

		res={}
		res['sol']=solver(x0=x0,p=p0,lbg=lbg,ubg=ubg,lbx=lbx,ubx=ubx)

		xsol=res['sol']['x'].toarray().flatten()
		v=xsol[ind['vars']['vr']]+1j*xsol[ind['vars']['vi']]
		v=np.hstack((np.array(p0[0:3])+1j*np.array(p0[3::]),v))
		assert v.shape[0]==len(nodeNames)
		res={'vm':np.abs(v),'va':np.angle(v),'ids':nodeNames}
		res['success']=solver.stats()['success']

		return res

#=======================================================================================================================
	def complex_matrix_to_real(self,A):
		nRows,nCols=A.shape[0],A.shape[1]
		rr,cc,val=A.row,A.col,A.data
		vr,vi=val.real,val.imag

		row=np.vstack((rr,rr,rr+nRows,rr+nRows)).flatten()
		col=np.vstack((cc,cc+nCols,cc,cc+nCols)).flatten()
		val=np.vstack((vr,-vi,vi,vr)).flatten()

		AReal=coo_matrix((val,(row,col)),shape=(2*nRows,2*nCols))

		return AReal

